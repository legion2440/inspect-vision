"""Shared bounded multipart decoding for inspection image endpoints."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from fastapi import HTTPException, UploadFile, status

from backend.utils.preprocessing import decode_image


@dataclass(frozen=True, slots=True)
class DecodedUpload:
    payload: bytes
    image: np.ndarray
    media_type: str
    extension: str


def detect_media_type(payload: bytes) -> tuple[str, str]:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if payload.startswith(b"\xff\xd8"):
        return "image/jpeg", "jpg"
    raise ValueError("unsupported image content")


def decode_upload(
    upload: UploadFile,
    *,
    max_bytes: int,
    allowed_media_types: frozenset[str] = frozenset({"image/jpeg", "image/png"}),
) -> DecodedUpload:
    payload = upload.file.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File size exceeds 10MB limit",
        )
    try:
        media_type, extension = detect_media_type(payload)
        if media_type not in allowed_media_types:
            raise ValueError("media type is not accepted by this endpoint")
        image = decode_image(payload)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type",
        ) from None
    return DecodedUpload(
        payload=payload,
        image=image,
        media_type=media_type,
        extension=extension,
    )
