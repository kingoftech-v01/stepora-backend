"""
File upload validators for social media posts and events.

Validates MIME types, file sizes, and magic bytes to prevent
malicious file uploads.
"""


from django.core.exceptions import ValidationError

# ── Allowed MIME types ───────────────────────────────────────────
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg"}

# ── File size limits (bytes) ─────────────────────────────────────
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20 MB

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


def validate_image_upload(file_obj):
    """Validate an uploaded image file."""
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
