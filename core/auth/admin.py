from django.contrib import admin

from core.auth.models import EmailAddress, SocialAccount


@admin.register(EmailAddress)
class EmailAddressAdmin(admin.ModelAdmin):
    list_display = ("email", "user", "verified", "primary", "created_at")
    list_filter = ("verified", "primary")
    search_fields = ("email", "user__email")
    raw_id_fields = ("user",)


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "uid", "created_at", "last_login")
    list_filter = ("provider",)
    search_fields = ("user__email", "uid")
    raw_id_fields = ("user",)
