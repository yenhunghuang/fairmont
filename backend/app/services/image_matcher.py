"""Image matching service - finds first large image after each BOQ item.

Strategy:
1. For each BOQ item, find the first large image on same/next page
2. Use Gemini to verify if image matches item description
3. High confidence → use image
4. Low confidence → leave blank for manual input
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

# Image size thresholds
MIN_LARGE_IMAGE_AREA = 20000  # Minimum area to be considered "large"
CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence to use image


class ImageMatcherService:
    """Service for matching first large image to each BOQ item."""

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
            logger.warning("google-generativeai not installed")
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
        Match first large image after each BOQ item.

        Args:
            images: List of dicts with {bytes, width, height, page, index}
            boq_items: List of BOQItem objects

        Returns:
            Dict mapping image index to BOQ item ID
        """
        if not images or not boq_items:
            logger.info("No images or items to match")
            return {}

        # Filter to large images only
        large_images = [
            img for img in images
            if img["width"] * img["height"] >= MIN_LARGE_IMAGE_AREA
        ]

        if not large_images:
            logger.warning("No large images found")
            return {}

        # Sort images by page, then by index (order in PDF)
        large_images.sort(key=lambda x: (x["page"], x["index"]))

        # Group images by page
        images_by_page = defaultdict(list)
        for img in large_images:
            images_by_page[img["page"]].append(img)

        logger.info(f"Found {len(large_images)} large images across {len(images_by_page)} pages")

        # For each BOQ item, find candidate image (first large image on same/next page)
        candidates = []  # List of (item, image) pairs to verify
        used_images = set()

        for item in boq_items:
            item_page = item.source_page or 1

            # Look for first unused large image on same page or next page
            candidate_img = None
            for page in [item_page, item_page + 1]:
                for img in images_by_page.get(page, []):
                    if img["index"] not in used_images:
                        candidate_img = img
                        break
                if candidate_img:
                    break

            if candidate_img:
                candidates.append((item, candidate_img))
                used_images.add(candidate_img["index"])

        if not candidates:
            logger.info("No candidate pairs found")
            return {}

        logger.info(f"Found {len(candidates)} candidate image-item pairs")

        # Use Gemini to verify matches
        if self.model:
            return await self._verify_matches_with_gemini(candidates)
        else:
            # Without Gemini, just use all candidates
            return {img["index"]: item.id for item, img in candidates}

    async def _verify_matches_with_gemini(
        self,
        candidates: List[tuple],
    ) -> Dict[int, str]:
        """Verify each candidate pair with Gemini, return only confident matches."""
        verified_matches = {}

        # Process in batch for efficiency
        try:
            # Prepare all images and items info
            pil_images = []
            items_info = []
            valid_candidates = []

            for item, img_data in candidates:
                try:
                    pil_img = Image.open(io.BytesIO(img_data["bytes"]))
                    if pil_img.mode == "RGBA":
                        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
                        bg.paste(pil_img, mask=pil_img.split()[3])
                        pil_img = bg
                    elif pil_img.mode != "RGB":
                        pil_img = pil_img.convert("RGB")

                    # Resize if too large
                    max_dim = 600
                    if pil_img.width > max_dim or pil_img.height > max_dim:
                        pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                    pil_images.append(pil_img)
                    items_info.append({
                        "index": len(pil_images) - 1,
                        "item_id": item.id,
                        "item_no": item.item_no,
                        "description": item.description,
                        "image_index": img_data["index"],
                    })
                    valid_candidates.append((item, img_data))
                except Exception as e:
                    logger.warning(f"Failed to process image: {e}")

            if not pil_images:
                return {}

            # Create verification prompt
            prompt = self._create_verification_prompt(items_info)

            # Call Gemini
            logger.info(f"Verifying {len(pil_images)} candidate matches with Gemini")
            contents = [prompt] + pil_images

            response = await asyncio.to_thread(
                self.model.generate_content,
                contents,
            )

            # Parse response
            verification_results = self._parse_verification_response(response)

            # Build final matches (only confident ones)
            for info in items_info:
                idx = str(info["index"])
                if idx in verification_results:
                    confidence = verification_results[idx].get("confidence", 0)
                    is_match = verification_results[idx].get("match", False)

                    if is_match and confidence >= CONFIDENCE_THRESHOLD:
                        verified_matches[info["image_index"]] = info["item_id"]
                        logger.debug(
                            f"Verified match: image {info['image_index']} -> {info['item_no']} "
                            f"(confidence: {confidence})"
                        )
                    else:
                        logger.debug(
                            f"Rejected match: image {info['image_index']} -> {info['item_no']} "
                            f"(confidence: {confidence}, match: {is_match})"
                        )

            logger.info(f"Verified {len(verified_matches)} confident matches out of {len(candidates)} candidates")
            return verified_matches

        except Exception as e:
            logger.error(f"Gemini verification failed: {e}")
            return {}

    def _create_verification_prompt(self, items_info: List[Dict]) -> str:
        """Create prompt for verifying image-item matches."""
        items_json = json.dumps(
            [{"index": i["index"], "item_no": i["item_no"], "description": i["description"]}
             for i in items_info],
            ensure_ascii=False,
            indent=2
        )

        return f"""你是家具圖片驗證專家。我提供 {len(items_info)} 張圖片，每張對應一個 BOQ 項目。
請判斷每張圖片是否真的是該項目的產品照片。

BOQ 項目對應：
{items_json}

判斷標準：
1. 圖片必須是彩色產品照片（不是設計圖、平面圖、Logo）
2. 圖片中的家具類型必須符合 description（例如：床的圖片配對床的項目）
3. 給出信心度 0.0-1.0

回應格式（JSON）：
{{
  "0": {{"match": true, "confidence": 0.9}},
  "1": {{"match": false, "confidence": 0.3}},
  "2": {{"match": true, "confidence": 0.85}}
}}

- 鍵 = 圖片索引（與上方列表對應）
- match = 是否為正確的產品照片
- confidence = 信心度（0.0-1.0）

只返回 JSON，不要其他文字。"""

    def _parse_verification_response(self, response) -> Dict[str, Dict]:
        """Parse verification response from Gemini."""
        try:
            text = response.text.strip()

            json_start = text.find("{")
            json_end = text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                logger.warning("No valid JSON in verification response")
                return {}

            result = json.loads(text[json_start:json_end])
            return result

        except Exception as e:
            logger.error(f"Failed to parse verification response: {e}")
            return {}


# Global matcher instance
_matcher_instance: Optional[ImageMatcherService] = None


def get_image_matcher() -> ImageMatcherService:
    """Get or create image matcher instance."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = ImageMatcherService()
    return _matcher_instance
