"""Unified image matching service using Gemini Vision.

Strategy: Single API call that:
1. Receives all images + all BOQ items
2. Gemini identifies which images are product photos
3. Gemini matches each product photo to the best BOQ item
4. Returns only valid matches (non-product images excluded automatically)
"""

import logging
import asyncio
import json
import io
from typing import List, Dict, Optional
from collections import defaultdict

from PIL import Image

from ..models import BOQItem
from ..config import settings

logger = logging.getLogger(__name__)

# Basic size filter - only remove tiny images
MIN_IMAGE_AREA = 3000  # Very small threshold, let Gemini decide


class ImageMatcherService:
    """Service for matching images to BOQ items using unified Gemini Vision approach."""

    def __init__(self):
        """Initialize image matcher service."""
        try:
            import google.generativeai as genai
            self.genai = genai
            if settings.gemini_api_key:
                genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(settings.gemini_model)
            logger.info(f"ImageMatcherService initialized with Gemini: {settings.gemini_model}")
        except ImportError:
            logger.warning("google-generativeai not installed, using page-based matching")
            self.genai = None
            self.model = None
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.genai = None
            self.model = None

    async def match_images_to_items(
        self,
        images: List[Dict],
        boq_items: List[BOQItem],
    ) -> Dict[int, str]:
        """
        Match images to BOQ items using unified Gemini Vision approach.

        Single API call that:
        - Identifies product photos vs logos/drawings
        - Matches each product photo to the best BOQ item

        Args:
            images: List of dicts with {bytes, width, height, page, index}
            boq_items: List of BOQItem objects

        Returns:
            Dict mapping image index to BOQ item ID (only valid matches)
        """
        if not images or not boq_items:
            logger.info("No images or items to match")
            return {}

        # Basic size filter only
        valid_images = [
            img for img in images
            if img["width"] * img["height"] >= MIN_IMAGE_AREA
        ]

        if not valid_images:
            logger.warning("No valid images after basic size filter")
            return {}

        logger.info(f"Processing {len(valid_images)} images for {len(boq_items)} BOQ items")

        # Use Gemini Vision if available
        if self.model:
            try:
                return await self._unified_gemini_matching(valid_images, boq_items)
            except Exception as e:
                logger.error(f"Gemini matching failed: {e}")
                return self._fallback_page_matching(valid_images, boq_items)
        else:
            return self._fallback_page_matching(valid_images, boq_items)

    async def _unified_gemini_matching(
        self,
        images: List[Dict],
        boq_items: List[BOQItem],
    ) -> Dict[int, str]:
        """Single Gemini call for unified filtering + matching."""
        try:
            # Build BOQ items info
            items_info = []
            for item in boq_items:
                items_info.append({
                    "id": item.id,
                    "item_no": item.item_no,
                    "description": item.description,
                    "location": item.location or "",
                    "page": item.source_page or 0,
                })

            # Convert images to PIL format
            pil_images = []
            image_indices = []

            for img_data in images:
                try:
                    pil_img = Image.open(io.BytesIO(img_data["bytes"]))
                    # Convert to RGB
                    if pil_img.mode == "RGBA":
                        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                        bg.paste(pil_img, mask=pil_img.split()[3])
                        pil_img = bg
                    elif pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")

                    # Resize large images to reduce API payload
                    max_dim = 800
                    if pil_img.width > max_dim or pil_img.height > max_dim:
                        pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                    pil_images.append(pil_img)
                    image_indices.append(img_data["index"])
                except Exception as e:
                    logger.warning(f"Failed to process image {img_data['index']}: {e}")

            if not pil_images:
                return {}

            # Create unified prompt
            prompt = self._create_unified_prompt(items_info, len(pil_images))

            # Single Gemini Vision API call
            logger.info(f"Calling Gemini Vision: {len(pil_images)} images, {len(boq_items)} items")
            contents = [prompt] + pil_images

            response = await asyncio.to_thread(
                self.model.generate_content,
                contents,
            )

            # Parse response
            raw_mapping = self._parse_response(response)

            # Convert prompt indices to original image indices
            mapping = {}
            for prompt_idx_str, item_id in raw_mapping.items():
                try:
                    prompt_idx = int(prompt_idx_str)
                    if prompt_idx < len(image_indices):
                        original_idx = image_indices[prompt_idx]
                        mapping[original_idx] = item_id
                except (ValueError, IndexError):
                    pass

            logger.info(f"Gemini matched {len(mapping)} images to items")
            return mapping

        except Exception as e:
            logger.error(f"Unified Gemini matching failed: {e}")
            raise

    def _create_unified_prompt(self, items_info: List[Dict], image_count: int) -> str:
        """Create unified prompt for Gemini - filtering + matching in one."""
        items_json = json.dumps(items_info, ensure_ascii=False, indent=2)

        return f"""你是家具報價單 (BOQ) 圖片分析專家。

我提供 {image_count} 張從 PDF 提取的圖片，以及 BOQ 項目列表。
請分析每張圖片，判斷是否為家具產品照片，並配對到最適合的 BOQ 項目。

BOQ 項目列表：
{items_json}

分析規則：

【排除這些圖片】不要配對：
- 技術設計圖（黑白線條、CAD 圖面）
- 建築平面圖、施工圖
- 公司 Logo、品牌標誌
- 表格、圖表、純文字
- 過小或模糊無法辨識的圖片

【配對這些圖片】應該配對：
- 彩色家具產品照片
- 真實拍攝的家具圖片
- 產品展示照

【配對邏輯】
1. 根據圖片中的家具外觀判斷類型（床、椅、桌、櫃等）
2. 比對 BOQ 項目的 description 欄位
3. 參考頁碼 (page) 接近度作為輔助
4. 每個 BOQ 項目最多配對一張最適合的圖片
5. 不確定或無法配對的圖片請跳過

回應格式（JSON）：
{{"0": "item_id", "2": "item_id", "5": "item_id"}}

- 鍵 = 圖片索引（0-based）
- 值 = BOQ 項目的 id
- 只列出成功配對的圖片，跳過不適合的

若沒有任何圖片可配對，回應：{{}}

只返回 JSON，不要其他文字。"""

    def _parse_response(self, response) -> Dict[str, str]:
        """Parse JSON mapping from Gemini response."""
        try:
            text = response.text.strip()

            # Find JSON in response
            json_start = text.find("{")
            json_end = text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                logger.warning("No valid JSON found in Gemini response")
                return {}

            json_str = text[json_start:json_end]
            mapping = json.loads(json_str)

            # Filter out null values
            return {k: v for k, v in mapping.items() if v is not None}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini: {e}")
            logger.debug(f"Raw response: {response.text[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return {}

    def _fallback_page_matching(
        self,
        images: List[Dict],
        boq_items: List[BOQItem],
    ) -> Dict[int, str]:
        """Fallback: Match images to items by page proximity."""
        logger.info("Using page-based fallback matching")

        # Group by page
        images_by_page = defaultdict(list)
        for img in images:
            images_by_page[img["page"]].append(img)

        items_by_page = defaultdict(list)
        for item in boq_items:
            items_by_page[item.source_page or 1].append(item)

        # Match
        mapping = {}
        used_items = set()

        for page in sorted(images_by_page.keys()):
            page_images = images_by_page[page]

            # Get items from same page or adjacent pages
            candidates = []
            for p in [page, page - 1, page + 1]:
                for item in items_by_page.get(p, []):
                    if item.id not in used_items:
                        candidates.append(item)

            # Match images to available items
            for img in page_images:
                if candidates:
                    item = candidates.pop(0)
                    mapping[img["index"]] = item.id
                    used_items.add(item.id)

        logger.info(f"Page-based matching: {len(mapping)} images")
        return mapping


# Global matcher instance
_matcher_instance: Optional[ImageMatcherService] = None


def get_image_matcher() -> ImageMatcherService:
    """Get or create image matcher instance."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = ImageMatcherService()
    return _matcher_instance
