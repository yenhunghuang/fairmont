"""Image extraction service using PyMuPDF."""

import logging
import fitz  # PyMuPDF
from pathlib import Path
from typing import List
import uuid

from ..models import ExtractedImage
from ..utils import ErrorCode, raise_error, FileManager
from ..config import settings

logger = logging.getLogger(__name__)


class ImageExtractorService:
    """Service for extracting images from PDF files."""

    def __init__(self):
        """Initialize image extractor service."""
        self.file_manager = FileManager(
            temp_dir=settings.temp_dir_path,
            images_dir=settings.extracted_images_dir_path,
        )

    def extract_images(self, file_path: str, document_id: str) -> List[str]:
        """
        Extract images from PDF file.

        Args:
            file_path: Path to PDF file
            document_id: Source document ID

        Returns:
            List of extracted image IDs

        Raises:
            APIError: If extraction fails
        """
        extracted_image_ids = []

        try:
            doc = fitz.open(file_path)
            image_count = 0

            for page_num in range(doc.page_count):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for img_index, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        image = doc.extract_image(xref)

                        if not image:
                            continue

                        # Save image to file
                        image_id = str(uuid.uuid4())
                        ext = self._get_image_extension(image["ext"])
                        filename = f"img_{document_id}_{page_num + 1}_{img_index}.{ext}"

                        # Save to disk
                        image_path = self.file_manager.save_extracted_image(
                            image["image"],
                            filename,
                        )

                        # Get image dimensions using PIL
                        from PIL import Image
                        import io

                        img_obj = Image.open(io.BytesIO(image["image"]))
                        width, height = img_obj.size

                        # Create ExtractedImage model
                        extracted_image = ExtractedImage(
                            id=image_id,
                            filename=filename,
                            file_path=image_path,
                            format=ext,
                            width=width,
                            height=height,
                            file_size=len(image["image"]),
                            source_document_id=document_id,
                            source_page=page_num + 1,
                        )

                        extracted_image_ids.append(extracted_image.id)
                        image_count += 1
                        logger.info(
                            f"Extracted image: {filename} ({width}x{height}px)"
                        )

                    except Exception as e:
                        logger.warning(
                            f"Failed to extract image from page {page_num + 1}: {e}"
                        )

            doc.close()
            logger.info(f"Extracted {image_count} images from {document_id}")
            return extracted_image_ids

        except Exception as e:
            logger.error(f"Image extraction failed for {file_path}: {e}")
            raise_error(
                ErrorCode.PDF_EXTRACT_FAILED,
                f"圖片提取失敗：{str(e)}",
            )

    @staticmethod
    def _get_image_extension(ext: str) -> str:
        """Convert image extension to standard format."""
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/bmp": "bmp",
            "image/webp": "webp",
            "jpeg": "jpg",
            "png": "png",
            "gif": "gif",
            "bmp": "bmp",
            "webp": "webp",
        }
        return ext_map.get(ext.lower(), "jpg")

    def get_image_dimensions(self, image_path: str) -> tuple[int, int]:
        """
        Get image dimensions.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (width, height)

        Raises:
            APIError: If unable to get dimensions
        """
        try:
            from PIL import Image

            with Image.open(image_path) as img:
                return img.size
        except Exception as e:
            logger.error(f"Failed to get image dimensions: {e}")
            raise_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                "無法取得圖片尺寸",
            )

    def convert_image_format(
        self,
        image_path: str,
        target_format: str = "jpeg",
    ) -> bytes:
        """
        Convert image to target format.

        Args:
            image_path: Path to image file
            target_format: Target format (jpeg, png, etc.)

        Returns:
            Converted image bytes

        Raises:
            APIError: If conversion fails
        """
        try:
            from PIL import Image
            import io

            with Image.open(image_path) as img:
                # Convert RGBA to RGB if target is JPEG
                if target_format.lower() == "jpeg" and img.mode == "RGBA":
                    img = img.convert("RGB")

                # Save to bytes
                output = io.BytesIO()
                img.save(output, format=target_format.upper())
                return output.getvalue()
        except Exception as e:
            logger.error(f"Image conversion failed: {e}")
            raise_error(
                ErrorCode.PROCESSING_FAILED,
                "圖片轉換失敗",
            )

    def compress_image(
        self,
        image_path: str,
        quality: int = 85,
    ) -> bytes:
        """
        Compress image while maintaining quality.

        Args:
            image_path: Path to image file
            quality: JPEG quality (1-100)

        Returns:
            Compressed image bytes

        Raises:
            APIError: If compression fails
        """
        try:
            from PIL import Image
            import io

            with Image.open(image_path) as img:
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=quality, optimize=True)
                return output.getvalue()
        except Exception as e:
            logger.error(f"Image compression failed: {e}")
            raise_error(
                ErrorCode.PROCESSING_FAILED,
                "圖片壓縮失敗",
            )


# Global extractor instance
_extractor_instance: ImageExtractorService = None


def get_image_extractor() -> ImageExtractorService:
    """Get or create image extractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ImageExtractorService()
    return _extractor_instance
