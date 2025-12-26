"""PDF parser service with Gemini AI integration."""

import logging
import fitz  # PyMuPDF
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

from ..models import BOQItem, SourceDocument
from ..utils import ErrorCode, raise_error
from ..config import settings
from .observability import get_observability, TraceMetadata

logger = logging.getLogger(__name__)


# ============================================================
# Default Prompts (Fallback when Skill config unavailable)
# ============================================================

DEFAULT_BOQ_PROMPT_TEMPLATE = """
請分析以下 PDF 內容，提取出家具報價單（BOQ）中的所有項目。

{categories_instruction}

**重要解析原則**：
- 每個規格頁只提取「主要項目」，忽略附屬的面料、配件、五金等
- 主要項目判斷依據：
  * 有獨立的 ITEM NO. 編號
  * 在規格頁標題或 ITEM 欄位中明確標示
  * 不是作為主項目的材質說明（如 "FURNITURE COM:" 區塊內的面料）
- 如果一個規格頁同時出現家具和其使用的面料，只提取家具本身
- 面料類項目只有在「獨立的面料規格頁」才需要提取（如 Fabric & Leather 文件）

針對每個項目，請按照以下 JSON 格式提取（對應惠而蒙格式 15 欄）：

```json
[
  {{
    "source_page": 項目所在的頁碼 (1-indexed),
    "category": "項目類別 (furniture 或 fabric)",
    "item_no": "項目編號 (B欄: Item no.)",
    "description": "項目描述 (C欄: Description)",
    "dimension": "尺寸 WxDxH mm (E欄: Dimension) - 僅家具類需填寫",
    "qty": 數量或 null (F欄: Qty),
    "uom": "單位 (G欄: UOM) - 使用標準值如 ea, m, set",
    "unit_cbm": 單位材積或 null (J欄: Unit CBM),
    "note": null,
    "location": "位置/區域 (M欄: Location)",
    "materials_specs": "材料/規格說明 (N欄: Materials Used / Specs)",
    "brand": "品牌或 null (O欄: Brand)"
  }}
]
```

欄位說明：
- source_page: 項目在 PDF 中的頁碼，必須根據文本中的 "--- Page N ---" 標記來判斷
- category: 項目類別，根據以下規則判斷：
  * "furniture" - 家具類：Casegoods、Seating、Lighting、桌椅櫃等實體家具
  * "fabric" - 面料類：Fabric、Leather、Vinyl、布料皮革等軟裝材料
  * 判斷依據：檔案名稱、ITEM 欄位內容（如 "Fabric @..." 開頭則為 fabric）
- item_no: 項目編號，如 "DLX-100"、"FUR-001"（注意：如果編號中有 @ 符號，只取 @ 之前的部分作為 item_no）
- description: 品名描述（**依 category 不同格式**）
  * **furniture 類別**：直接使用品名，如 "King Bed"、"Executive Chair"
  * **fabric 類別**：格式為 "<材料類型> to <關聯家具編號>"
    - 從 ITEM 欄位的 "@" 後面提取關聯的家具編號
    - 範例："Vinyl to DLX-100"、"Fabric to DLX-200, DLX-201"
- dimension: 尺寸/規格（**重要：依 category 不同處理**）
  * **furniture 類別**：格式為 "寬 x 深 x 高" mm，如 "1930 x 2130 x 290 H"
  * **fabric 類別**：格式為 "<Vendor>-<Pattern>-<Color>-<Width> <plain/pattern>"
    - 範例："Morbern Europe-Prodigy PRO 682-Lt Neutral-137cmW plain"
- qty: 數量，數字或 null
- uom: 單位（使用標準值：ea, set, m, roll, L, kg, sqm）
  * 家具類 → 通常是 "ea" 或 "set"
  * 面料類 → 可能是 "m" 或 "ea"
- unit_cbm: 單位材積（立方公尺），數字或 null
- note: 暫不處理，固定填 null
- location: **重要** 位置/區域提取規則：
  * 解析順序：先看詳細規格區取得家具資料，再查 Index 找到對應的 Location
  * 從 Index 中查找此 Item No. 出現的所有 "@XX" 地點
  * 如果有多個地點，用逗號分隔合併成一欄，如 "King DLX (A/B), End King, Grand King"
  * 如果沒有找到 @ 符號，location 填 null
  * 位置名稱簡寫規則：
    - "King Deluxe Room Type A" + "King Deluxe Room Type B" → "King DLX (A/B)"
    - "Standard Room Type A" + "Standard Room Type B" → "Standard (A/B)"
    - "Grand King Room Type A" + "Grand King Room Type B" → "Grand King (A/B)"
    - "End King" 保持原樣
  * 面料類 (Fabric/Leather): 從 Item No. 欄位提取 "@XX" 後面的部分
- materials_specs: 使用材料/規格，如 "Vinyl: DLX-500 Taupe"
- brand: 只填寫明確標示的品牌名稱（如 "Fairmont"、"Herman Miller"）。注意：MFR、材料代碼、規格編號都不是品牌，請留 null

PDF 內容：
{pdf_content}

請只返回 JSON 數組，不要包含其他文本。如果無法提取有效項目，返回空數組 []。
"""

