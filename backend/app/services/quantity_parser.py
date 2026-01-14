"""數量總表解析服務.

使用專用 Gemini prompt 解析數量總表 PDF，提取 Item No. 與 Total Qty。
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from google import genai

from ..config import settings
from ..models.quantity_summary import QuantitySummaryItem
from .observability import get_observability, TraceMetadata

logger = logging.getLogger(__name__)


class QuantityParserService:
    """數量總表解析服務."""

    def __init__(self, vendor_id: Optional[str] = None):
        """初始化服務.

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

        # Initialize Gemini client
        if settings.gemini_api_key:
            self.client = genai.Client(api_key=settings.gemini_api_key)
            self.model_name = settings.gemini_model
        else:
            self.client = None
            logger.warning("Gemini API key not configured")

    def _load_skill_config(self, vendor_id: str) -> None:
        """Load prompts from Skill config (required for POC).

        Raises:
            ValueError: If skill config cannot be loaded.
        """
        from .skill_loader import get_skill_loader

        loader = get_skill_loader()
        self._skill = loader.load_vendor(vendor_id)
        self._prompts_loaded = True
        logger.info(f"Loaded Skill prompts for quantity parser: {vendor_id}")

    def _get_quantity_prompt_template(self) -> str:
        """Get quantity summary prompt template from Skill."""
        if not self._prompts_loaded or self._skill is None:
            raise ValueError("Skill not loaded. POC requires habitus skill.")
        template = self._skill.prompts.parse_quantity_summary.user_template
        if not template:
            raise ValueError("Quantity summary prompt template not found in skill config.")
        return template

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        使用 PyMuPDF 提取 PDF 文字.

        Args:
            file_path: PDF 檔案路徑

        Returns:
            提取的文字內容
        """
        try:
            doc = fitz.open(file_path)
            text = ""

            for page_num in range(doc.page_count):
                page = doc[page_num]
                text += f"\n--- Page {page_num + 1} ---\n"
                text += page.get_text()

            doc.close()
            return text
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise

    async def parse_quantity_summary(
        self,
        file_path: str,
        document_id: str,
    ) -> List[QuantitySummaryItem]:
        """
        解析數量總表 PDF.

        Uses Skill prompt template if available, otherwise falls back to default.

        Args:
            file_path: PDF 檔案路徑
            document_id: 文件 ID

        Returns:
            QuantitySummaryItem 列表
        """
        observability = get_observability()

        # Prepare trace metadata
        skill_version = None
        if self._skill is not None:
            skill_version = self._skill.version

        trace_metadata = TraceMetadata(
            vendor_id=self.vendor_id,
            skill_version=skill_version,
            document_id=document_id,
            operation="quantity_summary_extraction",
            model=settings.gemini_model,
            environment=settings.environment,
        )

        try:
            if not self.client:
                raise ValueError("Gemini API 未配置")

            # Extract text from PDF using PyMuPDF
            text_content = self._extract_text_from_pdf(file_path)

            # Get prompt template (from Skill or default)
            template = self._get_quantity_prompt_template()

            # Format template with PDF content
            prompt = template.format(pdf_content=text_content)

            # Call Gemini API (use asyncio.to_thread for sync call)
            # New SDK uses client.models.generate_content
            start_time = datetime.utcnow()
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=prompt,
                ),
                timeout=settings.gemini_timeout_seconds,
            )

            # Track successful call
            usage = observability.track_gemini_call(
                name="quantity_summary_extraction",
                prompt=prompt,
                response=response,
                metadata=trace_metadata,
                start_time=start_time,
            )

            logger.info(
                f"Gemini API call successful for quantity summary: "
                f"tokens={{input: {usage.prompt_tokens}, output: {usage.completion_tokens}, "
                f"total: {usage.total_tokens}}}"
            )

            # Parse response
            response_text = response.text
            items = self._parse_gemini_response(response_text, document_id)

            logger.info(f"Parsed {len(items)} quantity items from quantity summary")
            return items

        except asyncio.TimeoutError:
            error_msg = f"Gemini API 呼叫超時（{settings.gemini_timeout_seconds} 秒）"
            logger.error(f"Gemini API timeout for quantity summary {file_path}")

            # Track timeout
            observability.track_gemini_call(
                name="quantity_summary_extraction",
                prompt=prompt if "prompt" in locals() else "",
                response=None,
                metadata=trace_metadata,
                start_time=start_time if "start_time" in locals() else datetime.utcnow(),
                error=error_msg,
            )

            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error parsing quantity summary {file_path}: {e}")

            # Track error
            observability.track_gemini_call(
                name="quantity_summary_extraction",
                prompt=prompt if "prompt" in locals() else "",
                response=None,
                metadata=trace_metadata,
                start_time=start_time if "start_time" in locals() else datetime.utcnow(),
                error=str(e),
            )

            raise

    def _parse_gemini_response(
        self, response_text: str, document_id: str
    ) -> List[QuantitySummaryItem]:
        """
        解析 Gemini API 回應.

        Args:
            response_text: Gemini 回應文字
            document_id: 文件 ID

        Returns:
            QuantitySummaryItem 列表
        """
        items = []

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = self._extract_json(response_text)

            # Parse JSON
            data = json.loads(json_text)

            if not isinstance(data, list):
                logger.warning(f"Expected list, got {type(data)}")
                return items

            for entry in data:
                try:
                    item_no = str(entry.get("item_no", "")).strip()
                    qty = entry.get("qty")
                    page = entry.get("page")

                    if not item_no:
                        continue

                    # Parse qty (handle string with commas)
                    if isinstance(qty, str):
                        qty = float(qty.replace(",", ""))
                    elif qty is None:
                        continue

                    item = QuantitySummaryItem(
                        item_no_raw=item_no,
                        total_qty=float(qty),
                        source_document_id=document_id,
                        source_page=int(page) if page else None,
                    )
                    items.append(item)

                except Exception as e:
                    logger.warning(f"Error parsing entry {entry}: {e}")
                    continue

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text}")

        return items

    def _extract_json(self, text: str) -> str:
        """
        從回應文字中提取 JSON.

        處理 markdown 程式碼區塊。

        Args:
            text: 回應文字

        Returns:
            純 JSON 字串
        """
        # Remove markdown code blocks
        json_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find JSON array directly
        array_pattern = r"\[\s*\{.*?\}\s*\]"
        match = re.search(array_pattern, text, re.DOTALL)
        if match:
            return match.group(0)

        # Return original text (might be pure JSON)
        return text.strip()

    def parse_quantity_from_text(
        self, text: str, document_id: str
    ) -> List[QuantitySummaryItem]:
        """
        從文字內容解析數量（用於測試或非 PDF 來源）.

        Args:
            text: 包含數量資訊的文字
            document_id: 文件 ID

        Returns:
            QuantitySummaryItem 列表
        """
        return self._parse_gemini_response(text, document_id)


# Global parser instance
_parser_instance: Optional[QuantityParserService] = None


# 工廠函式
def get_quantity_parser_service(vendor_id: Optional[str] = "habitus") -> QuantityParserService:
    """
    取得 QuantityParserService 實例.

    Args:
        vendor_id: Vendor ID for Skill-based prompts.
                   Defaults to "habitus" to load vendor skill configuration.

    Returns:
        QuantityParserService 實例
    """
    global _parser_instance

    # If vendor_id specified, create vendor-specific instance
    if vendor_id is not None:
        return QuantityParserService(vendor_id=vendor_id)

    # Otherwise, return default singleton (with habitus skill)
    if _parser_instance is None:
        _parser_instance = QuantityParserService(vendor_id="habitus")
    return _parser_instance
