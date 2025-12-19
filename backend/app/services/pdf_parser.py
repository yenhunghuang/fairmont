"""PDF parser service with Gemini AI integration."""

import logging
import fitz  # PyMuPDF
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

from ..models import BOQItem, SourceDocument
from ..utils import ErrorCode, raise_error
from ..config import settings

logger = logging.getLogger(__name__)


class PDFParserService:
    """Service for parsing PDFs and extracting BOQ items using Gemini AI."""

    def __init__(self):
        """Initialize PDF parser service."""
        try:
            import google.generativeai as genai
            self.genai = genai
            if settings.gemini_api_key:
                genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        except ImportError:
            logger.warning("google-generativeai not installed")
            self.genai = None
            self.model = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.genai = None
            self.model = None

    def validate_pdf(self, file_path: str) -> tuple[int, bool]:
        """
        Validate PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (page_count, is_valid)

        Raises:
            APIError: If PDF is invalid
        """
        try:
            doc = fitz.open(file_path)
            page_count = doc.page_count
            doc.close()

            if page_count == 0:
                raise_error(ErrorCode.PDF_PARSING_FAILED, "PDF 文件為空，無法解析")

            return page_count, True
        except fitz.FileError:
            raise_error(ErrorCode.PDF_CORRUPTED, "PDF 檔案損毀，無法開啟")
        except Exception as e:
            if "encrypted" in str(e).lower():
                raise_error(ErrorCode.PDF_PASSWORD_PROTECTED, "PDF 檔案受密碼保護")
            logger.error(f"PDF validation failed: {e}")
            raise_error(ErrorCode.PDF_PARSING_FAILED, f"PDF 驗證失敗：{str(e)}")

    def extract_text_from_pdf(self, file_path: str, max_pages: Optional[int] = None) -> str:
        """
        Extract text from PDF.

        Args:
            file_path: Path to PDF file
            max_pages: Maximum pages to extract (None for all)

        Returns:
            Extracted text content

        Raises:
            APIError: If extraction fails
        """
        try:
            doc = fitz.open(file_path)
            text = ""

            for page_num in range(min(doc.page_count, max_pages or doc.page_count)):
                page = doc[page_num]
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page.get_text()

            doc.close()
            return text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise_error(ErrorCode.PDF_EXTRACT_FAILED, "文本提取失敗")

    async def parse_boq_with_gemini(
        self,
        file_path: str,
        document_id: str,
        extract_images: bool = True,
        target_categories: Optional[List[str]] = None,
    ) -> tuple[List[BOQItem], List[str]]:
        """
        Parse BOQ from PDF using Gemini AI.

        Args:
            file_path: Path to PDF file
            document_id: Source document ID
            extract_images: Whether to extract images
            target_categories: Target categories to filter

        Returns:
            Tuple of (BOQ items list, image paths list)

        Raises:
            APIError: If parsing fails
        """
        if not self.model:
            raise_error(
                ErrorCode.GEMINI_API_ERROR,
                "Gemini API 未配置，無法解析 PDF",
            )

        try:
            # Extract text first
            text_content = self.extract_text_from_pdf(file_path)

            # Prepare prompt for Gemini
            prompt = self._create_boq_extraction_prompt(
                text_content,
                target_categories=target_categories,
            )

            # Call Gemini API
            logger.info(f"Calling Gemini API for document {document_id}")
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
            )

            # Parse response
            boq_items = self._parse_gemini_response(response, document_id)
            logger.info(f"Extracted {len(boq_items)} BOQ items from {document_id}")

            # Extract images if requested
            image_paths = []
            if extract_images:
                image_paths = await self.extract_images_async(file_path, document_id)

            return boq_items, image_paths

        except Exception as e:
            if "find api key" in str(e).lower() or "api key" in str(e).lower():
                raise_error(
                    ErrorCode.GEMINI_API_ERROR,
                    "Gemini API Key 未設定或無效",
                )
            if "quota" in str(e).lower():
                raise_error(
                    ErrorCode.GEMINI_QUOTA_EXCEEDED,
                    "Gemini API 配額已用盡",
                )
            if "rate" in str(e).lower():
                raise_error(
                    ErrorCode.GEMINI_RATE_LIMIT,
                    "Gemini API 速率限制，請稍後重試",
                )
            logger.error(f"Gemini parsing failed: {e}")
            raise_error(ErrorCode.GEMINI_API_ERROR, f"Gemini 解析失敗：{str(e)}")

    def _create_boq_extraction_prompt(
        self,
        pdf_text: str,
        target_categories: Optional[List[str]] = None,
    ) -> str:
        """Create prompt for Gemini to extract BOQ items."""
        categories_str = (
            f"只關注這些類別：{', '.join(target_categories)}"
            if target_categories
            else "提取所有家具和物料項目"
        )

        prompt = f"""
請分析以下 PDF 內容，提取出家具報價單（BOQ）中的所有項目。

{categories_str}

針對每個項目，請按照以下 JSON 格式提取：

```json
[
  {{
    "item_no": "項目編號",
    "description": "項目描述",
    "dimension": "尺寸（WxDxH mm）",
    "qty": 數量或 null,
    "uom": "單位（如：ea, m, set）",
    "note": "備註或說明",
    "location": "位置/區域",
    "materials_specs": "材料/規格說明"
  }}
]
```

PDF 內容：
{pdf_text}

請只返回 JSON 數組，不要包含其他文本。如果無法提取有效項目，返回空數組 []。
"""
        return prompt

    def _parse_gemini_response(self, response: Any, document_id: str) -> List[BOQItem]:
        """Parse Gemini response and create BOQItem objects."""
        try:
            response_text = response.text
            # Extract JSON from response
            json_start = response_text.find("[")
            json_end = response_text.rfind("]") + 1

            if json_start == -1 or json_end <= json_start:
                logger.warning(f"No JSON found in Gemini response for {document_id}")
                return []

            json_str = response_text[json_start:json_end]
            items_data = json.loads(json_str)

            boq_items = []
            for idx, item_data in enumerate(items_data, 1):
                try:
                    boq_item = BOQItem(
                        no=idx,
                        item_no=item_data.get("item_no", f"ITEM-{idx}"),
                        description=item_data.get("description", ""),
                        dimension=item_data.get("dimension"),
                        qty=self._parse_qty(item_data.get("qty")),
                        uom=item_data.get("uom"),
                        note=item_data.get("note"),
                        location=item_data.get("location"),
                        materials_specs=item_data.get("materials_specs"),
                        source_document_id=document_id,
                        source_type="boq",
                    )
                    boq_items.append(boq_item)
                except Exception as e:
                    logger.warning(f"Failed to parse item {idx}: {e}")

            return boq_items
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return []

    @staticmethod
    def _parse_qty(qty_value: Any) -> Optional[float]:
        """Parse quantity value from various formats."""
        if qty_value is None:
            return None
        if isinstance(qty_value, (int, float)):
            return float(qty_value)
        if isinstance(qty_value, str):
            try:
                return float(qty_value)
            except ValueError:
                return None
        return None

    async def extract_images_async(
        self,
        file_path: str,
        document_id: str,
    ) -> List[str]:
        """Extract images asynchronously."""
        return await asyncio.to_thread(
            self.extract_images,
            file_path,
            document_id,
        )

    def extract_images(
        self,
        file_path: str,
        document_id: str,
    ) -> List[str]:
        """Extract images from PDF."""
        from .image_extractor import ImageExtractorService

        extractor = ImageExtractorService()
        return extractor.extract_images(file_path, document_id)


# Global parser instance
_parser_instance: Optional[PDFParserService] = None


def get_pdf_parser() -> PDFParserService:
    """Get or create PDF parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = PDFParserService()
    return _parser_instance
