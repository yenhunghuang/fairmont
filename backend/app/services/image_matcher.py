"""Image matching service with intelligent BOQ description-based matching.

Strategy:
1. For each BOQ item, find candidate images on same/nearby pages
2. Use Gemini Vision to validate:
   - Is it a product sample (not logo/design)?
   - Does it match the BOQ item description?
3. Only match images that pass both checks
4. Significantly reduces API calls (5 items × 2-3 candidates vs 39 images)
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import Optional

from ..config import settings
from ..models import BOQItem

logger = logging.getLogger(__name__)

# Minimum area to be considered "large" (filters out logos/icons/small graphics)
MIN_LARGE_IMAGE_AREA = 8000

# Search radius for candidate images around BOQ item's page
IMAGE_SEARCH_RADIUS = 2  # pages before/after item's page


def create_description_based_prompt(boq_description: str) -> str:
    """Create Vision prompt that matches images against BOQ item description."""
    return f"""请分析这张图片，判断它是否是与以下家具项目相匹配的实物样品照：

【项目描述】{boq_description}

评估标准：
1. 这张图片是否是实物家具/产品样品照（而非设计图、CAD、平面图）？
2. 图片内容是否与"{boq_description}"这类产品相匹配？
   - 如果描述是"會議桌"，图片应显示桌子而非椅子
   - 如果描述是"辦公椅"，图片应显示椅子而非其他家具
3. 是否清晰可见产品的样式、颜色、材质？
4. 是否NOT是纯Logo、Icon、品牌标记？
5. 是否NOT是文字说明图、信息图？

请返回JSON格式，只返回这个格式，不要其他文本：
{{
  "is_matching_product": true或false,
  "confidence": 0.0到1.0,
  "reason": "简短说明"
}}

