"""Upload generated images to S3 / Cloudflare R2 and return CDN URLs."""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import PurePosixPath

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — set these as environment variables in production
# ---------------------------------------------------------------------------

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "qtown-assets")
S3_REGION = os.getenv("S3_REGION", "auto")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")  # Set to R2 endpoint for Cloudflare
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "")        # e.g. https://assets.qtown.example.com

# If CDN_BASE_URL is not set, construct a public S3 URL
_USE_CDN = bool(CDN_BASE_URL)


def _build_cdn_url(key: str) -> str:
    """Return the public CDN or S3 URL for the given object key."""
    if _USE_CDN:
        return f"{CDN_BASE_URL.rstrip('/')}/{key}"
    if S3_ENDPOINT_URL:
        return f"{S3_ENDPOINT_URL.rstrip('/')}/{S3_BUCKET}/{key}"
    return f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{key}"


def _get_s3_client() -> "boto3.client":  # type: ignore[type-arg]
    kwargs: dict = {
        "region_name": S3_REGION,
        "aws_access_key_id": AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
        "config": Config(signature_version="s3v4", retries={"max_attempts": 3}),
    }
    if S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


async def upload_image(
    image_bytes: bytes,
    key: str,
    content_type: str = "image/png",
    extra_metadata: dict[str, str] | None = None,
) -> str:
    """Upload *image_bytes* to S3/R2 at *key* and return the public CDN URL.

    Parameters
    ----------
    image_bytes:
        Raw image bytes.
    key:
        Object key (path) in the bucket, e.g. ``npcs/alice/portrait-day42.png``.
    content_type:
        MIME type of the image.
    extra_metadata:
        Optional key-value metadata to attach to the S3 object.

    Returns
    -------
    Public URL of the uploaded asset.
    """
    import asyncio

    metadata: dict[str, str] = extra_metadata or {}

    loop = asyncio.get_event_loop()

    def _upload() -> None:
        client = _get_s3_client()
        client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
            Metadata=metadata,
        )

    await loop.run_in_executor(None, _upload)

    cdn_url = _build_cdn_url(key)
    logger.info("Uploaded %d bytes → s3://%s/%s  CDN: %s", len(image_bytes), S3_BUCKET, key, cdn_url)
    return cdn_url


def build_asset_key(asset_type: str, asset_id: str, filename: str) -> str:
    """Construct a canonical S3 object key.

    Examples
    --------
    >>> build_asset_key("npc-portrait", "alice", "portrait-day042.png")
    'npc-portrait/alice/portrait-day042.png'
    """
    return str(PurePosixPath(asset_type) / asset_id / filename)
