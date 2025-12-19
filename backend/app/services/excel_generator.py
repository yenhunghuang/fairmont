"""Excel generation service for Fairmont format quotations."""

import logging
from pathlib import Path
from typing import List, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter
import uuid

from ..models import Quotation, BOQItem
from ..utils import ErrorCode, raise_error, FileManager
from ..config import settings

logger = logging.getLogger(__name__)


class ExcelGeneratorService:
    """Service for generating Excel quotations in Fairmont format."""

    # Fairmont format column headers (10 columns)
    COLUMNS = [
        ("NO.", "no", 5),  # Column width
        ("Item No.", "item_no", 12),
        ("Description", "description", 25),
        ("Photo", "photo", 15),
        ("Dimension", "dimension", 15),
        ("Qty", "qty", 8),
        ("UOM", "uom", 8),
        ("Note", "note", 15),
        ("Location", "location", 15),
        ("Materials Used / Specs", "materials_specs", 25),
    ]

    def __init__(self):
        """Initialize Excel generator service."""
        self.file_manager = FileManager(
            temp_dir=settings.temp_dir_path,
            images_dir=settings.extracted_images_dir_path,
        )

    def create_quotation_excel(
        self,
        quotation: Quotation,
        include_photos: bool = True,
        photo_height_cm: float = 3.0,
    ) -> str:
        """
        Create Excel file for quotation.

        Args:
            quotation: Quotation object with items
            include_photos: Whether to embed photos
            photo_height_cm: Photo height in centimeters

        Returns:
            Path to generated Excel file

        Raises:
            APIError: If generation fails
        """
        try:
            # Create workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "報價單"

            # Set column widths and create headers
            self._create_header_row(ws)

            # Add items
            self._add_items_to_sheet(ws, quotation.items, include_photos, photo_height_cm)

            # Generate filename and save
            filename = f"quotation_{quotation.id}_{uuid.uuid4().hex[:8]}.xlsx"
            file_path = self.file_manager.temp_dir / filename

            wb.save(str(file_path))
            logger.info(f"Excel file created: {file_path}")

            return str(file_path)

        except Exception as e:
            logger.error(f"Excel generation failed: {e}")
            raise_error(
                ErrorCode.EXPORT_FAILED,
                f"Excel 生成失敗：{str(e)}",
            )

    def _create_header_row(self, ws) -> None:
        """Create header row with formatting."""
        # Header styling
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # Add headers
        for col_num, (header_text, _, width) in enumerate(self.COLUMNS, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header_text
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_num)].width = width

        ws.row_dimensions[1].height = 25

    def _add_items_to_sheet(
        self,
        ws,
        items: List[BOQItem],
        include_photos: bool = True,
        photo_height_cm: float = 3.0,
    ) -> None:
        """Add items to worksheet."""
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )
        center_alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        left_alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

        # Calculate photo size in pixels (assuming 96 DPI)
        # 1 cm = ~37.8 pixels at 96 DPI
        photo_height_px = int(photo_height_cm * 37.8)

        for row_num, item in enumerate(items, 2):  # Start from row 2 (after header)
            # NO.
            cell = ws.cell(row=row_num, column=1)
            cell.value = item.no
            cell.alignment = center_alignment
            cell.border = thin_border

            # Item No.
            cell = ws.cell(row=row_num, column=2)
            cell.value = item.item_no
            cell.alignment = left_alignment
            cell.border = thin_border

            # Description
            cell = ws.cell(row=row_num, column=3)
            cell.value = item.description
            cell.alignment = left_alignment
            cell.border = thin_border

            # Photo
            if include_photos and item.photo_path:
                self._embed_photo(ws, row_num, 4, item.photo_path, photo_height_px)
            else:
                cell = ws.cell(row=row_num, column=4)
                cell.value = "[無圖片]" if not item.photo_path else ""
                cell.alignment = center_alignment
                cell.border = thin_border

            # Dimension
            cell = ws.cell(row=row_num, column=5)
            cell.value = item.dimension or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # Qty
            cell = ws.cell(row=row_num, column=6)
            if item.qty is not None:
                cell.value = item.qty
                cell.number_format = "0.00"
            cell.alignment = center_alignment
            cell.border = thin_border

            # UOM
            cell = ws.cell(row=row_num, column=7)
            cell.value = item.uom or ""
            cell.alignment = center_alignment
            cell.border = thin_border

            # Note
            cell = ws.cell(row=row_num, column=8)
            cell.value = item.note or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # Location
            cell = ws.cell(row=row_num, column=9)
            cell.value = item.location or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # Materials Used / Specs
            cell = ws.cell(row=row_num, column=10)
            cell.value = item.materials_specs or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # Set row height based on content
            row_height = 20
            if include_photos and item.photo_path:
                row_height = max(row_height, photo_height_px + 5)
            ws.row_dimensions[row_num].height = row_height

    def _embed_photo(
        self,
        ws,
        row_num: int,
        col_num: int,
        photo_path: str,
        photo_height_px: int,
    ) -> None:
        """Embed photo in worksheet."""
        try:
            path = Path(photo_path)
            if not path.exists():
                logger.warning(f"Photo not found: {photo_path}")
                cell = ws.cell(row=row_num, column=col_num)
                cell.value = "[圖片不存在]"
                return

            # Create Excel image object
            img = XLImage(str(path))

            # Set height (width will be proportional)
            img.height = photo_height_px
            # Calculate width based on aspect ratio
            from PIL import Image as PILImage
            pil_img = PILImage.open(path)
            aspect_ratio = pil_img.width / pil_img.height
            img.width = int(photo_height_px * aspect_ratio)

            # Get column letter and position
            col_letter = get_column_letter(col_num)
            cell_ref = f"{col_letter}{row_num}"

            # Add image to worksheet
            ws.add_image(img, cell_ref)

            logger.info(f"Embedded photo in cell {cell_ref}")

        except Exception as e:
            logger.warning(f"Failed to embed photo: {e}")
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = "[圖片嵌入失敗]"

    def update_quotation_excel(
        self,
        file_path: str,
        quotation: Quotation,
    ) -> None:
        """
        Update existing Excel file with new items.

        Args:
            file_path: Path to Excel file
            quotation: Updated quotation with items

        Raises:
            APIError: If update fails
        """
        try:
            from openpyxl import load_workbook

            wb = load_workbook(file_path)
            ws = wb.active

            # Clear existing items (keep header)
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
                for cell in row:
                    cell.value = None

            # Add updated items
            self._add_items_to_sheet(ws, quotation.items)

            wb.save(file_path)
            logger.info(f"Excel file updated: {file_path}")

        except Exception as e:
            logger.error(f"Excel update failed: {e}")
            raise_error(
                ErrorCode.EXPORT_FAILED,
                "Excel 更新失敗",
            )

    def validate_excel_file(self, file_path: str) -> bool:
        """
        Validate generated Excel file.

        Args:
            file_path: Path to Excel file

        Returns:
            True if valid

        Raises:
            APIError: If invalid
        """
        try:
            from openpyxl import load_workbook

            wb = load_workbook(file_path)
            ws = wb.active

            # Check headers
            expected_headers = [col[0] for col in self.COLUMNS]
            actual_headers = [cell.value for cell in ws[1]]

            if actual_headers[:10] != expected_headers:
                raise ValueError("Headers do not match Fairmont format")

            # Check at least one data row
            if ws.max_row < 2:
                raise ValueError("No data rows in worksheet")

            logger.info(f"Excel file validated: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Excel validation failed: {e}")
            raise_error(
                ErrorCode.EXPORT_FAILED,
                "Excel 驗證失敗",
            )


# Global generator instance
_generator_instance: ExcelGeneratorService = None


def get_excel_generator() -> ExcelGeneratorService:
    """Get or create Excel generator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ExcelGeneratorService()
    return _generator_instance
