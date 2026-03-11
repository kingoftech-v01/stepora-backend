"""
Management command to create a superadmin with a verified EmailAddress.
Sets a random password and sends a password reset email so the user
can choose their own.

Usage:
  python manage.py create_admin --email admin@stepora.net --name "Jean-Hervé"
"""

import secrets

from django.core.management.base import BaseCommand

from apps.users.models import User
from core.auth.models import EmailAddress
from core.auth.tasks import send_password_reset_email


class Command(BaseCommand):
    help = "Create a superadmin with verified email and send password reset link"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", default="Admin")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        name = options["name"]
        random_password = secrets.token_urlsafe(32)

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(random_password)
            user.save()
            self.stdout.write(f"Updated existing user {email} to superadmin.")
        else:
            user = User.objects.create_superuser(
                email=email,
                password=random_password,
                display_name=name,
            )
            self.stdout.write(f"Created superadmin {email}.")

        # Ensure verified EmailAddress exists
        email_addr, created = EmailAddress.objects.get_or_create(
            user=user,
            email=email,
            defaults={"verified": True, "primary": True},
        )
        if not created:
            email_addr.verified = True
            email_addr.primary = True
            email_addr.save()

        # Send password reset email so user can set their own password
        send_password_reset_email.delay(str(user.id))
        self.stdout.write(self.style.SUCCESS(
            f"Done — {email} is superadmin. Password reset email sent."
        ))
