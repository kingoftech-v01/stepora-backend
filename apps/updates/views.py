import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AppBundle

# ── Load public key once at module level ──────────────────────

_PUBLIC_KEY = None


def _get_public_key():
    """Load the RSA public key for signature verification."""
    global _PUBLIC_KEY
    if _PUBLIC_KEY is not None:
        return _PUBLIC_KEY

    key_path = getattr(settings, "OTA_PUBLIC_KEY_PATH", None)
    if not key_path:
        return None

    try:
        with open(key_path, "rb") as f:
            _PUBLIC_KEY = serialization.load_pem_public_key(f.read())
        return _PUBLIC_KEY
    except Exception:
        return None


def _verify_signature(checksum: str, signature_b64: str) -> bool:
    """Verify that the signature matches the checksum using the RSA public key."""
    public_key = _get_public_key()
    if not public_key:
        # No public key configured — skip verification
        return True

    try:
        signature_bytes = base64.b64decode(signature_b64)
        public_key.verify(
            signature_bytes,
            checksum.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, Exception):
        return False


class UpdateCheckView(APIView):
    """
    Check for available OTA web bundle updates.
    Called by the mobile app at startup and from the AppVersion screen.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Check for OTA updates",
        description=(
            "Returns the latest active bundle for the given platform "
            "and native app version. Returns 204 if no update available "
            "or client already has the latest bundle."
        ),
        parameters=[
            OpenApiParameter(
                "platform", str, description="Client platform: android, ios"
            ),
            OpenApiParameter("app_version", str, description="Native versionCode"),
            OpenApiParameter(
                "bundle_id", str, description="Currently installed bundle ID"
            ),
        ],
        tags=["Updates"],
    )
    def get(self, request):
        platform = request.query_params.get("platform", "").lower()
        app_version_str = request.query_params.get("app_version", "0")
        current_bundle = request.query_params.get("bundle_id", "")

        try:
            app_version = int(app_version_str)
        except (ValueError, TypeError):
            app_version = 0

        # Find the latest active bundle compatible with this platform + version
        qs = AppBundle.objects.filter(is_active=True)

        if app_version > 0:
            qs = qs.filter(min_app_version__lte=app_version)

        if platform in ("android", "ios"):
            qs = qs.filter(platform__in=["all", platform])

        bundle = qs.first()  # Ordered by -created_at

        if not bundle:
            return Response({}, status=status.HTTP_204_NO_CONTENT)

        # Client already has this bundle
        if current_bundle and current_bundle == bundle.bundle_id:
            return Response({}, status=status.HTTP_204_NO_CONTENT)

        # Build download URL (S3 signed URL via storage backend)
        download_url = bundle.bundle_file.url

        return Response(
            {
                "bundle_id": bundle.bundle_id,
                "url": download_url,
                "strategy": bundle.strategy,
                "checksum": bundle.checksum or None,
                "signature": bundle.signature or None,
                "message": bundle.message or None,
                "min_app_version": bundle.min_app_version,
            }
        )


class BundleUploadView(APIView):
    """
    Upload a new OTA web bundle.
    Staff/admin only — called by the deploy script from any machine.

    POST /api/v1/updates/upload/
    Content-Type: multipart/form-data

    Fields:
      - file (required): The zip bundle
      - strategy: "silent" or "notify" (default: "notify")
      - platform: "all", "android", or "ios" (default: "all")
      - min_app_version: integer (default: 1)
      - message: optional string
      - signature: RSA signature (base64) — verified if OTA_PUBLIC_KEY_PATH is set
    """

    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="Upload OTA bundle",
        description="Upload a new web bundle for OTA distribution. Admin only.",
        tags=["Updates"],
    )
    def post(self, request):
        bundle_file = request.FILES.get("file")
        if not bundle_file:
            return Response(
                {"error": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate it's a zip
        if not bundle_file.name.endswith(".zip"):
            return Response(
                {"error": "File must be a .zip archive"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        strategy = request.data.get("strategy", "notify")
        if strategy not in ("silent", "notify"):
            strategy = "notify"

        platform = request.data.get("platform", "all")
        if platform not in ("all", "android", "ios"):
            platform = "all"

        try:
            min_app_version = int(request.data.get("min_app_version", 1))
        except (ValueError, TypeError):
            min_app_version = 1

        message = request.data.get("message", "")
        signature = request.data.get("signature", "")

        # Compute checksum of uploaded file
        sha = hashlib.sha256()
        bundle_file.seek(0)
        for chunk in bundle_file.chunks(8192):
            sha.update(chunk)
        bundle_file.seek(0)
        checksum = sha.hexdigest()

        # Verify signature if provided and public key is configured
        if signature and _get_public_key():
            if not _verify_signature(checksum, signature):
                return Response(
                    {"error": "Invalid bundle signature"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif _get_public_key() and not signature:
            # Public key configured but no signature provided — reject
            return Response(
                {"error": "Bundle signature required (code signing is enabled)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create bundle — bundle_id auto-generated, checksum pre-computed
        bundle = AppBundle(
            strategy=strategy,
            platform=platform,
            min_app_version=min_app_version,
            message=message,
            signature=signature,
            checksum=checksum,
            bundle_file=bundle_file,
            is_active=True,
        )
        bundle.save()

        return Response(
            {
                "bundle_id": bundle.bundle_id,
                "checksum": bundle.checksum,
                "url": bundle.bundle_file.url,
                "strategy": bundle.strategy,
                "platform": bundle.platform,
                "signed": bool(signature),
                "created_at": bundle.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )
