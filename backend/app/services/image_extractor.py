"""Image extraction service using PyMuPDF with page rendering approach.

Updated to support Base64 output for embedding images in Excel (完全比照惠而蒙格式).
"""

import logging
import fitz  # PyMuPDF
import base64
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import uuid
import io

from PIL import Image

from ..models import ExtractedImage
from ..utils import ErrorCode, raise_error, FileManager
from ..config import settings

logger = logging.getLogger(__name__)

# 過濾設定：忽略過小的圖片區域
MIN_IMAGE_WIDTH = 50  # 像素
MIN_IMAGE_HEIGHT = 50  # 像素
MIN_ASPECT_RATIO = 0.2  # 避免過窄的長條
MAX_ASPECT_RATIO = 5.0  # 避免過寬的長條


class ImageExtractorService:
    """Service for extracting images from PDF files using page rendering."""

    def __init__(self):
        """Initialize image extractor service."""
        # 使用 settings 中已處理好的絕對路徑
        self.file_manager = FileManager(
            temp_dir=settings.temp_dir_path,
            images_dir=settings.extracted_images_dir_path,
        )
        logger.info(f"Image extractor initialized with images_dir: {self.file_manager.images_dir}")

    def extract_images(self, file_path: str, document_id: str) -> List[str]:
        """
        Extract images from PDF file using page rendering approach.

        This method renders each page and extracts image regions based on
        their bounding boxes, which avoids the stripe/tile problem that
        occurs with direct xref extraction.

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

                # 方法一：使用頁面渲染 + 圖片區域裁剪（推薦）
                page_images = self._extract_images_by_rendering(
                    doc, page, page_num, document_id
                )

                for img_data in page_images:
                    try:
                        image_id = str(uuid.uuid4())
                        filename = f"img_{document_id}_{page_num + 1}_{image_count}.png"

                        # 儲存圖片
                        image_path = self.file_manager.save_extracted_image(
                            img_data["bytes"],
                            filename,
                            document_id=document_id,
                        )

                        # 建立 ExtractedImage 模型
                        extracted_image = ExtractedImage(
                            id=image_id,
                            filename=filename,
                            file_path=image_path,
                            format="png",
                            width=img_data["width"],
                            height=img_data["height"],
                            file_size=len(img_data["bytes"]),
                            source_document_id=document_id,
                            source_page=page_num + 1,
                        )

                        extracted_image_ids.append(extracted_image.id)
                        image_count += 1
                        logger.info(
                            f"Extracted image: {filename} ({img_data['width']}x{img_data['height']}px)"
                        )

                    except Exception as e:
                        logger.warning(
                            f"Failed to save image from page {page_num + 1}: {e}"
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

    def extract_images_as_base64(
        self,
        file_path: str,
        document_id: str,
        max_width: int = 400,
        max_height: int = 300,
    ) -> List[Dict[str, any]]:
        """
        Extract images from PDF and return as Base64 encoded strings.

        This method is optimized for embedding images directly into Excel files
        per the Fairmont format requirements.

        Args:
            file_path: Path to PDF file
            document_id: Source document ID
            max_width: Maximum image width (for compression)
            max_height: Maximum image height (for compression)

        Returns:
            List of dicts containing:
                - base64: Base64 encoded image string
                - width: Image width in pixels
                - height: Image height in pixels
                - page: Source page number (1-indexed)
                - format: Image format (png/jpeg)

        Raises:
            APIError: If extraction fails
        """
        extracted_images = []

        try:
            doc = fitz.open(file_path)
            image_count = 0

            for page_num in range(doc.page_count):
                page = doc[page_num]

                # 使用頁面渲染 + 圖片區域裁剪
                page_images = self._extract_images_by_rendering(
                    doc, page, page_num, document_id
                )

                for img_data in page_images:
                    try:
                        # 轉換為 Base64
                        base64_data = self._convert_to_base64(
                            img_data["bytes"],
                            max_width=max_width,
                            max_height=max_height,
                        )

                        extracted_images.append({
                            "base64": base64_data,
                            "width": img_data["width"],
                            "height": img_data["height"],
                            "page": page_num + 1,
                            "format": "png",
                            "index": image_count,
                        })

                        image_count += 1
                        logger.info(
                            f"Extracted image as Base64: page {page_num + 1}, "
                            f"{img_data['width']}x{img_data['height']}px"
                        )

                    except Exception as e:
                        logger.warning(
                            f"Failed to convert image to Base64 from page {page_num + 1}: {e}"
                        )

            doc.close()
            logger.info(f"Extracted {image_count} images as Base64 from {document_id}")
            return extracted_images

        except Exception as e:
            logger.error(f"Image extraction (Base64) failed for {file_path}: {e}")
            raise_error(
                ErrorCode.PDF_EXTRACT_FAILED,
                f"圖片提取失敗：{str(e)}",
            )

    def extract_images_with_bytes(
        self,
        file_path: str,
        document_id: str,
    ) -> List[Dict]:
        """
        Extract all images with raw bytes for Gemini Vision matching.

        This method returns raw image bytes along with metadata for use
        with Gemini's multimodal vision API.

        Args:
            file_path: Path to PDF file
            document_id: Source document ID

        Returns:
            List of dicts with: {bytes, width, height, page, index}

        Raises:
            APIError: If extraction fails
        """
        extracted = []
        image_count = 0

        try:
            doc = fitz.open(file_path)

            for page_num in range(doc.page_count):
                page = doc[page_num]
                page_images = self._extract_images_by_rendering(
                    doc, page, page_num, document_id
                )

                for img_data in page_images:
                    extracted.append({
                        "bytes": img_data["bytes"],
                        "width": img_data["width"],
                        "height": img_data["height"],
                        "page": page_num + 1,
                        "index": image_count,
                    })
                    image_count += 1

            doc.close()
            logger.info(f"Extracted {image_count} images with bytes from {document_id}")
            return extracted

        except Exception as e:
            logger.error(f"Image extraction (with bytes) failed for {file_path}: {e}")
            raise_error(
                ErrorCode.PDF_EXTRACT_FAILED,
                f"圖片提取失敗：{str(e)}",
            )

    def _convert_to_base64(
        self,
        image_bytes: bytes,
        max_width: int = 400,
        max_height: int = 300,
        quality: int = 85,
    ) -> str:
        """
        Convert image bytes to Base64 encoded string with optional resizing.

        Args:
            image_bytes: Raw image bytes
            max_width: Maximum width (resize if larger)
            max_height: Maximum height (resize if larger)
            quality: JPEG quality if converting

        Returns:
            Base64 encoded image string (without data URI prefix)
        """
        try:
            # Open image
            img = Image.open(io.BytesIO(image_bytes))

            # Convert RGBA to RGB if needed
            if img.mode == "RGBA":
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background

            # Resize if too large (maintain aspect ratio)
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            # Save to bytes
            output = io.BytesIO()
            img.save(output, format="PNG", optimize=True)
            output.seek(0)

            # Encode to Base64
            base64_str = base64.b64encode(output.read()).decode("utf-8")
            return base64_str

        except Exception as e:
            logger.error(f"Failed to convert image to Base64: {e}")
            raise

    @staticmethod
    def image_path_to_base64(image_path: str) -> Optional[str]:
        """
        Convert an existing image file to Base64 encoded string.

        Args:
            image_path: Path to image file

        Returns:
            Base64 encoded image string, or None if failed
        """
        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning(f"Image file not found: {image_path}")
                return None

            with open(path, "rb") as f:
                image_bytes = f.read()

            base64_str = base64.b64encode(image_bytes).decode("utf-8")
            return base64_str

        except Exception as e:
            logger.error(f"Failed to convert image file to Base64: {e}")
            return None

    @staticmethod
    def base64_to_bytes(base64_str: str) -> bytes:
        """
        Convert Base64 string to image bytes.

        Args:
            base64_str: Base64 encoded image string

        Returns:
            Raw image bytes
        """
        # Remove data URI prefix if present
        if base64_str.startswith("data:"):
            base64_str = base64_str.split(",", 1)[1]

        return base64.b64decode(base64_str)

    def _extract_images_by_rendering(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_num: int,
        document_id: str,
    ) -> List[dict]:
        """
        Extract images by rendering the page and cropping image regions.

        This approach:
        1. Gets all image bounding boxes on the page
        2. Merges overlapping/adjacent boxes (handles striped images)
        3. Renders the page at high resolution
        4. Crops each merged region

        Args:
            doc: PyMuPDF document
            page: Current page
            page_num: Page number (0-indexed)
            document_id: Document ID

        Returns:
            List of dicts with image bytes and dimensions
        """
        extracted = []

        # 獲取頁面上所有圖片的邊界框
        image_rects = self._get_merged_image_rects(page)

        if not image_rects:
            return extracted

        # 以較高解析度渲染頁面（2x 縮放）
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # 轉換為 PIL Image
        page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        for rect_idx, rect in enumerate(image_rects):
            try:
                # 將 PDF 座標轉換為像素座標
                x0 = int(rect.x0 * zoom)
                y0 = int(rect.y0 * zoom)
                x1 = int(rect.x1 * zoom)
                y1 = int(rect.y1 * zoom)

                # 確保座標在有效範圍內
                x0 = max(0, x0)
                y0 = max(0, y0)
                x1 = min(pix.width, x1)
                y1 = min(pix.height, y1)

                width = x1 - x0
                height = y1 - y0

                # 過濾過小或異常比例的圖片
                if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                    continue

                aspect_ratio = width / height if height > 0 else 0
                if aspect_ratio < MIN_ASPECT_RATIO or aspect_ratio > MAX_ASPECT_RATIO:
                    logger.debug(
                        f"Skipping image with unusual aspect ratio: {aspect_ratio:.2f}"
                    )
                    continue

                # 裁剪圖片區域
                cropped = page_image.crop((x0, y0, x1, y1))

                # 轉換為 bytes
                output = io.BytesIO()
                cropped.save(output, format="PNG", optimize=True)
                img_bytes = output.getvalue()

                extracted.append({
                    "bytes": img_bytes,
                    "width": width,
                    "height": height,
                })

            except Exception as e:
                logger.warning(f"Failed to crop image region {rect_idx}: {e}")

        return extracted

    def _get_merged_image_rects(self, page: fitz.Page) -> List[fitz.Rect]:
        """
        Get merged image rectangles from page.

        Merges overlapping and adjacent image rectangles to handle
        striped/tiled images that were split during PDF creation.

        Args:
            page: PyMuPDF page

        Returns:
            List of merged fitz.Rect objects
        """
        # 獲取所有圖片資訊
        image_list = page.get_images(full=True)

        if not image_list:
            return []

        # 收集所有圖片的邊界框
        all_rects = []
        for img_info in image_list:
            xref = img_info[0]
            try:
                # 獲取圖片在頁面上的位置（可能有多個實例）
                img_rects = page.get_image_rects(xref)
                for rect in img_rects:
                    if rect and not rect.is_empty:
                        all_rects.append(rect)
            except Exception as e:
                logger.debug(f"Could not get rect for xref {xref}: {e}")

        if not all_rects:
            return []

        # 合併重疊或相鄰的矩形
        merged = self._merge_rects(all_rects)

        return merged

    def _merge_rects(
        self,
        rects: List[fitz.Rect],
        tolerance: float = 5.0,
    ) -> List[fitz.Rect]:
        """
        Merge overlapping or adjacent rectangles.

        Uses iterative approach to ensure all adjacent/overlapping
        rectangles are merged, even if not initially adjacent in sorted order.

        Args:
            rects: List of rectangles
            tolerance: Pixel tolerance for considering rects as adjacent

        Returns:
            List of merged rectangles
        """
        if not rects:
            return []

        # 複製矩形列表
        working_rects = [fitz.Rect(r) for r in rects]

        # 迭代合併直到沒有更多變化
        changed = True
        while changed:
            changed = False
            new_rects = []
            used = [False] * len(working_rects)

            for i, rect_i in enumerate(working_rects):
                if used[i]:
                    continue

                current = fitz.Rect(rect_i)
                used[i] = True

                # 嘗試與其他所有矩形合併
                for j, rect_j in enumerate(working_rects):
                    if used[j]:
                        continue

                    # 檢查是否重疊或相鄰
                    expanded_current = fitz.Rect(
                        current.x0 - tolerance,
                        current.y0 - tolerance,
                        current.x1 + tolerance,
                        current.y1 + tolerance,
                    )

                    if expanded_current.intersects(rect_j):
                        # 合併矩形
                        current = current | rect_j  # Union
                        used[j] = True
                        changed = True

                new_rects.append(current)

            working_rects = new_rects

        return working_rects

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
