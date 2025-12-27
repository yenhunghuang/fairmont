"""Excel generation service for Fairmont format quotations.

完全比照惠而蒙格式 Excel 範本 15 欄:
A: NO., B: Item no., C: Description, D: Photo, E: Dimension WxDxH (mm),
F: Qty, G: UOM, H: Unit Rate (留空), I: Amount (留空), J: Unit CBM,
K: Total CBM (公式), L: Note, M: Location, N: Materials Used / Specs, O: Brand
"""

import base64
import logging
import uuid
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..config import settings
from ..models import BOQItem, Quotation
from ..utils import ErrorCode, FileManager, raise_error

logger = logging.getLogger(__name__)


class ExcelGeneratorService:
    """Service for generating Excel quotations in Fairmont format (15 columns)."""

    # Fairmont format column headers (15 columns per template)
    # Format: (header_text, field_name, column_width)
    COLUMNS = [
        ("NO.", "no", 5),                          # A: 序號
        ("Item no.", "item_no", 13),               # B: 項目編號
        ("Description", "description", 20),        # C: 描述
        ("Photo", "photo", 15),                    # D: 圖片 (Base64)
        ("Dimension\nWxDxH (mm)", "dimension", 18),  # E: 尺寸
        ("Qty", "qty", 8),                         # F: 數量
        ("UOM", "uom", 6),                         # G: 單位
        ("Unit Rate\n(USD)", "unit_rate", 12),    # H: 單價 (留空)
        ("Amount\n(USD)", "amount", 12),          # I: 金額 (留空)
        ("Unit\nCBM", "unit_cbm", 8),             # J: 單位材積
        ("Total\nCBM", "total_cbm", 8),           # K: 總材積 (公式)
        ("Note", "note", 20),                      # L: 備註
        ("Location", "location", 15),              # M: 位置
        ("Materials Used / Specs", "materials_specs", 20),  # N: 材料規格
        ("Brand", "brand", 12),                    # O: 品牌
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
        items: list[BOQItem],
        include_photos: bool = True,
        photo_height_cm: float = 3.0,
    ) -> None:
        """Add items to worksheet (15 columns per Fairmont template)."""
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )
        center_alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
        left_alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        right_alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)

        # Calculate photo size in pixels (assuming 96 DPI)
        # 1 cm = ~37.8 pixels at 96 DPI
        photo_height_px = int(photo_height_cm * 37.8)

        for row_num, item in enumerate(items, 2):  # Start from row 2 (after header)
            # A: NO.
            cell = ws.cell(row=row_num, column=1)
            cell.value = item.no
            cell.alignment = center_alignment
            cell.border = thin_border

            # B: Item no.
            cell = ws.cell(row=row_num, column=2)
            cell.value = item.item_no
            cell.alignment = left_alignment
            cell.border = thin_border

            # C: Description
            cell = ws.cell(row=row_num, column=3)
            cell.value = item.description
            cell.alignment = left_alignment
            cell.border = thin_border

            # D: Photo (Base64)
            if include_photos and item.photo_base64:
                self._embed_base64_photo(ws, row_num, 4, item.photo_base64, photo_height_px)
            else:
                cell = ws.cell(row=row_num, column=4)
                cell.value = ""
                cell.alignment = center_alignment
                cell.border = thin_border

            # E: Dimension WxDxH (mm)
            cell = ws.cell(row=row_num, column=5)
            cell.value = item.dimension or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # F: Qty
            cell = ws.cell(row=row_num, column=6)
            if item.qty is not None:
                cell.value = item.qty
                cell.number_format = "0"
            cell.alignment = center_alignment
            cell.border = thin_border

            # G: UOM
            cell = ws.cell(row=row_num, column=7)
            cell.value = item.uom or ""
            cell.alignment = center_alignment
            cell.border = thin_border

            # H: Unit Rate (USD) - 留空，使用者填寫
            cell = ws.cell(row=row_num, column=8)
            cell.value = ""
            cell.alignment = right_alignment
            cell.border = thin_border

            # I: Amount (USD) - 留空，使用者填寫
            cell = ws.cell(row=row_num, column=9)
            cell.value = ""
            cell.alignment = right_alignment
            cell.border = thin_border

            # J: Unit CBM
            cell = ws.cell(row=row_num, column=10)
            if item.unit_cbm is not None:
                cell.value = item.unit_cbm
                cell.number_format = "0.00"
            cell.alignment = center_alignment
            cell.border = thin_border

            # K: Total CBM (公式: =F*J)
            cell = ws.cell(row=row_num, column=11)
            if item.unit_cbm is not None and item.qty is not None:
                cell.value = f"=F{row_num}*J{row_num}"
                cell.number_format = "0.00"
            cell.alignment = center_alignment
            cell.border = thin_border

            # L: Note
            cell = ws.cell(row=row_num, column=12)
            cell.value = item.note or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # M: Location
            cell = ws.cell(row=row_num, column=13)
            cell.value = item.location or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # N: Materials Used / Specs
            cell = ws.cell(row=row_num, column=14)
            cell.value = item.materials_specs or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # O: Brand
            cell = ws.cell(row=row_num, column=15)
            cell.value = item.brand or ""
            cell.alignment = left_alignment
            cell.border = thin_border

            # Set fixed row height for uniform layout (85px to fit 80px images + margin)
            FIXED_ROW_HEIGHT = 85
            ws.row_dimensions[row_num].height = FIXED_ROW_HEIGHT

    def _embed_base64_photo(
        self,
        ws,
        row_num: int,
        col_num: int,
        photo_base64: str,
        photo_height_px: int,
    ) -> None:
        """Embed Base64 encoded photo in worksheet with fixed dimensions."""
        # Fixed dimensions for uniform Excel layout
        FIXED_WIDTH = 100
        FIXED_HEIGHT = 80

        try:
            # Remove data URI prefix if present
            if photo_base64.startswith("data:"):
                photo_base64 = photo_base64.split(",", 1)[1]

            # Decode Base64 to bytes
            image_bytes = base64.b64decode(photo_base64)
            image_stream = BytesIO(image_bytes)

            # Create Excel image object from bytes
            img = XLImage(image_stream)

            # Set fixed width and height (may stretch/compress image)
            img.width = FIXED_WIDTH
            img.height = FIXED_HEIGHT

            # Get column letter and position
            col_letter = get_column_letter(col_num)
            cell_ref = f"{col_letter}{row_num}"

            # Add image to worksheet
            ws.add_image(img, cell_ref)

            logger.debug(f"Embedded Base64 photo in cell {cell_ref} ({FIXED_WIDTH}x{FIXED_HEIGHT}px)")

        except Exception as e:
            logger.warning(f"Failed to embed Base64 photo: {e}")
            cell = ws.cell(row=row_num, column=col_num)
            cell.value = "[圖片嵌入失敗]"

    def _embed_photo(
        self,
        ws,
        row_num: int,
        col_num: int,
        photo_path: str,
        photo_height_px: int,
    ) -> None:
        """Embed photo from file path in worksheet (legacy support)."""
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
        Validate generated Excel file (15 columns per Fairmont format).

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

            # Check headers (15 columns)
            expected_headers = [col[0] for col in self.COLUMNS]
            actual_headers = [cell.value for cell in ws[1]]

            # Compare first 15 columns
            if actual_headers[:15] != expected_headers:
                logger.warning(
                    f"Header mismatch. Expected: {expected_headers}, "
                    f"Actual: {actual_headers[:15]}"
                )
                raise ValueError("Headers do not match Fairmont format (15 columns)")

            # Check at least one data row
            if ws.max_row < 2:
                raise ValueError("No data rows in worksheet")

            logger.info(f"Excel file validated: {file_path} (15 columns)")
            return True

        except Exception as e:
            logger.error(f"Excel validation failed: {e}")
            raise_error(
                ErrorCode.EXPORT_FAILED,
                "Excel 驗證失敗",
            )


@lru_cache(maxsize=1)
def get_excel_generator() -> ExcelGeneratorService:
    """Get or create Excel generator instance (thread-safe via lru_cache)."""
    return ExcelGeneratorService()