DEFAULT_PROJECT_METADATA_PROMPT = """
請分析以下 PDF 內容，提取專案名稱。

請按照以下 JSON 格式返回：

```json
{{
  "project_name": "專案名稱"
}}
```

說明：
- project_name: 專案名稱，通常在文件標題或 "Project Name:" 後面，例如 "SOLAIRE BAY TOWER"

如果找不到，請填入 null。

PDF 內容：
{pdf_content}

請只返回 JSON 對象，不要包含其他文本。
"""


class PDFParserService:
    """Service for parsing PDFs and extracting BOQ items using Gemini AI."""

    def __init__(self, vendor_id: Optional[str] = None):
        """Initialize PDF parser service.

        Args:
            vendor_id: Optional vendor ID to load prompts from Skill config.
                       If None, uses default hardcoded prompts.
        """
        self.vendor_id = vendor_id
        self._skill = None
        self._prompts_loaded = False

        # Load Skill config if vendor_id provided
        if vendor_id:
            self._load_skill_config(vendor_id)

        try:
            import google.generativeai as genai
            self.genai = genai
            if settings.gemini_api_key:
                genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(settings.gemini_model)
            logger.info(f"Gemini model initialized: {settings.gemini_model}")
        except ImportError:
            logger.warning("google-generativeai not installed")
            self.genai = None
            self.model = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.genai = None
            self.model = None

    def _load_skill_config(self, vendor_id: str) -> None:
        """Load prompts from Skill config.

        Falls back to default prompts if loading fails.
        """
        try:
            from .skill_loader import get_skill_loader

            loader = get_skill_loader()
            self._skill = loader.load_vendor_or_default(vendor_id)

            if self._skill is not None:
                self._prompts_loaded = True
                logger.info(f"Loaded Skill prompts for vendor: {vendor_id}")
            else:
                logger.warning(f"Skill config not found for {vendor_id}, using default prompts")

        except Exception as e:
            logger.warning(f"Failed to load Skill config: {e}, using default prompts")
            self._skill = None

    def _get_boq_prompt_template(self) -> str:
        """Get BOQ extraction prompt template (from Skill or default)."""
        if self._skill is not None and self._prompts_loaded:
            template = self._skill.prompts.parse_specification.user_template
            if template:
                return template
        return DEFAULT_BOQ_PROMPT_TEMPLATE

    def _get_project_metadata_prompt_template(self) -> str:
        """Get project metadata prompt template (from Skill or default)."""
        if self._skill is not None and self._prompts_loaded:
            template = self._skill.prompts.parse_project_metadata.user_template
            if template:
                return template
        return DEFAULT_PROJECT_METADATA_PROMPT

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

    async def _call_gemini_with_retry(
        self,
        prompt: str,
        document_id: str,
        operation: str = "parse",
    ) -> Any:
        """
        Call Gemini API with timeout, retry logic, and observability tracking.

        Args:
            prompt: The prompt to send
            document_id: Document ID for logging
            operation: Operation name for logging

        Returns:
            Gemini API response

        Raises:
            APIError: If all retries fail
        """
        max_retries = settings.gemini_max_retries
        timeout_seconds = settings.gemini_timeout_seconds
        last_error = None
        observability = get_observability()

        # Prepare trace metadata
        skill_version = None
        if self._skill is not None:
            skill_version = self._skill.version

        trace_metadata = TraceMetadata(
            vendor_id=self.vendor_id,
            skill_version=skill_version,
            document_id=document_id,
            operation=operation,
            model=settings.gemini_model,
        )

        for attempt in range(max_retries + 1):
            start_time = datetime.utcnow()
            try:
                logger.info(
                    f"Calling Gemini API for {operation} (document: {document_id}, "
                    f"attempt: {attempt + 1}/{max_retries + 1}, timeout: {timeout_seconds}s)"
                )

                # Use asyncio.wait_for to enforce timeout
                response = await asyncio.wait_for(
                    asyncio.to_thread(self.model.generate_content, prompt),
                    timeout=timeout_seconds,
                )

                # Track successful call
                usage = observability.track_gemini_call(
                    name=operation,
                    prompt=prompt,
                    response=response,
                    metadata=trace_metadata,
                    start_time=start_time,
                )

                logger.info(
                    f"Gemini API call successful for {operation}: "
                    f"tokens={{input: {usage.prompt_tokens}, output: {usage.completion_tokens}, "
                    f"total: {usage.total_tokens}}}"
                )

                return response

            except asyncio.TimeoutError:
                last_error = f"API 呼叫超時（{timeout_seconds} 秒）"
                logger.warning(f"Gemini API timeout for {document_id}, attempt {attempt + 1}")

                # Track timeout
                observability.track_gemini_call(
                    name=operation,
                    prompt=prompt,
                    response=None,
                    metadata=trace_metadata,
                    start_time=start_time,
                    error=last_error,
                )

                if attempt < max_retries:
                    # Exponential backoff: 2s, 4s, 8s...
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                error_str = str(e).lower()

                # Track error
                observability.track_gemini_call(
                    name=operation,
                    prompt=prompt,
                    response=None,
                    metadata=trace_metadata,
                    start_time=start_time,
                    error=str(e),
                )

                # Check for specific errors that shouldn't be retried
                if "api key" in error_str:
                    raise_error(ErrorCode.GEMINI_API_ERROR, "Gemini API Key 未設定或無效")
                if "quota" in error_str:
                    raise_error(ErrorCode.GEMINI_QUOTA_EXCEEDED, "Gemini API 配額已用盡")

                last_error = str(e)
                logger.warning(f"Gemini API error for {document_id}: {e}")

                # Retry on rate limit and transient errors
                if "rate" in error_str or "504" in error_str or "deadline" in error_str:
                    if attempt < max_retries:
                        wait_time = 2 ** (attempt + 1)
                        logger.info(f"Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue

                # Don't retry other errors
                raise_error(ErrorCode.GEMINI_API_ERROR, f"Gemini 解析失敗：{str(e)}")

        # All retries exhausted
        raise_error(
            ErrorCode.GEMINI_API_ERROR,
            f"Gemini API 呼叫失敗（已重試 {max_retries} 次）：{last_error}",
        )

    async def parse_boq_with_gemini(
        self,
        file_path: str,
        document_id: str,
        extract_images: bool = True,
        target_categories: Optional[List[str]] = None,
    ) -> tuple[List[BOQItem], List[str], Dict[str, Any]]:
        """
        Parse BOQ from PDF using Gemini AI.

        Args:
            file_path: Path to PDF file
            document_id: Source document ID
            extract_images: Whether to extract images
            target_categories: Target categories to filter

        Returns:
            Tuple of (BOQ items list, image paths list, project metadata dict)

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

            # 1. Extract project metadata first
            project_metadata = await self._extract_project_metadata(text_content)
            logger.info(f"Extracted project metadata: {project_metadata}")

            # 2. Prepare prompt for BOQ items
            prompt = self._create_boq_extraction_prompt(
                text_content,
                target_categories=target_categories,
            )

            # Call Gemini API with retry logic
            response = await self._call_gemini_with_retry(prompt, document_id, "BOQ extraction")

            # Parse response
            boq_items = self._parse_gemini_response(response, document_id)
            logger.info(f"Extracted {len(boq_items)} BOQ items from document")

            # Extract images if requested
            image_paths = []
            if extract_images:
                image_paths = await self.extract_images_async(file_path, document_id)

            return boq_items, image_paths, project_metadata

        except Exception as e:
            # Re-raise APIError as-is
            if hasattr(e, "detail"):
                raise
            logger.error(f"Gemini parsing failed: {e}")
            raise_error(ErrorCode.GEMINI_API_ERROR, f"Gemini 解析失敗：{str(e)}")

    async def _extract_project_metadata(self, pdf_text: str) -> Dict[str, Any]:
        """
        Extract project metadata from PDF text using Gemini AI.

        Uses Skill prompt template if available, otherwise falls back to default.

        Args:
            pdf_text: Extracted text from PDF

        Returns:
            Dict containing project_name and area
        """
        if not self.model:
            return {}

        # Get prompt template (from Skill or default)
        template = self._get_project_metadata_prompt_template()

        # Format template with PDF content (limit to first 3000 chars for metadata)
        prompt = template.format(pdf_content=pdf_text[:3000])

        try:
            # Use simpler call without full retry (metadata extraction is optional)
            response = await asyncio.wait_for(
                asyncio.to_thread(self.model.generate_content, prompt),
                timeout=30,  # Shorter timeout for metadata
            )

            response_text = response.text
            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                logger.warning("No JSON found in project metadata response")
                return {}

            json_str = response_text[json_start:json_end]
            metadata = json.loads(json_str)

            return {
                "project_name": metadata.get("project_name"),
            }

        except asyncio.TimeoutError:
            logger.warning("Timeout extracting project metadata, skipping")
            return {}
        except Exception as e:
            logger.warning(f"Failed to extract project metadata: {e}")
            return {}

    def _create_boq_extraction_prompt(
        self,
        pdf_text: str,
        target_categories: Optional[List[str]] = None,
    ) -> str:
        """Create prompt for Gemini to extract BOQ items (15 columns per Excel template).

        Uses Skill prompt template if available, otherwise falls back to default.
        """
        categories_instruction = (
            f"只關注這些類別：{', '.join(target_categories)}"
            if target_categories
            else "提取所有家具和物料項目"
        )

        # Get prompt template (from Skill or default)
        template = self._get_boq_prompt_template()

        # Format template with variables
        prompt = template.format(
            categories_instruction=categories_instruction,
            pdf_content=pdf_text,
        )

        return prompt

    def _parse_gemini_response(self, response: Any, document_id: str) -> List[BOQItem]:
        """Parse Gemini response and create BOQItem objects (15 columns)."""
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
                    # Extract source_page from Gemini response
                    # This enables the deterministic image matching algorithm
                    source_page = self._parse_source_page(item_data.get("source_page"))

                    # Parse and validate category
                    raw_category = item_data.get("category")
                    category = None
                    if raw_category and isinstance(raw_category, str):
                        cat_lower = raw_category.lower().strip()
                        if cat_lower in ("furniture", "fabric"):
                            category = cat_lower

                    boq_item = BOQItem(
                        no=idx,
                        item_no=item_data.get("item_no", f"ITEM-{idx}"),
                        description=item_data.get("description", ""),
                        category=category,
                        dimension=item_data.get("dimension"),
                        qty=self._parse_qty(item_data.get("qty")),
                        uom=item_data.get("uom"),  # LLM 自行判斷，不做硬編碼標準化
                        unit_cbm=self._parse_float(item_data.get("unit_cbm")),
                        note=item_data.get("note"),
                        location=self._normalize_location(item_data.get("location")),
                        materials_specs=item_data.get("materials_specs"),
                        brand=item_data.get("brand"),
                        source_document_id=document_id,
                        source_page=source_page,
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
    def _parse_float(value: Any) -> Optional[float]:
        """Parse float value from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # Remove common formatting characters
                cleaned = value.replace(",", "").strip()
                return float(cleaned) if cleaned else None
            except ValueError:
                return None
        return None

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

    @staticmethod
    def _normalize_location(location: Optional[str]) -> Optional[str]:
        """
        Normalize location field for fabric/leather items.

        Converts "and" to "," to properly separate multiple furniture items.

        Examples:
            "DLX-100 King Bed and DLX-103 Queen Bed"
            -> "DLX-100 King Bed, DLX-103 Queen Bed"
        """
        if not location:
            return location

        # Replace " and " with ", " for proper separation
        # Use word boundary to avoid replacing "and" within words like "Grand"
        import re
        normalized = re.sub(r'\s+and\s+', ', ', location)

        return normalized.strip()

    @staticmethod
    def _parse_source_page(page_value: Any) -> Optional[int]:
        """
        Parse source page number from Gemini response.

        Args:
            page_value: Page number (int, float, or string)

        Returns:
            Page number (1-indexed) or None if invalid
        """
        if page_value is None:
            return None
        if isinstance(page_value, int) and page_value >= 1:
            return page_value
        if isinstance(page_value, float):
            page_int = int(page_value)
            return page_int if page_int >= 1 else None
        if isinstance(page_value, str):
            try:
                page_int = int(page_value.strip())
                return page_int if page_int >= 1 else None
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


def get_pdf_parser(vendor_id: Optional[str] = None) -> PDFParserService:
    """Get or create PDF parser instance.

    Args:
        vendor_id: Optional vendor ID for Skill-based prompts.
                   If provided, creates a new instance with vendor config.
                   If None, returns/creates default instance.

    Returns:
        PDFParserService instance
    """
    global _parser_instance

    # If vendor_id specified, create vendor-specific instance
    if vendor_id is not None:
        return PDFParserService(vendor_id=vendor_id)

    # Otherwise, return default singleton
    if _parser_instance is None:
        _parser_instance = PDFParserService()
    return _parser_instance
