"""Deterministic image matching based on page location and image area.

Core principle: Rules over predictions
- Extract item location from PDF structure
- Select largest image from target page (usually product sample)
- No AI/Vision API needed - deterministic and reliable

Algorithm:
1. Indexing: Build Item No. → Page mapping during PDF parsing
2. Targeting: For each item on page N, target page N+1
3. Visual Filtering: Apply exclusion rules from Skill config (logo, swatch, etc.)
"""

import logging
from collections import defaultdict
from functools import lru_cache
from typing import Any, Optional

from ..models import BOQItem

logger = logging.getLogger(__name__)

# Default minimum image area threshold (in pixels)
# Logos/icons are typically < 10000, actual products > 20000
# Used as fallback when Skill config is unavailable
MIN_PRODUCT_IMAGE_AREA = 10000

# Default exclusion rules (fallback when Skill config unavailable)
DEFAULT_EXCLUSION_RULES = [
    {
        "type": "logo",
        "description": "Small images (logos/icons)",
        "rules": {"max_area_px": 10000},
    }
]


class DeterministicImageMatcher:
    """Image matcher using page location and image size (no AI needed).

    Supports configurable exclusion rules via Skill config:
    - logo: Filter by max area
    - material_swatch: Filter by max dimensions
    - technical_drawing: Filter by saturation (not yet implemented)
    - hardware_detail: Filter by max area ratio
    """

    def __init__(self, vendor_id: Optional[str] = None):
        """Initialize deterministic matcher.

        Args:
            vendor_id: Optional vendor ID to load exclusion rules from Skill config.
                       If None, uses default rules (MIN_PRODUCT_IMAGE_AREA filter).
        """
        self.vendor_id = vendor_id
        self._exclusion_rules: Optional[list[dict]] = None
        self._min_area_px: int = MIN_PRODUCT_IMAGE_AREA

        # Load Skill config if vendor_id provided
        if vendor_id:
            self._load_skill_config(vendor_id)

        logger.info(
            f"DeterministicImageMatcher initialized "
            f"(vendor={vendor_id or 'default'}, min_area={self._min_area_px}px)"
        )

    def _load_skill_config(self, vendor_id: str) -> None:
        """Load exclusion rules from Skill config.

        Falls back to default rules if loading fails.
        """
        try:
            from .skill_loader import get_skill_loader

            loader = get_skill_loader()
            skill = loader.load_vendor_or_default(vendor_id)

            if skill is None:
                logger.warning(f"Skill config not found for {vendor_id}, using defaults")
                return

            # Extract config values
            img_config = skill.image_extraction
            self._min_area_px = img_config.product_image.min_area_px
            self._exclusion_rules = [
                {"type": rule.type, "description": rule.description, "rules": rule.rules}
                for rule in img_config.exclusions
            ]

            logger.info(
                f"Loaded Skill config: min_area={self._min_area_px}px, "
                f"exclusion_rules={len(self._exclusion_rules)}"
            )

        except Exception as e:
            logger.warning(f"Failed to load Skill config: {e}, using defaults")
            self._exclusion_rules = None

    def _get_exclusion_rules(self) -> list[dict]:
        """Get exclusion rules (from Skill or default)."""
        if self._exclusion_rules is not None:
            return self._exclusion_rules
        return DEFAULT_EXCLUSION_RULES

    def _should_exclude_image(self, img: dict[str, Any], page_area: Optional[int] = None) -> tuple[bool, str]:
        """Check if image should be excluded based on rules.

        Args:
            img: Image dict with width, height, page, index
            page_area: Total page area for ratio calculations (optional)

        Returns:
            Tuple of (should_exclude, reason)
        """
        area = img["width"] * img["height"]
        rules = self._get_exclusion_rules()

        for rule in rules:
            rule_type = rule.get("type", "")
            rule_config = rule.get("rules", {})

            # Check max_area_px rule
            max_area = rule_config.get("max_area_px")
            if max_area is not None and area < max_area:
                return True, f"{rule_type}: area {area}px² < {max_area}px²"

            # Check max_area_ratio rule (requires page_area)
            max_ratio = rule_config.get("max_area_ratio")
            if max_ratio is not None and page_area is not None:
                img_ratio = area / page_area
                if img_ratio < max_ratio:
                    return True, f"{rule_type}: ratio {img_ratio:.3f} < {max_ratio}"

            # Check max_width_px / max_height_px rules
            max_width = rule_config.get("max_width_px")
            max_height = rule_config.get("max_height_px")
            if max_width is not None and max_height is not None:
                if img["width"] <= max_width and img["height"] <= max_height:
                    return True, f"{rule_type}: size {img['width']}x{img['height']} within {max_width}x{max_height}"

        return False, ""

    def _is_product_image(self, img: dict[str, Any]) -> bool:
        """Check if image meets product image criteria.

        Args:
            img: Image dict with width, height, page, index

        Returns:
            True if image is large enough to be a product image
        """
        area = img["width"] * img["height"]
        return area >= self._min_area_px

    async def match_images_to_items(
        self,
        images: list[dict],
        boq_items: list[BOQItem],
        target_page_offset: int = 1,
    ) -> dict[int, str]:
        """
        Match images to BOQ items using deterministic page+size algorithm.

        Algorithm:
        1. Build page-to-item index
        2. For each item on page N, find images on page N+target_page_offset
        3. Apply exclusion rules from Skill config
        4. Select largest-area image from remaining candidates

        Args:
            images: List of dicts with {bytes, width, height, page, index}
            boq_items: List of BOQItem objects with source_page
            target_page_offset: Look for images target_page_offset pages ahead (default: 1)

        Returns:
            Dict mapping image index to BOQ item ID
        """
        if not images or not boq_items:
            logger.info("No images or items to match")
            return {}

        logger.info(
            f"Deterministic matching: {len(boq_items)} items, {len(images)} images, "
            f"target_page_offset={target_page_offset}, vendor={self.vendor_id or 'default'}"
        )

        # Step 1: Build item location index
        item_by_page = defaultdict(list)
        for item in boq_items:
            item_page = item.source_page or 1
            item_by_page[item_page].append(item)
            logger.debug(f"Item {item.item_no} on page {item_page}")

        # Step 2: Build image index by page (with exclusion filtering)
        images_by_page = defaultdict(list)
        excluded_count = 0

        for img in images:
            page = img["page"]
            area = img["width"] * img["height"]

            # Apply exclusion rules
            excluded, reason = self._should_exclude_image(img)
            if excluded:
                logger.debug(f"Excluded image {img['index']} on page {page}: {reason}")
                excluded_count += 1
                continue

            # Check minimum area threshold
            if not self._is_product_image(img):
                logger.debug(
                    f"Excluded image {img['index']} on page {page}: "
                    f"area {area}px² < min {self._min_area_px}px²"
                )
                excluded_count += 1
                continue

            images_by_page[page].append((img, area))
            logger.debug(
                f"Image {img['index']} on page {page}: {img['width']}x{img['height']} = {area} px²"
            )

        if excluded_count > 0:
            logger.info(f"Excluded {excluded_count} images by filtering rules")

        # Step 3: Sort images by page, keeping track of area
        for page in images_by_page:
            images_by_page[page].sort(key=lambda x: x[1], reverse=True)

        # Step 4: Match items to images
        mapping = {}
        used_images = set()

        for source_page, items_on_page in item_by_page.items():
            # Target page: source_page + offset
            target_page = source_page + target_page_offset
            candidates = images_by_page.get(target_page, [])

            if not candidates:
                logger.warning(
                    f"No images found on page {target_page} "
                    f"for {len(items_on_page)} items from page {source_page}"
                )
                continue

            logger.info(
                f"Page {source_page} ({len(items_on_page)} items) → "
                f"Page {target_page} ({len(candidates)} images)"
            )

            # Match items from this page to images on target page
            for item_idx, item in enumerate(items_on_page):
                # Find largest unused image
                best_image = None
                best_area = 0

                for img, area in candidates:
                    if img["index"] not in used_images and area > best_area:
                        best_image = img
                        best_area = area

                if best_image:
                    mapping[best_image["index"]] = item.id
                    used_images.add(best_image["index"])

                    logger.info(
                        f"✓ {item.item_no}: image {best_image['index']} "
                        f"({best_image['width']}x{best_image['height']} = {best_area} px²)"
                    )
                else:
                    logger.warning(f"No available images for {item.item_no}")

        logger.info(
            f"Deterministic matching complete: {len(mapping)}/{len(boq_items)} items matched"
        )
        return mapping


# Global instance (default, no vendor-specific config)
_matcher_instance: Optional[DeterministicImageMatcher] = None


def get_deterministic_image_matcher(vendor_id: Optional[str] = None) -> DeterministicImageMatcher:
    """Get or create deterministic image matcher instance.

    Args:
        vendor_id: Optional vendor ID for Skill-based configuration.
                   If provided, creates a new instance with vendor config.
                   If None, returns/creates default instance.

    Returns:
        DeterministicImageMatcher instance
    """
    global _matcher_instance

    # If vendor_id specified, create vendor-specific instance
    if vendor_id is not None:
        return DeterministicImageMatcher(vendor_id=vendor_id)

    # Otherwise, return default singleton
    if _matcher_instance is None:
        _matcher_instance = DeterministicImageMatcher()
    return _matcher_instance
