import os
import io
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageOps
from config import settings

logger = logging.getLogger("woodturnery.storage")

class R2StorageClient:
    def __init__(self):
        self.s3_client = None
        self._init_client()

    def _init_client(self):
        if settings.is_r2_ready:
            try:
                import boto3
                endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=endpoint_url,
                    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                    region_name="auto"
                )
                logger.info("Cloudflare R2 storage client successfully initialized.")
            except Exception as e:
                logger.warning(f"Could not initialize Cloudflare R2 client ({e}). Local storage will be used.")
                self.s3_client = None
        else:
            logger.info("Cloudflare R2 placeholder credentials detected. Operating in local asset storage mode.")

    def compress_image(self, file_bytes: bytes, max_dimension: int = 1600, quality: int = 82) -> Tuple[bytes, str, Dict[str, Any]]:
        """
        Compresses an image, standardizing to high-quality progressive JPEG,
        orienting via EXIF, and resizing down if exceeding max_dimension.
        Returns: (compressed_bytes, content_type, stats_dict)
        """
        orig_size = len(file_bytes)
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img = ImageOps.exif_transpose(img)

            # Convert RGBA/P to RGB for JPEG
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[3])
                else:
                    rgba = img.convert("RGBA")
                    background.paste(rgba, mask=rgba.split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if exceeding max dimension while maintaining aspect ratio
            w, h = img.size
            if max(w, h) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG", quality=quality, optimize=True, progressive=True)
            compressed_bytes = out_buf.getvalue()
            comp_size = len(compressed_bytes)
            reduction = ((orig_size - comp_size) / orig_size) * 100 if orig_size > 0 else 0.0

            stats = {
                "originalBytes": orig_size,
                "compressedBytes": comp_size,
                "reductionPercent": round(reduction, 1),
                "width": img.width,
                "height": img.height,
                "format": "JPEG"
            }
            logger.info(f"Image compressed: {orig_size/1024:.1f}KB -> {comp_size/1024:.1f}KB ({reduction:.1f}% reduction)")
            return compressed_bytes, "image/jpeg", stats
        except Exception as e:
            logger.warning(f"Image compression failed ({e}), using original bytes.")
            return file_bytes, "image/jpeg", {
                "originalBytes": orig_size,
                "compressedBytes": orig_size,
                "reductionPercent": 0.0,
                "format": "original"
            }

    def upload_file(self, file_bytes: bytes, filename: str, content_type: str = "image/jpeg", auto_compress: bool = True) -> Tuple[str, str, Dict[str, Any]]:
        """
        Compresses image and uploads to Cloudflare R2 if configured, and caches locally.
        Returns: (file_url, storage_provider, compression_stats)
        """
        # Standardize extension to .jpg
        base, ext = os.path.splitext(filename)
        clean_ext = ext.lower()
        if clean_ext in [".jpg", ".jpeg", ".png", ".webp", ""]:
            filename = f"{base}.jpg"

        # Compress image
        stats = {}
        if auto_compress:
            file_bytes, content_type, stats = self.compress_image(file_bytes)

        # Cloudflare R2 upload
        if self.s3_client and settings.is_r2_ready:
            try:
                self.s3_client.put_object(
                    Bucket=settings.R2_BUCKET_NAME,
                    Key=filename,
                    Body=file_bytes,
                    ContentType=content_type
                )
                # Local cache copy in backend/uploads and frontend assets if present
                backend_uploads = Path(__file__).resolve().parent / "uploads"
                backend_uploads.mkdir(parents=True, exist_ok=True)
                with open(backend_uploads / filename, "wb") as f:
                    f.write(file_bytes)

                frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "src" / "assets" / "products"
                if frontend_dir.parent.exists():
                    frontend_dir.mkdir(parents=True, exist_ok=True)
                    with open(frontend_dir / filename, "wb") as f:
                        f.write(file_bytes)

                public_url = f"http://127.0.0.1:8000/api/images/{filename}"
                logger.info(f"File uploaded to Cloudflare R2 & cached locally: {filename}")
                return public_url, "cloudflare_r2", stats
            except Exception as e:
                logger.error(f"Failed to upload to Cloudflare R2 ({e}), falling back to local storage.")

        # Local fallback
        backend_uploads = Path(__file__).resolve().parent / "uploads"
        backend_uploads.mkdir(parents=True, exist_ok=True)
        dest_path = backend_uploads / filename
        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "src" / "assets" / "products"
        if frontend_dir.parent.exists():
            frontend_dir.mkdir(parents=True, exist_ok=True)
            with open(frontend_dir / filename, "wb") as f:
                f.write(file_bytes)

        local_url = f"assets/products/{filename}"
        logger.info(f"File saved to local assets: {local_url}")
        return local_url, "local_assets", stats

storage_client = R2StorageClient()