如果无法判断，返回 is_matching_product: false"""


class ImageMatcherService:
    """Service for matching images to BOQ items with Gemini Vision validation."""

    def __init__(self, enable_vision_validation: bool = True):
        """
        Initialize image matcher service.

        Args:
            enable_vision_validation: Whether to use Gemini Vision for validation
        """
        self.enable_vision_validation = enable_vision_validation

        # Initialize Gemini
        self.genai = None
        self.model = None

        try:
            import google.generativeai as genai
            self.genai = genai
            if settings.gemini_api_key:
                genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel(settings.gemini_model)
            logger.info(f"Gemini Vision model initialized: {settings.gemini_model}")
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini Vision: {e}")
            self.genai = None
            self.model = None
            self.enable_vision_validation = False

        logger.info(
            f"ImageMatcherService initialized (vision_validation={self.enable_vision_validation})"
        )

    async def match_images_to_items(
        self,
        images: list[dict],
        boq_items: list[BOQItem],
        validate_product_images: bool = True,
        min_confidence: float = 0.6,
    ) -> dict[int, str]:
        """
        Match images to BOQ items using description-based validation.

        Strategy:
        1. Filter to large images (≥8000 pixels) as candidates
        2. For each BOQ item, find candidate images on same/nearby pages
        3. Use Gemini Vision to validate if images match item description
        4. Only validate required candidates, not all images (much faster)

        Args:
            images: List of dicts with {bytes, width, height, page, index}
            boq_items: List of BOQItem objects
            validate_product_images: Whether to use Vision validation
            min_confidence: Minimum confidence threshold

        Returns:
            Dict mapping image index to BOQ item ID
        """
        if not images or not boq_items:
            logger.info("No images or items to match")
            return {}

        # 1. Filter to large images globally
        large_images = [
            img for img in images
            if img["width"] * img["height"] >= MIN_LARGE_IMAGE_AREA
        ]

        if not large_images:
            logger.warning("No large images found for matching")
            return {}

        logger.info(
            f"Found {len(large_images)} large images "
            f"for {len(boq_items)} items (description-based matching)"
        )

        # 2. Group large images by page
        images_by_page = defaultdict(list)
        for img in large_images:
            images_by_page[img["page"]].append(img)

        # 3. Match each BOQ item using description-based validation
        mapping = {}
        used_images = set()

        for item_idx, item in enumerate(boq_items, 1):
            logger.info(f"Processing item {item_idx}/{len(boq_items)}: {item.item_no} (page {item.source_page or 1})")
            item_page = item.source_page or 1

            # Find candidate images on same page or nearby pages
            candidates = []
            search_range = [
                item_page - IMAGE_SEARCH_RADIUS,
                item_page,
                item_page + IMAGE_SEARCH_RADIUS,
            ]
            logger.debug(f"Searching pages {search_range} for {item.item_no}")

            for search_page in search_range:
                if search_page > 0:
                    page_images = images_by_page.get(search_page, [])
                    unused_images = [
                        img for img in page_images if img["index"] not in used_images
                    ]
                    logger.debug(
                        f"  Page {search_page}: {len(page_images)} total, "
                        f"{len(unused_images)} unused"
                    )
                    candidates.extend(unused_images)

            if not candidates:
                logger.warning(
                    f"No candidate images found for {item.item_no} "
                    f"(search pages: {search_range})"
                )
                continue

            logger.info(f"Found {len(candidates)} candidate images for {item.item_no}")

            # 4. Validate candidates against item description
            if validate_product_images and self.enable_vision_validation:
                # Find best matching image using Vision
                best_match = await self._find_best_matching_image(
                    candidates, item, min_confidence
                )

                if best_match:
                    mapping[best_match["index"]] = item.id
                    used_images.add(best_match["index"])
                    logger.debug(
                        f"Matched image {best_match['index']} "
                        f"to item {item.item_no}"
                    )
            else:
                # Fallback: use first candidate (original behavior)
                candidates.sort(key=lambda x: (x["page"], x["index"]))
                first_img = candidates[0]
                mapping[first_img["index"]] = item.id
                used_images.add(first_img["index"])

        logger.info(
            f"Matched {len(mapping)}/{len(boq_items)} items with images "
            f"(validated {len(boq_items) * 2} images instead of {len(large_images)})"
        )
        return mapping

    async def _find_best_matching_image(
        self,
        candidates: list[dict],
        boq_item: BOQItem,
        min_confidence: float = 0.6,
    ) -> dict | None:
        """
        Find best matching image for a BOQ item using description-based validation.

        Args:
            candidates: List of candidate image dicts
            boq_item: BOQ item to match against
            min_confidence: Minimum confidence threshold

        Returns:
            Best matching image dict or None
        """
        if not self.model:
            logger.warning(f"Gemini Vision not available for {boq_item.item_no}")
            return None

        if not candidates:
            logger.debug(f"No candidate images for {boq_item.item_no}")
            return None

        logger.debug(
            f"Validating {len(candidates)} candidates for {boq_item.item_no} "
            f"(description: {boq_item.description})"
        )

        best_match_verified = None
        best_match_fallback = None
        best_confidence_verified = 0.0
        best_confidence_fallback = 0.0

        # Validate candidates against item description
        for img in candidates:
            try:
                is_match, confidence, reason = (
                    await self._validate_image_for_item(
                        img["bytes"], boq_item, min_confidence
                    )
                )

                logger.debug(
                    f"Image {img['index']} (page {img['page']}): "
                    f"match={is_match}, confidence={confidence:.2f}, reason={reason}"
                )

                # Track best verified match (is_match=True)
                if is_match and confidence > best_confidence_verified:
                    best_match_verified = img
                    best_confidence_verified = confidence

                # Track best fallback match (highest confidence regardless)
                if confidence > best_confidence_fallback:
                    best_match_fallback = img
                    best_confidence_fallback = confidence

            except Exception as e:
                logger.warning(
                    f"Failed to validate image {img['index']} for {boq_item.item_no}: {e}"
                )
                continue

        # Prefer verified matches, but use fallback if available
        best_match = best_match_verified or best_match_fallback

        if best_match:
            match_type = "verified" if best_match == best_match_verified else "fallback"
            best_confidence = (
                best_confidence_verified
                if best_match == best_match_verified
                else best_confidence_fallback
            )
            logger.info(
                f"Best match ({match_type}) for {boq_item.item_no}: "
                f"image {best_match['index']} (confidence={best_confidence:.2f})"
            )
        else:
            logger.warning(
                f"No matching images found for {boq_item.item_no} "
                f"(threshold={min_confidence})"
            )

        return best_match

    async def _validate_image_for_item(
        self,
        image_bytes: bytes,
        boq_item: BOQItem,
        min_confidence: float = 0.6,
    ) -> tuple[bool, float, str]:
        """
        Validate if image matches BOQ item using description.

        Args:
            image_bytes: Raw image bytes
            boq_item: BOQ item with description
            min_confidence: Minimum confidence threshold

        Returns:
            Tuple of (is_matching, confidence, reason)
        """
        if not self.model:
            return False, 0.0, "Gemini Vision not initialized"

        try:
            import base64

            # Use description-based prompt
            item_desc = boq_item.description or "家具"
            prompt = create_description_based_prompt(item_desc)
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            logger.debug(f"Calling Vision API for item: {boq_item.item_no}")

            # Call Gemini Vision
            response = await asyncio.to_thread(
                self.model.generate_content,
                [
                    prompt,
                    {
                        "mime_type": "image/png",
                        "data": image_base64,
                    },
                ],
            )

            response_text = response.text.strip()
            logger.debug(
                f"Vision response for {boq_item.item_no}: {response_text[:300]}"
            )

            # Extract JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                logger.warning(
                    f"Could not find JSON in Vision response for {boq_item.item_no}. "
                    f"Response: {response_text[:500]}"
                )
                return False, 0.0, "無法解析響應"

            json_str = response_text[json_start:json_end]
            logger.debug(f"Extracted JSON: {json_str}")

            result = json.loads(json_str)
            logger.debug(f"Parsed result: {result}")

            is_match = result.get("is_matching_product", False)
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "未知原因")

            logger.debug(
                f"Validation result - is_match: {is_match}, "
                f"confidence: {confidence}, reason: {reason}"
            )

            # Return best result regardless of threshold
            # (threshold check happens in _find_best_matching_image)
            return is_match, confidence, reason

        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse Vision JSON for {boq_item.item_no}: {e}. "
                f"Raw response: {response_text[:500] if 'response_text' in locals() else 'N/A'}"
            )
            return False, 0.0, "JSON解析失敗"
        except Exception as e:
            logger.error(
                f"Vision validation error for {boq_item.item_no}: {e}",
                exc_info=True,
            )
            return False, 0.0, f"驗證錯誤: {str(e)}"

    async def _validate_images_batch(
        self,
        images: list[dict],
        min_confidence: float = 0.6,
    ) -> list[dict]:
        """
        Legacy method - kept for backward compatibility.
        New approach uses _find_best_matching_image instead.
        """
        if not self.model:
            logger.warning("Gemini Vision not available, skipping validation")
            return images

        validated = []

        # Validate sequentially to avoid rate limits
        for idx, img in enumerate(images, 1):
            try:
                is_valid, confidence, reason = await self._validate_single_image(
                    img["bytes"], min_confidence
                )

                logger.debug(
                    f"[{idx}/{len(images)}] Image validation: "
                    f"valid={is_valid}, confidence={confidence:.2f}, reason={reason}"
                )

                if is_valid:
                    validated.append(img)
                else:
                    logger.debug(
                        f"Image {img['index']} (page {img['page']}) rejected: {reason}"
                    )

            except Exception as e:
                logger.warning(f"Failed to validate image {idx}: {e}")
                # On validation error, skip the image (conservative approach)
                continue

        return validated

    async def _validate_single_image(
        self,
        image_bytes: bytes,
        min_confidence: float = 0.6,
    ) -> tuple[bool, float, str]:
        """
        Validate a single image using Gemini Vision.

        Args:
            image_bytes: Raw image bytes
            min_confidence: Minimum confidence threshold

        Returns:
            Tuple of (is_valid, confidence, reason)
        """
        if not self.model:
            return False, 0.0, "Gemini Vision not initialized"

        try:
            import base64

            # Encode image to base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # Call Gemini Vision
            response = await asyncio.to_thread(
                self.model.generate_content,
                [
                    PRODUCT_IMAGE_VALIDATION_PROMPT,
                    {
                        "mime_type": "image/png",
                        "data": image_base64,
                    },
                ],
            )

            # Parse response
            response_text = response.text.strip()
            logger.debug(f"Gemini Vision response: {response_text}")

            # Extract JSON
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start == -1 or json_end <= json_start:
                logger.warning("Could not find JSON in Gemini response")
                return False, 0.0, "无法解析响应"

            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)

            is_valid = result.get("is_product_sample", False)
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "未知原因")

            # Check confidence threshold
            if is_valid and confidence >= min_confidence:
                return True, confidence, reason

            return False, confidence, reason

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini Vision JSON: {e}")
            return False, 0.0, f"JSON解析失败"
        except Exception as e:
            logger.error(f"Gemini Vision validation error: {e}")
            raise


# Global matcher instance
_matcher_instance: Optional[ImageMatcherService] = None


def get_image_matcher(enable_vision_validation: bool = True) -> ImageMatcherService:
    """
    Get or create image matcher instance.

    Args:
        enable_vision_validation: Whether to enable Vision validation

    Returns:
        ImageMatcherService instance
    """
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = ImageMatcherService(enable_vision_validation)
    return _matcher_instance
