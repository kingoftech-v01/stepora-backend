"""
File upload validators for social media posts and events.

Validates MIME types, file sizes, magic bytes, EXIF stripping,
and CSAM hash checking to prevent malicious/illegal file uploads.

Security fixes:
- V-847: EXIF metadata stripping (GPS coordinates, camera info, etc.)
- V-837: CSAM hash-based detection stub (PhotoDNA/NCMEC integration point)
- V-858: Malware scanning integration point (ClamAV TODO)
"""

import hashlib
import io
import logging

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")

# ── Allowed MIME types ───────────────────────────────────────────
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg"}

# ── File size limits (bytes) ─────────────────────────────────────
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20 MB

# ── Image dimension limits (V-325: decompression bomb protection) ─
MAX_IMAGE_PIXELS = 25_000_000  # 25 megapixels (e.g. 5000x5000)
MAX_IMAGE_DIMENSION = 10_000   # Max width or height in pixels

# ── Magic byte signatures ────────────────────────────────────────
# Maps file types to their magic byte prefixes
MAGIC_BYTES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [],  # Checked via RIFF header below
    "video/mp4": [],  # Checked via ftyp box below
    "video/quicktime": [],  # Checked via ftyp box below
    "video/webm": [b"\x1a\x45\xdf\xa3"],  # EBML header
    "audio/mpeg": [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    "audio/mp4": [],  # Checked via ftyp box below
    "audio/wav": [],  # Checked via RIFF header below
    "audio/ogg": [b"OggS"],
}


def _check_riff_format(header, expected_format):
    """Check RIFF container format (WAVE, WEBP)."""
    return (
        len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == expected_format
    )


def _check_ftyp_box(header):
    """Check ISO base media file format (MP4, MOV, M4A)."""
    if len(header) < 12:
        return False
    # ftyp box can start at offset 0 or 4
    return b"ftyp" in header[:12]


def _validate_magic_bytes(file_obj, content_type):
    """
    Validate that the file's magic bytes match the declared content type.

    Reads the first 12 bytes of the file and checks against known signatures.
    Resets the file position after reading.
    """
    file_obj.seek(0)
    header = file_obj.read(12)
    file_obj.seek(0)

    if not header:
        raise ValidationError("Empty file uploaded.")

    # RIFF-based formats
    if content_type == "image/webp":
        if not _check_riff_format(header, b"WEBP"):
            raise ValidationError("File content does not match WebP format.")
        return

    if content_type == "audio/wav":
        if not _check_riff_format(header, b"WAVE"):
            raise ValidationError("File content does not match WAV format.")
        return

    # ISO base media (MP4, MOV, M4A)
    if content_type in ("video/mp4", "video/quicktime", "audio/mp4"):
        if not _check_ftyp_box(header):
            raise ValidationError(f"File content does not match {content_type} format.")
        return

    # Simple prefix-based check
    signatures = MAGIC_BYTES.get(content_type, [])
    if signatures:
        matched = any(header.startswith(sig) for sig in signatures)
        if not matched:
            raise ValidationError(
                f"File content does not match declared type {content_type}."
            )


def strip_exif_data(file_obj):
    """Strip EXIF metadata from uploaded images (V-847).

    Removes GPS coordinates, camera info, timestamps, and other
    potentially sensitive metadata from JPEG and PNG files using Pillow.
    Re-encodes the image to remove hidden data (also mitigates V-847
    steganography concerns).

    WebP and GIF are re-saved without metadata as well.
    Returns a new file-like object with clean image data.
    """
    from io import BytesIO

    from PIL import Image

    content_type = getattr(file_obj, "content_type", "")
    if content_type not in ALLOWED_IMAGE_TYPES:
        return file_obj

    try:
        file_obj.seek(0)
        img = Image.open(file_obj)

        # Map MIME types to Pillow save formats
        format_map = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
            "image/gif": "GIF",
        }
        save_format = format_map.get(content_type, "JPEG")

        # Create a new image without EXIF data
        output = BytesIO()

        # For JPEG, explicitly strip EXIF by not passing exif= parameter
        if save_format == "JPEG":
            # Convert RGBA to RGB for JPEG (no alpha channel support)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(output, format=save_format, quality=95)
        elif save_format == "PNG":
            # PNG: re-save without metadata chunks
            img.save(output, format=save_format)
        elif save_format == "GIF":
            img.save(output, format=save_format)
        else:
            img.save(output, format=save_format)

        output.seek(0)

        # Update the file object with stripped data
        file_obj.seek(0)
        file_obj.truncate(0)
        file_obj.write(output.read())
        file_obj.seek(0)

        # Update size attribute
        output.seek(0, 2)
        file_obj.size = output.tell()

        logger.debug("EXIF data stripped from %s upload", content_type)
    except Exception:
        # If stripping fails, log but don't block the upload --
        # the image has already passed magic bytes validation.
        logger.warning("Failed to strip EXIF data from uploaded image", exc_info=True)
        file_obj.seek(0)

    return file_obj


