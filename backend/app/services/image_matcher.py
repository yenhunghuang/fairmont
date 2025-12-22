"""Image matching service with Gemini Vision validation.

Strategy:
1. Filter to large images only (≥8000 pixels) as candidates
2. Use Gemini Vision to validate each image is a product sample (not logo/design)
3. For each BOQ item, match first validated large image on same/next page
4. Return only images that pass product validation
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

# Gemini Vision validation prompt
PRODUCT_IMAGE_VALIDATION_PROMPT = """请分析这张图片，判断它是否是家具/家居产品的实物样品或展示照片。

评估标准：
1. 是否清晰可见实际的家具/产品样式、形状、颜色、材质？
2. 是否是产品样品照片或展示图（而非设计图、CAD图纸、平面图、技术图纸）？
3. 是否NOT是纯Logo、Icon、品牌标记或装饰性图案？
4. 是否NOT是文字说明图、信息图或表格？
5. 图片内容是否与家具/家居产品相关？

请返回以下JSON格式的判断结果，不要包含其他文本：
{
  "is_product_sample": true或false,
  "confidence": 0.0到1.0之间的置信度,
  "reason": "简短说明（中文，最多一句）"
}

如果无法判断，返回 is_product_sample: false"""


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
        Match images to BOQ items with optional Gemini Vision validation.

        Strategy:
        1. Filter to large images (≥8000 pixels)
        2. Optionally validate each using Gemini Vision (is it a product sample?)
        3. For each BOQ item, find first validated image on same/next page
        4. Return mapping of image index to BOQ item ID

        Args:
            images: List of dicts with {bytes, width, height, page, index}
            boq_items: List of BOQItem objects
            validate_product_images: Whether to use Vision validation
            min_confidence: Minimum confidence threshold for product validation

        Returns:
            Dict mapping image index to BOQ item ID
        """
        if not images or not boq_items:
            logger.info("No images or items to match")
            return {}

        # 1. Filter to large images
        large_images = [
            img for img in images
            if img["width"] * img["height"] >= MIN_LARGE_IMAGE_AREA
        ]

        if not large_images:
            logger.warning("No large images found for matching")
            return {}

        logger.info(f"Found {len(large_images)} large images for {len(boq_items)} items")

        # 2. Validate images if enabled
        validated_images = large_images
        if validate_product_images and self.enable_vision_validation:
            logger.info("Starting Gemini Vision validation of product images...")
            validated_images = await self._validate_images_batch(
                large_images, min_confidence
            )
            logger.info(
                f"Validated {len(validated_images)}/{len(large_images)} images "
                f"as product samples"
            )

        if not validated_images:
            logger.warning("No images passed product sample validation")
            return {}

        # 3. Sort by page and index
        validated_images.sort(key=lambda x: (x["page"], x["index"]))

        # 4. Group by page
        images_by_page = defaultdict(list)
        for img in validated_images:
            images_by_page[img["page"]].append(img)

        # 5. Match images to items
        mapping = {}
        used_images = set()

        for item in boq_items:
            item_page = item.source_page or 1

            # Find first unused validated image on same page or next page
            matched = False
            for page in [item_page, item_page + 1]:
                if matched:
                    break
                for img in images_by_page.get(page, []):
                    if img["index"] not in used_images:
                        mapping[img["index"]] = item.id
                        used_images.add(img["index"])
                        matched = True
                        logger.debug(
                            f"Matched image {img['index']} (page {img['page']}) "
                            f"to item {item.item_no}"
                        )
                        break

        logger.info(f"Matched {len(mapping)} validated images to items")
        return mapping

    async def _validate_images_batch(
        self,
        images: list[dict],
        min_confidence: float = 0.6,
    ) -> list[dict]:
        """
        Validate images using Gemini Vision API (batch mode for efficiency).

        Args:
            images: List of image dicts with bytes
            min_confidence: Minimum confidence threshold

        Returns:
            List of validated images (subset of input images)
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
