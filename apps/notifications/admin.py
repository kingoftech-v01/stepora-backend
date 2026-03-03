"""
Django admin configuration for Notifications app.
"""

import logging
from datetime import datetime

from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Notification, NotificationTemplate, NotificationBatch, UserDevice

logger = logging.getLogger(__name__)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model."""

    list_display = ['title', 'user', 'notification_type', 'status', 'scheduled_for', 'sent_at']
    list_filter = ['notification_type', 'status', 'scheduled_for', 'created_at']
    search_fields = ['title', 'body', 'user__email']
    ordering = ['-scheduled_for']
    readonly_fields = ['sent_at', 'read_at', 'created_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'notification_type', 'title', 'body')
        }),
        ('Data & Deep Linking', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Scheduling', {
            'fields': ('scheduled_for', 'status', 'sent_at', 'read_at')
        }),
        ('Retry Logic', {
            'fields': ('retry_count', 'max_retries', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    actions = ['send_now', 'mark_as_sent', 'mark_as_cancelled']

    def changelist_view(self, request, extra_context=None):
        """Add a 'Send Bulk' button to the notification list page."""
        extra_context = extra_context or {}
        extra_context['bulk_send_url'] = reverse('admin:notifications_bulk_send')
        return super().changelist_view(request, extra_context=extra_context)

    def send_now(self, request, queryset):
        """Deliver selected notifications via FCM/email/WebSocket right now."""
        from .services import NotificationDeliveryService
        service = NotificationDeliveryService()
        sent = 0
        failed = 0
        for notification in queryset:
            try:
                success = service.deliver(notification)
                if success:
                    notification.status = 'sent'
                    notification.sent_at = timezone.now()
                    notification.save(update_fields=['status', 'sent_at'])
                    sent += 1
                else:
                    notification.mark_failed('All delivery channels failed')
                    failed += 1
            except Exception as e:
                notification.mark_failed(str(e))
                failed += 1
                logger.warning(f"Admin send_now failed for {notification.id}: {e}")
        self.message_user(request, f'{sent} sent, {failed} failed.')
    send_now.short_description = 'Send now (deliver via FCM/email)'

    def mark_as_sent(self, request, queryset):
        """Mark selected notifications as sent (without actually delivering)."""
        updated = queryset.update(status='sent')
        self.message_user(request, f'{updated} notifications marked as sent.')
    mark_as_sent.short_description = 'Mark selected as sent (no delivery)'

    def mark_as_cancelled(self, request, queryset):
        """Cancel selected notifications."""
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} notifications cancelled.')
    mark_as_cancelled.short_description = 'Cancel selected notifications'


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Notification templates."""

    list_display = ['name', 'notification_type', 'is_active', 'created_at']
    list_filter = ['notification_type', 'is_active', 'created_at']
    search_fields = ['name', 'title_template', 'body_template']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'notification_type', 'is_active')
        }),
        ('Template', {
            'fields': ('title_template', 'body_template', 'available_variables')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    """Admin interface for Notification batches."""

    list_display = ['name', 'notification_type', 'status', 'progress', 'created_at']
    list_filter = ['notification_type', 'status', 'created_at']
    search_fields = ['name']
    readonly_fields = ['total_scheduled', 'total_sent', 'total_failed', 'completed_at', 'created_at']

    def progress(self, obj):
        if obj.total_scheduled == 0:
            return '0%'
        percentage = (obj.total_sent / obj.total_scheduled) * 100
        return f'{percentage:.1f}% ({obj.total_sent}/{obj.total_scheduled})'
    progress.short_description = 'Progress'


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    """Admin interface for FCM device registrations."""

    list_display = ['user', 'platform', 'device_name', 'is_active', 'created_at', 'updated_at']
    list_filter = ['platform', 'is_active', 'created_at']
    search_fields = ['user__email', 'device_name', 'fcm_token']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user']


# ── Bulk Send Admin View ──────────────────────────────────────────


def _get_audience_queryset(audience, platform):
    """Return a User queryset filtered by audience and optional platform."""
    from apps.users.models import User

    qs = User.objects.filter(is_active=True)

    if audience == 'free':
        qs = qs.filter(subscription='free')
    elif audience == 'premium':
        qs = qs.filter(subscription='premium')
    elif audience == 'pro':
        qs = qs.filter(subscription='pro')
    elif audience == 'premium_pro':
        qs = qs.filter(subscription__in=['premium', 'pro'])
    elif audience == 'has_device':
        qs = qs.filter(devices__is_active=True).distinct()

    if platform:
        qs = qs.filter(devices__is_active=True, devices__platform=platform).distinct()

    return qs


def _get_audience_counts():
    """Get user counts for each audience segment."""
    from apps.users.models import User

    active = User.objects.filter(is_active=True)
    return {
        'all': active.count(),
        'free': active.filter(subscription='free').count(),
        'premium': active.filter(subscription='premium').count(),
        'pro': active.filter(subscription='pro').count(),
        'premium_pro': active.filter(subscription__in=['premium', 'pro']).count(),
        'has_device': active.filter(devices__is_active=True).distinct().count(),
    }


def bulk_send_view(request):
    """Admin view for sending notifications to groups of users."""
    if not request.user.is_staff:
        return redirect('admin:login')

    result = None

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        notification_type = request.POST.get('notification_type', 'system')
        audience = request.POST.get('audience', 'all')
        platform = request.POST.get('platform', '')
        delivery = request.POST.get('delivery', 'now')
        scheduled_for_str = request.POST.get('scheduled_for', '')

        if title and body:
            from .services import NotificationDeliveryService

            users = _get_audience_queryset(audience, platform)
            now = timezone.now()

            if delivery == 'scheduled' and scheduled_for_str:
                try:
                    scheduled_for = timezone.make_aware(
                        datetime.strptime(scheduled_for_str, '%Y-%m-%dT%H:%M')
                    )
                except (ValueError, TypeError):
                    scheduled_for = now
            else:
                scheduled_for = now

            send_immediately = (delivery == 'now')

            # Create batch record
            batch = NotificationBatch.objects.create(
                name=f"Bulk: {title[:50]} ({audience})",
                notification_type=notification_type,
                total_scheduled=users.count(),
                status='processing' if send_immediately else 'scheduled',
            )

            sent = 0
            failed = 0
            service = NotificationDeliveryService() if send_immediately else None

            for user in users.iterator():
                notification = Notification.objects.create(
                    user=user,
                    notification_type=notification_type,
                    title=title,
                    body=body,
                    scheduled_for=scheduled_for,
                    status='pending',
                )

                if send_immediately:
                    try:
                        success = service.deliver(notification)
                        if success:
                            notification.status = 'sent'
                            notification.sent_at = timezone.now()
                            notification.save(update_fields=['status', 'sent_at'])
                            sent += 1
                        else:
                            notification.mark_failed('All delivery channels failed')
                            failed += 1
                    except Exception as e:
                        notification.mark_failed(str(e))
                        failed += 1

            batch.total_sent = sent
            batch.total_failed = failed
            if send_immediately:
                batch.status = 'completed'
                batch.completed_at = timezone.now()
            batch.save()

            result = {
                'sent': sent,
                'failed': failed,
                'total': users.count(),
                'batch_id': str(batch.id),
                'batch_name': batch.name,
                'scheduled': not send_immediately,
            }

    counts = _get_audience_counts()

    return render(request, 'admin/notifications/bulk_send.html', {
        'title': 'Send Bulk Notification',
        'counts': counts,
        'result': result,
        'has_permission': True,
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
        'is_popup': False,
        'opts': Notification._meta,
    })


# Register the custom URL with the admin site
_original_get_urls = admin.AdminSite.get_urls


def _patched_get_urls(self):
    custom_urls = [
        path(
            'notifications/bulk-send/',
            self.admin_view(bulk_send_view),
            name='notifications_bulk_send',
        ),
    ]
    return custom_urls + _original_get_urls(self)


admin.AdminSite.get_urls = _patched_get_urls