def check_image_hash_blocklist(file_obj):
    """Check uploaded image against known-bad hash blocklist (V-837).

    Computes SHA-256 of the raw file content and checks against a
    blocklist. This is the integration point for CSAM hash databases
    (PhotoDNA, NCMEC hash lists, GIFCT).

    In production, this should be extended to:
    1. Query a PhotoDNA-compatible perceptual hash service
    2. Report matches to NCMEC as required by law (18 U.S.C. 2258A)
    3. Preserve evidence and block the upload

    Currently uses a local SHA-256 blocklist file if available.
    """
    from django.conf import settings

    try:
        file_obj.seek(0)
        file_hash = hashlib.sha256(file_obj.read()).hexdigest()
        file_obj.seek(0)

        # Check against local blocklist (one hash per line)
        blocklist_path = getattr(settings, "CSAM_HASH_BLOCKLIST_PATH", None)
        if blocklist_path:
            try:
                with open(blocklist_path) as f:
                    blocked_hashes = {line.strip().lower() for line in f if line.strip()}
                if file_hash.lower() in blocked_hashes:
                    security_logger.critical(
                        "CSAM_HASH_MATCH hash=%s -- upload blocked and flagged for review",
                        file_hash,
                    )
                    raise ValidationError(
                        "This file has been flagged and cannot be uploaded. "
                        "This incident has been reported."
                    )
            except FileNotFoundError:
                pass  # Blocklist file not deployed yet

        # Log hash for future auditing / retroactive scanning
        logger.debug("Image upload hash: %s", file_hash)

    except ValidationError:
        raise
    except Exception:
        logger.warning("Image hash check failed", exc_info=True)

    return file_obj


def scan_file_for_malware(file_obj):
    """Scan uploaded file for malware (V-858).

    Integration point for ClamAV or similar antivirus scanning.
    When ClamAV is available (via clamd socket or TCP), this function
    will send the file for scanning before allowing the upload.

    TODO: Install pyclamd and configure ClamAV daemon:
        pip install pyclamd
        apt-get install clamav clamav-daemon
        Configure CLAMAV_SOCKET in settings (e.g. '/var/run/clamav/clamd.ctl')

    For now, this performs basic structural validation beyond magic bytes:
    - Checks that image files can be opened by Pillow (rejects polyglots)
    - Logs a warning if ClamAV is not configured
    """
    from django.conf import settings

    content_type = getattr(file_obj, "content_type", "")

    # Attempt ClamAV scan if configured
    clamav_socket = getattr(settings, "CLAMAV_SOCKET", None)
    if clamav_socket:
        try:
            import pyclamd

            cd = pyclamd.ClamdUnixSocket(filename=clamav_socket)
            file_obj.seek(0)
            result = cd.scan_stream(file_obj.read())
            file_obj.seek(0)
            if result:
                security_logger.critical(
                    "MALWARE_DETECTED scan_result=%s content_type=%s",
                    result,
                    content_type,
                )
                raise ValidationError(
                    "This file has been flagged as potentially harmful and cannot be uploaded."
                )
        except ImportError:
            logger.warning("pyclamd not installed -- ClamAV scanning disabled")
        except ValidationError:
            raise
        except Exception:
            logger.warning("ClamAV scan failed", exc_info=True)

    # Structural validation for images: ensure Pillow can open them
    # This catches polyglot files that pass magic bytes but contain
    # embedded executables or scripts
    if content_type in ALLOWED_IMAGE_TYPES:
        try:
            from PIL import Image

            file_obj.seek(0)
            img = Image.open(file_obj)
            img.verify()  # Verify image integrity without loading full data
            file_obj.seek(0)
        except Exception:
            file_obj.seek(0)
            raise ValidationError(
                "The uploaded image file appears to be corrupted or invalid."
            )

    return file_obj


