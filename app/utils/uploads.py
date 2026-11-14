"""Validated file uploads to Cloudinary (MIME allow-list, magic bytes, size)."""
import cloudinary.uploader
from flask import current_app

from app.errors import ApiError, ValidationError

_MAGIC = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF",),
}
IMAGE_MIME = ("image/jpeg", "image/png", "image/webp")


def _unsupported(field, detail):
    return ApiError("Unsupported file type", 415, "UNSUPPORTED_MEDIA_TYPE", fields={field: detail})


def validate_upload(file, field="image", allowed_mime=None, max_mb=None):
    """Raise 400/413/415 ApiError if the FileStorage is empty, too large or not an allowed type.

    allowed_mime narrows config ALLOWED_UPLOAD_MIME (it can never widen it).
    """
    if file is None or not file.filename:
        raise ValidationError(fields={field: "file is empty"})
    config_allowed = tuple(current_app.config.get("ALLOWED_UPLOAD_MIME", ()))
    allowed = tuple(m for m in (allowed_mime or config_allowed) if m in config_allowed)
    mime = (file.mimetype or "").lower()
    if mime not in allowed:
        raise _unsupported(field, f"allowed types: {', '.join(allowed)}")

    stream = file.stream
    stream.seek(0)
    head = stream.read(12)
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    limit_mb = max_mb or current_app.config.get("MAX_UPLOAD_MB", 5)
    if size > limit_mb * 1024 * 1024:
        raise ApiError("File too large", 413, "PAYLOAD_TOO_LARGE", fields={field: f"max {limit_mb} MB"})
    if size == 0:
        raise ValidationError(fields={field: "file is empty"})
    signatures = _MAGIC.get(mime, ())
    if signatures and not any(head.startswith(sig) for sig in signatures):
        raise _unsupported(field, "content does not match declared type")
    if mime == "image/webp" and head[8:12] != b"WEBP":
        raise _unsupported(field, "content does not match declared type")


def upload_file(file, folder, field="image", allowed_mime=None):
    """Validate then upload; returns the secure URL. Storage failures -> 502 INTERNAL_ERROR."""
    validate_upload(file, field=field, allowed_mime=allowed_mime)
    try:
        result = cloudinary.uploader.upload(file, folder=folder, resource_type="auto")
    except Exception:
        current_app.logger.exception("File upload to storage failed")
        raise ApiError("File upload failed", 502, "INTERNAL_ERROR")
    url = (result or {}).get("secure_url")
    if not url:
        raise ApiError("File upload failed", 502, "INTERNAL_ERROR")
    return url
