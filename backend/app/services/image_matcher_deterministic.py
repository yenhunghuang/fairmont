"""Deterministic image matching based on page location and image area.

Core principle: Rules over predictions
- Extract item location from PDF structure
- Select largest image from target page (usually product sample)
- No AI/Vision API needed - deterministic and reliable

Algorithm:
1. Indexing: Build Item No. → Page mapping during PDF parsing
2. Targeting: For each item on page N, target page N+1
3. Visual Filtering: Select largest area image (excludes small logos/icons)
"""

import logging
from collections import defaultdict
from typing import Optional

from ..models import BOQItem

logger = logging.getLogger(__name__)

# Minimum image area threshold (in pixels)
# Logos/icons are typically < 10000, actual products > 20000
MIN_PRODUCT_IMAGE_AREA = 10000


class DeterministicImageMatcher:
    """Image matcher using page location and image size (no AI needed)."""

    def __init__(self):
        """Initialize deterministic matcher."""
        logger.info("DeterministicImageMatcher initialized (rule-based, no Vision API)")

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
        3. Select largest-area image from candidates
        4. Automatic logo filtering: logos are small, products are large

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
            f"target_page_offset={target_page_offset}"
        )

        # Step 1: Build item location index
        item_by_page = defaultdict(list)
        for item in boq_items:
            item_page = item.source_page or 1
            item_by_page[item_page].append(item)
            logger.debug(f"Item {item.item_no} on page {item_page}")

        # Step 2: Build image index by page
        images_by_page = defaultdict(list)
        for img in images:
            page = img["page"]
            area = img["width"] * img["height"]
            images_by_page[page].append((img, area))
            logger.debug(
                f"Image {img['index']} on page {page}: {img['width']}x{img['height']} = {area} px²"
            )

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
                    # Check if image is large enough to be product (not logo)
                    if best_area >= MIN_PRODUCT_IMAGE_AREA:
                        mapping[best_image["index"]] = item.id
                        used_images.add(best_image["index"])

                        logger.info(
                            f"✓ {item.item_no}: image {best_image['index']} "
                            f"({best_image['width']}x{best_image['height']} = {best_area} px²)"
                        )
                    else:
                        logger.warning(
                            f"✗ {item.item_no}: largest image {best_area} px² "
                            f"< threshold {MIN_PRODUCT_IMAGE_AREA} px² (likely logo/icon)"
                        )
                else:
                    logger.warning(f"No available images for {item.item_no}")

        logger.info(
            f"Deterministic matching complete: {len(mapping)}/{len(boq_items)} items matched"
        )
        return mapping


# Global instance
_matcher_instance: Optional[DeterministicImageMatcher] = None


def get_deterministic_image_matcher() -> DeterministicImageMatcher:
    """Get or create deterministic image matcher instance."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = DeterministicImageMatcher()
    return _matcher_instance
