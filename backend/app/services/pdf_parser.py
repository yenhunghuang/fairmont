"""PDF parser service with Gemini AI integration."""

import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

from ..config import settings
from ..models import BOQItem
from ..utils import ErrorCode, raise_error
from .observability import get_observability, TraceMetadata

logger = logging.getLogger(__name__)


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
            from google import genai
            self.genai = genai
            if settings.gemini_api_key:
                self.client = genai.Client(api_key=settings.gemini_api_key)
            else:
                self.client = None
            self.model_name = settings.gemini_model
            logger.info(f"Gemini client initialized: {settings.gemini_model}")
        except ImportError:
            logger.warning("google-genai not installed")
            self.genai = None
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.genai = None
            self.client = None

    def _load_skill_config(self, vendor_id: str) -> None:
        """Load prompts from Skill config (required for POC).

        Raises:
            ValueError: If skill config cannot be loaded.
        """
        from .skill_loader import get_skill_loader

        loader = get_skill_loader()
        self._skill = loader.load_vendor(vendor_id)
        self._prompts_loaded = True
        logger.info(f"Loaded Skill prompts for vendor: {vendor_id}")

    def _get_boq_prompt_template(self) -> str:
        """Get BOQ extraction prompt template from Skill."""
        if not self._prompts_loaded or self._skill is None:
            raise ValueError("Skill not loaded. POC requires habitus skill.")
        template = self._skill.prompts.parse_specification.user_template
        if not template:
            raise ValueError("BOQ prompt template not found in skill config.")
        return template

    def _get_project_metadata_prompt_template(self) -> str:
        """Get project metadata prompt template from Skill."""
        if not self._prompts_loaded or self._skill is None:
            raise ValueError("Skill not loaded. POC requires habitus skill.")
        template = self._skill.prompts.parse_project_metadata.user_template
        if not template:
            raise ValueError("Project metadata prompt template not found in skill config.")
        return template

    def _get_boq_system_prompt(self) -> Optional[str]:
        """Get BOQ extraction system prompt (from Skill or None)."""
        if self._skill is not None and self._prompts_loaded:
            system_prompt = self._skill.prompts.parse_specification.system
            if system_prompt and system_prompt.strip():
                return system_prompt.strip()
        return None

    def _get_metadata_system_prompt(self) -> Optional[str]:
        """Get metadata extraction system prompt (from Skill or None)."""
        if self._skill is not None and self._prompts_loaded:
            system_prompt = self._skill.prompts.parse_project_metadata.system
            if system_prompt and system_prompt.strip():
                return system_prompt.strip()
        return None

    def _find_specification_page_content(self, pdf_text: str, max_chars: int = 5000) -> str:
        """
        Find specification page content from PDF text.

        Searches for content containing "ITEM NO.:" which indicates a spec page,
        rather than index/cover pages. Uses page separators to avoid picking up
        PROJECT from index pages.

        Args:
            pdf_text: Full PDF text content
            max_chars: Maximum characters to return

        Returns:
            Specification page content containing PROJECT field
        """
        spec_markers = ["ITEM NO.:", "ITEM NO:", "Item No.:"]
        page_separators = ["\f", "\n\n\n", "\r\n\r\n\r\n"]

        for marker in spec_markers:
            marker_pos = pdf_text.find(marker)
            if marker_pos != -1:
                # Search within 800 chars before ITEM NO. (reduced from 1500)
                search_start = max(0, marker_pos - 800)
                prefix_text = pdf_text[search_start:marker_pos]

                # Find the nearest page separator to isolate spec page content
                page_start = 0
                for sep in page_separators:
                    sep_pos = prefix_text.rfind(sep)
                    if sep_pos != -1:
                        page_start = max(page_start, sep_pos + len(sep))

                # Search for PROJECT only within the same page block
                page_content = prefix_text[page_start:]
                project_pos = page_content.rfind("PROJECT:")
                if project_pos == -1:
                    project_pos = page_content.rfind("PROJECT :")
                if project_pos == -1:
                    project_pos = page_content.rfind("Project:")

                if project_pos != -1:
                    start_pos = search_start + page_start + project_pos
                else:
                    start_pos = search_start + page_start

                end_pos = min(len(pdf_text), marker_pos + 2000)
                result = pdf_text[start_pos:end_pos]
                logger.debug(
                    f"_find_specification_page_content: marker={marker}, "
                    f"marker_pos={marker_pos}, page_start={page_start}, "
                    f"project_pos={project_pos}, result_len={len(result)}"
                )
                # Log first 200 chars of result for debugging
                logger.debug(f"Spec content preview: {result[:200]}...")
                return result

        # Fallback: return first portion if no spec markers found
        logger.debug("_find_specification_page_content: No spec markers found, using fallback")
        return pdf_text[:max_chars]

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
        doc = None
        try:
            doc = fitz.open(file_path)
            page_count = doc.page_count

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
        finally:
            if doc:
                doc.close()

    def extract_text_from_pdf(self, file_path: str, max_pages: int | None = None) -> str:
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
        doc = None
        try:
            doc = fitz.open(file_path)
            text = ""

            for page_num in range(min(doc.page_count, max_pages or doc.page_count)):
                page = doc[page_num]
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page.get_text()

            return text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise_error(ErrorCode.PDF_EXTRACT_FAILED, "文本提取失敗")
        finally:
            if doc:
                doc.close()

    async def _call_gemini_with_retry(
        self,
        prompt: str,
        document_id: str,
        operation: str = "parse",
        system_prompt: Optional[str] = None,
    ) -> Any:
        """
        Call Gemini API with timeout, retry logic, and observability tracking.

        Args:
            prompt: The prompt to send
            document_id: Document ID for logging
            operation: Operation name for logging
            system_prompt: Optional system instruction for the model

        Returns:
            Gemini API response

        Raises:
            APIError: If all retries fail
        """
        max_retries = settings.gemini_max_retries
        timeout_seconds = settings.gemini_timeout_seconds
        last_error = None
        observability = get_observability()

        # Prepare generation config with system instruction if provided
        generate_config = None
        if system_prompt and self.genai:
            try:
                generate_config = self.genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                )
                logger.debug(f"Using system prompt for {operation}")
            except Exception as e:
                logger.warning(f"Failed to create config with system instruction: {e}")

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
            retry_count=0,
            environment=settings.environment,
        )

        for attempt in range(max_retries + 1):
            start_time = datetime.utcnow()
            trace_metadata.retry_count = attempt  # Track retry count
            try:
                logger.info(
                    f"Calling Gemini API for {operation} (document: {document_id}, "
                    f"attempt: {attempt + 1}/{max_retries + 1}, timeout: {timeout_seconds}s)"
                )

                # Use asyncio.wait_for to enforce timeout
                # New SDK uses client.models.generate_content with model name
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=prompt,
                        config=generate_config,
                    ),
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

                # Retry on rate limit and transient errors (including 499 cancelled)
                retryable = (
                    "rate" in error_str
                    or "504" in error_str
                    or "499" in error_str
                    or "cancelled" in error_str
                    or "deadline" in error_str
                    or "unavailable" in error_str
                )
                if retryable and attempt < max_retries:
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"Retrying in {wait_time} seconds due to transient error...")
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
        if not self.client:
            raise_error(
                ErrorCode.GEMINI_API_ERROR,
                "Gemini API 未配置，無法解析 PDF",
            )

        try:
            # Extract text first
            text_content = self.extract_text_from_pdf(file_path)

            # 1. Extract project metadata first
            project_metadata = await self._extract_project_metadata(text_content, document_id)
            logger.info(
                f"Extracted project metadata: {project_metadata}, "
                f"project_name={project_metadata.get('project_name') if project_metadata else 'N/A'}"
            )

            # 2. Prepare prompt for BOQ items
            prompt = self._create_boq_extraction_prompt(
                text_content,
                target_categories=target_categories,
            )

            # Call Gemini API with retry logic (using system prompt if available)
            system_prompt = self._get_boq_system_prompt()
            response = await self._call_gemini_with_retry(
                prompt, document_id, "BOQ extraction", system_prompt=system_prompt
            )

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

    async def _extract_project_metadata(
        self, pdf_text: str, document_id: str = ""
    ) -> Dict[str, Any]:
        """
        Extract project metadata from PDF text using Gemini AI.

        Uses Skill prompt template if available, otherwise falls back to default.

        Args:
            pdf_text: Extracted text from PDF
            document_id: Document ID for tracking

        Returns:
            Dict containing project_name and area
        """
        if not self.client:
            return {}

        observability = get_observability()

        # Prepare trace metadata
        skill_version = None
        if self._skill is not None:
            skill_version = self._skill.version

        trace_metadata = TraceMetadata(
            vendor_id=self.vendor_id,
            skill_version=skill_version,
            document_id=document_id,
            operation="metadata_extraction",
            model=settings.gemini_model,
            environment=settings.environment,
        )

        # Get prompt template (from Skill or default)
        template = self._get_project_metadata_prompt_template()

        # Find specification page content (contains "ITEM NO.:")
        # Skip index/cover pages and find the actual spec page with PROJECT field
        spec_content = self._find_specification_page_content(pdf_text)

        # Format template with spec page content
        prompt = template.format(pdf_content=spec_content)

        start_time = datetime.utcnow()
        try:
            # Use simpler call without full retry (metadata extraction is optional)
            # New SDK uses client.models.generate_content
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=prompt,
                ),
                timeout=30,  # Shorter timeout for metadata
            )

            # Track successful call
            usage = observability.track_gemini_call(
                name="metadata_extraction",
                prompt=prompt,
                response=response,
                metadata=trace_metadata,
                start_time=start_time,
            )

            logger.info(
                f"Metadata extraction successful: "
                f"tokens={{input: {usage.prompt_tokens}, output: {usage.completion_tokens}, "
                f"total: {usage.total_tokens}}}"
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
            observability.track_gemini_call(
                name="metadata_extraction",
                prompt=prompt,
                response=None,
                metadata=trace_metadata,
                start_time=start_time,
                error="Timeout",
            )
            return {}
        except Exception as e:
            logger.warning(f"Failed to extract project metadata: {e}")
            observability.track_gemini_call(
                name="metadata_extraction",
                prompt=prompt,
                response=None,
                metadata=trace_metadata,
                start_time=start_time,
                error=str(e),
            )
            return {}

    def _create_boq_extraction_prompt(
        self,
        pdf_text: str,
        target_categories: list[str] | None = None,
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

    def _parse_gemini_response(self, response: Any, document_id: str) -> list[BOQItem]:
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

                    # Parse and validate category (1=家具, 5=面料)
                    # 擴展接受值以提高容錯能力：LLM 可能回傳原始分類名稱而非統一值
                    FURNITURE_CATEGORIES = {
                        "furniture", "casegoods", "casegood", "seating", "lighting"
                    }
                    FABRIC_CATEGORIES = {"fabric", "leather", "vinyl", "textile"}

                    raw_category = item_data.get("category")
                    category = None
                    if raw_category and isinstance(raw_category, str):
                        cat_lower = raw_category.lower().strip()
                        if cat_lower in FURNITURE_CATEGORIES:
                            category = 1
                        elif cat_lower in FABRIC_CATEGORIES:
                            category = 5

                    # Extract affiliate (面料來源家具編號)
                    # First, try to detect fabric from description pattern
                    description = item_data.get("description", "")
                    affiliate = self._extract_affiliate_from_description(description, category)

                    # If category is not set but affiliate is found, it's fabric
                    # If description contains "to DLX-" pattern, it's fabric
                    if category is None and affiliate:
                        category = 5
                    elif category is None:
                        # Try to detect fabric from description pattern even without explicit category
                        import re
                        fabric_pattern = r'\b(Vinyl|Fabric|Leather)\s+to\s+[A-Z]{2,4}-\d+'
                        if re.search(fabric_pattern, description, re.IGNORECASE):
                            category = 5
                            affiliate = self._extract_affiliate_from_description(description, 5)
                        else:
                            # Default to furniture if no fabric pattern found
                            category = 1

                    boq_item = BOQItem(
                        no=idx,
                        item_no=item_data.get("item_no", f"ITEM-{idx}"),
                        description=description,
                        category=category,
                        affiliate=affiliate,
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
    def _parse_float(value: Any) -> float | None:
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
    def _parse_qty(qty_value: Any) -> float | None:
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
    def _extract_affiliate_from_description(
        description: str, category: Optional[int]
    ) -> Optional[str]:
        """
        Extract affiliate furniture item numbers from fabric description.

        Only extracts for fabric items (category=5). Looks for patterns like:
        - "Vinyl to DLX-100"
        - "Fabric to DLX-100, DLX-101"
        - "Leather to STD-200 and DLX-300"

        Args:
            description: Item description
            category: Category (1=furniture, 5=fabric)

        Returns:
            Comma-separated furniture item numbers for fabric items, None for furniture
        """
        import re

        # Only process fabric items (category=5)
        if category != 5 or not description:
            return None

        # First, find the part after "to"
        to_pattern = r'\bto\s+(.+)$'
        to_match = re.search(to_pattern, description, re.IGNORECASE)

        if not to_match:
            return None

        rest = to_match.group(1)

        # Find all item_no patterns in the rest of the description
        # Matches item_no format like: DLX-100, STD-200, DLX-100.1, DLX-100A, etc.
        item_pattern = r'([A-Z]{2,4}-\d+(?:\.\d+)?(?:[A-Z])?)'
        matches = re.findall(item_pattern, rest, re.IGNORECASE)

        if matches:
            # Normalize to uppercase and join with ', '
            return ', '.join([m.upper() for m in matches])

        return None

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
    ) -> list[str]:
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
    ) -> list[str]:
        """Extract images from PDF."""
        from .image_extractor import ImageExtractorService

        extractor = ImageExtractorService()
        return extractor.extract_images(file_path, document_id)


# Global parser instance
_parser_instance: Optional[PDFParserService] = None


def get_pdf_parser(vendor_id: Optional[str] = "habitus") -> PDFParserService:
    """Get or create PDF parser instance.

    Args:
        vendor_id: Vendor ID for Skill-based prompts.
                   Defaults to "habitus" to load vendor skill configuration.

    Returns:
        PDFParserService instance
    """
    global _parser_instance

    # If vendor_id specified, create vendor-specific instance
    if vendor_id is not None:
        return PDFParserService(vendor_id=vendor_id)

    # Otherwise, return default singleton (with habitus skill)
    if _parser_instance is None:
        _parser_instance = PDFParserService(vendor_id="habitus")
    return _parser_instance