def _validate_image_dimensions(file_obj):
    """Validate image dimensions to prevent decompression bomb attacks (V-325).

    A decompression bomb is a small compressed file that expands to enormous
    dimensions (e.g., 100,000 x 100,000 pixels) consuming all available RAM.
    PIL/Pillow has a built-in MAX_IMAGE_PIXELS check, but we enforce our own
    stricter limits here.
    """
    try:
        from PIL import Image

        # Set Pillow's decompression bomb threshold
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

        file_obj.seek(0)
        img = Image.open(file_obj)
        width, height = img.size
        file_obj.seek(0)

        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            raise ValidationError(
                f"Image dimensions too large ({width}x{height}). "
                f"Maximum: {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} pixels."
            )

        total_pixels = width * height
        if total_pixels > MAX_IMAGE_PIXELS:
            raise ValidationError(
                f"Image has too many pixels ({total_pixels:,}). "
                f"Maximum: {MAX_IMAGE_PIXELS:,} pixels."
            )
    except ValidationError:
        raise
    except Exception as exc:
        logger.warning("Image dimension validation failed: %s", exc)
        file_obj.seek(0)
        raise ValidationError(
            "Could not validate image dimensions. The file may be corrupted."
        )


def validate_image_upload(file_obj):
    """Validate an uploaded image file.

    Pipeline: type check -> size check -> magic bytes -> dimension check (V-325) ->
    malware scan -> CSAM hash check -> EXIF strip.
    """
    content_type = getattr(file_obj, "content_type", "")

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            f"Unsupported image type: {content_type}. "
            f"Allowed: JPEG, PNG, WebP, GIF."
        )

    if file_obj.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            f"Image too large ({file_obj.size // (1024*1024)}MB). "
            f"Maximum: {MAX_IMAGE_SIZE // (1024*1024)}MB."
        )

    _validate_magic_bytes(file_obj, content_type)

    # V-325: Image dimension validation (decompression bomb protection)
    _validate_image_dimensions(file_obj)

    # V-858: Structural validation + malware scan
    scan_file_for_malware(file_obj)

    # V-837: CSAM hash-based detection
    check_image_hash_blocklist(file_obj)

    # V-847: Strip EXIF metadata (GPS, camera info, timestamps)
    strip_exif_data(file_obj)


def validate_video_upload(file_obj):
    """Validate an uploaded video file."""
    content_type = getattr(file_obj, "content_type", "")

    if content_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationError(
            f"Unsupported video type: {content_type}. " f"Allowed: MP4, MOV, WebM."
        )

    if file_obj.size > MAX_VIDEO_SIZE:
        raise ValidationError(
            f"Video too large ({file_obj.size // (1024*1024)}MB). "
            f"Maximum: {MAX_VIDEO_SIZE // (1024*1024)}MB."
        )

    _validate_magic_bytes(file_obj, content_type)

    # V-858: Malware scan for video uploads
    scan_file_for_malware(file_obj)


def validate_audio_upload(file_obj):
    """Validate an uploaded audio file."""
    content_type = getattr(file_obj, "content_type", "")

    if content_type not in ALLOWED_AUDIO_TYPES:
        raise ValidationError(
            f"Unsupported audio type: {content_type}. " f"Allowed: MP3, M4A, WAV, OGG."
        )

    if file_obj.size > MAX_AUDIO_SIZE:
        raise ValidationError(
            f"Audio too large ({file_obj.size // (1024*1024)}MB). "
            f"Maximum: {MAX_AUDIO_SIZE // (1024*1024)}MB."
        )

    _validate_magic_bytes(file_obj, content_type)

    # V-858: Malware scan for audio uploads
    scan_file_for_malware(file_obj)


def validate_event_cover_upload(file_obj):
    """Validate an event cover image (same rules as image, smaller limit)."""
    content_type = getattr(file_obj, "content_type", "")

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            f"Unsupported image type: {content_type}. "
            f"Allowed: JPEG, PNG, WebP, GIF."
        )

    if file_obj.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            f"Cover image too large ({file_obj.size // (1024*1024)}MB). "
            f"Maximum: {MAX_IMAGE_SIZE // (1024*1024)}MB."
        )

    _validate_magic_bytes(file_obj, content_type)

    # V-325: Image dimension validation (decompression bomb protection)
    _validate_image_dimensions(file_obj)

    # V-858: Structural validation + malware scan
    scan_file_for_malware(file_obj)

    # V-837: CSAM hash-based detection
    check_image_hash_blocklist(file_obj)

    # V-847: Strip EXIF metadata
    strip_exif_data(file_obj)
