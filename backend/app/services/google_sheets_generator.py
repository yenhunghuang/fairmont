"""Google Sheets generation service for Fairmont format quotations.

Generates Google Sheets quotations with the same 15-column Fairmont format
as the Excel generator, using IMAGE() function for photos.
"""

import logging
import time
from typing import List, Optional, Literal

from pydantic import BaseModel
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from ..models import Quotation, BOQItem
from ..config import settings
from ..utils import ErrorCode, raise_error
from .google_drive_service import get_google_drive_service, GoogleDriveService

logger = logging.getLogger(__name__)

# Google API scopes required
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleSheetsResult(BaseModel):
    """Result of Google Sheets creation."""

    spreadsheet_id: str
    spreadsheet_url: str
    shareable_link: str
    sheet_id: Optional[int] = None  # Individual sheet/tab ID
    sheet_name: Optional[str] = None  # Sheet name
    drive_folder_id: Optional[str] = None
    image_count: int = 0


class GoogleSheetsGeneratorService:
    """Service for generating Google Sheets quotations in Fairmont format (15 columns)."""

    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds

    # Fairmont format column headers (15 columns per template)
    # Same as ExcelGeneratorService
    COLUMNS = [
        ("NO.", "no", 50),                          # A: 序號
        ("Item no.", "item_no", 100),               # B: 項目編號
        ("Description", "description", 200),        # C: 描述
        ("Photo", "photo", 120),                    # D: 圖片 (IMAGE formula)
        ("Dimension\nWxDxH (mm)", "dimension", 130),  # E: 尺寸
        ("Qty", "qty", 60),                         # F: 數量
        ("UOM", "uom", 50),                         # G: 單位
        ("Unit Rate\n(USD)", "unit_rate", 90),     # H: 單價 (留空)
        ("Amount\n(USD)", "amount", 90),           # I: 金額 (留空)
        ("Unit\nCBM", "unit_cbm", 70),             # J: 單位材積
        ("Total\nCBM", "total_cbm", 70),           # K: 總材積 (公式)
        ("Note", "note", 150),                      # L: 備註
        ("Location", "location", 100),              # M: 位置
        ("Materials Used / Specs", "materials_specs", 150),  # N: 材料規格
        ("Brand", "brand", 100),                    # O: 品牌
    ]

    def __init__(self):
        """Initialize Google Sheets generator service."""
        self._service: Optional[Resource] = None
        self._drive_service: Optional[GoogleDriveService] = None

    def _get_service(self) -> Resource:
        """Get or create Sheets API service instance."""
        if self._service is None:
            self._service = self._authenticate()
        return self._service

    def _get_drive_service(self) -> GoogleDriveService:
        """Get Google Drive service for image uploads."""
        if self._drive_service is None:
            self._drive_service = get_google_drive_service()
        return self._drive_service

    def _authenticate(self) -> Resource:
        """Authenticate using Service Account JSON."""
        try:
            creds_path = settings.google_credentials_path_resolved
            if not creds_path or not creds_path.exists():
                raise_error(
                    ErrorCode.GOOGLE_AUTH_FAILED,
                    "找不到 Google 服務帳號憑證檔案",
                    status_code=500,
                )

            credentials = service_account.Credentials.from_service_account_file(
                str(creds_path),
                scopes=SCOPES,
            )

            service = build("sheets", "v4", credentials=credentials)
            logger.info("Google Sheets API authenticated successfully")
            return service

        except Exception as e:
            if "GOOGLE_AUTH_FAILED" in str(e):
                raise
            logger.error(f"Google Sheets authentication failed: {e}")
            raise_error(
                ErrorCode.GOOGLE_AUTH_FAILED,
                f"Google Sheets API 認證失敗：{str(e)}",
                status_code=500,
            )

    def _execute_with_retry(self, request):
        """Execute API request with exponential backoff."""
        for attempt in range(self.MAX_RETRIES):
            try:
                return request.execute()
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {delay}s before retry")
                    time.sleep(delay)
                elif e.resp.status == 403:  # Quota exceeded
                    raise_error(
                        ErrorCode.GOOGLE_QUOTA_EXCEEDED,
                        "Google API 配額已用盡，請稍後重試",
                        status_code=503,
                    )
                else:
                    raise
        raise_error(
            ErrorCode.GOOGLE_API_ERROR,
            "Google Sheets API 請求失敗",
            status_code=500,
        )

    def create_quotation_sheet(
        self,
        quotation: Quotation,
        include_photos: bool = True,
        share_mode: Literal["view", "edit"] = "view",
    ) -> GoogleSheetsResult:
        """
        Create Google Sheets for quotation.

        Uses the master spreadsheet approach: adds a new sheet (tab) to
        the master spreadsheet instead of creating a new file.

        Args:
            quotation: Quotation object with items
            include_photos: Whether to upload and embed photos
            share_mode: "view" for read-only, "edit" for editable

        Returns:
            GoogleSheetsResult with URLs and metadata

        Raises:
            APIError: If creation fails
        """
        try:
            # Check if Google Sheets is available
            if not settings.google_sheets_available:
                raise_error(
                    ErrorCode.GOOGLE_SHEETS_DISABLED,
                    "Google Sheets 整合未啟用，請設定環境變數",
                    status_code=503,
                )

            # Get master spreadsheet ID
            master_id = settings.google_sheets_master_id
            if not master_id:
                raise_error(
                    ErrorCode.GOOGLE_SHEETS_DISABLED,
                    "未設定 Google Sheets 主試算表 ID",
                    status_code=503,
                )

            # Create a new sheet (tab) in master spreadsheet
            from datetime import datetime
            sheet_title = quotation.title or f"報價單_{quotation.id[:8]}"
            sheet_title = f"{sheet_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            sheet_id = self._add_sheet(master_id, sheet_title)

            # Get folder ID for images
            folder_id = settings.google_drive_folder_id or None
            image_count = 0

            # Write headers
            self._write_headers(master_id, sheet_title)

            # Write items
            image_count = self._write_items(
                master_id,
                sheet_title,
                quotation.items,
                include_photos,
                folder_id,
            )

            # Apply formatting
            self._format_sheet(master_id, sheet_id, len(quotation.items) + 1)

            # Set sharing (if not already set)
            shareable_link = self._set_sharing(master_id, share_mode, sheet_id)

            # Get spreadsheet URL with sheet ID
            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{master_id}/edit#gid={sheet_id}"

            logger.info(
                f"Created Google Sheets tab: {sheet_title} in {master_id} "
                f"(items: {len(quotation.items)}, images: {image_count})"
            )

            return GoogleSheetsResult(
                spreadsheet_id=master_id,
                spreadsheet_url=spreadsheet_url,
                shareable_link=shareable_link,
                sheet_id=sheet_id,
                sheet_name=sheet_title,
                drive_folder_id=folder_id,
                image_count=image_count,
            )

        except Exception as e:
            if any(code in str(e) for code in [
                "GOOGLE_AUTH_FAILED", "GOOGLE_QUOTA_EXCEEDED",
                "GOOGLE_API_ERROR", "GOOGLE_SHEETS_DISABLED"
            ]):
                raise
            logger.error(f"Google Sheets generation failed: {e}")
            raise_error(
                ErrorCode.EXPORT_FAILED,
                f"Google Sheets 生成失敗：{str(e)}",
            )

    def _add_sheet(self, spreadsheet_id: str, sheet_title: str) -> int:
        """Add a new sheet (tab) to existing spreadsheet and return sheet ID."""
        service = self._get_service()

        request = {
            "requests": [{
                "addSheet": {
                    "properties": {
                        "title": sheet_title,
                        "gridProperties": {
                            "frozenRowCount": 1,  # Freeze header row
                        },
                    }
                }
            }]
        }

        result = self._execute_with_retry(
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request,
            )
        )

        sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
        logger.info(f"Added sheet '{sheet_title}' with ID: {sheet_id}")
        return sheet_id

    def _write_headers(self, spreadsheet_id: str, sheet_title: str) -> None:
        """Write header row to spreadsheet."""
        service = self._get_service()

        headers = [[col[0] for col in self.COLUMNS]]

        self._execute_with_retry(
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_title}'!A1:O1",
                valueInputOption="RAW",
                body={"values": headers},
            )
        )

        logger.debug(f"Wrote headers to sheet '{sheet_title}'")

    def _write_items(
        self,
        spreadsheet_id: str,
        sheet_title: str,
        items: List[BOQItem],
        include_photos: bool,
        folder_id: Optional[str],
    ) -> int:
        """
        Write item rows to spreadsheet.

        Returns:
            Number of images successfully uploaded
        """
        service = self._get_service()
        drive_service = self._get_drive_service() if include_photos and folder_id else None

        rows = []
        image_count = 0

        for item in items:
            # Handle photo
            photo_cell = ""
            if include_photos and item.photo_base64 and folder_id and drive_service:
                # Upload image to Drive and get URL
                filename = f"item_{item.no or item.id[:8]}.png"
                image_url = drive_service.upload_base64_image(
                    item.photo_base64,
                    filename,
                    folder_id,
                )
                if image_url:
                    # Use IMAGE() function with custom size (mode 4)
                    # =IMAGE(url, mode, height, width)
                    photo_cell = f'=IMAGE("{image_url}", 4, 80, 100)'
                    image_count += 1

            # Build row data (15 columns)
            row = [
                item.no or "",                  # A: NO.
                item.item_no or "",             # B: Item no.
                item.description or "",         # C: Description
                photo_cell,                     # D: Photo (IMAGE formula or empty)
                item.dimension or "",           # E: Dimension
                item.qty if item.qty is not None else "",  # F: Qty
                item.uom or "",                 # G: UOM
                "",                             # H: Unit Rate (留空)
                "",                             # I: Amount (留空)
                item.unit_cbm if item.unit_cbm is not None else "",  # J: Unit CBM
                "",                             # K: Total CBM (will add formula)
                item.note or "",                # L: Note
                item.location or "",            # M: Location
                item.materials_specs or "",     # N: Materials Used / Specs
                item.brand or "",               # O: Brand
            ]
            rows.append(row)

        if not rows:
            return 0

        # Write all items at once
        end_row = len(rows) + 1
        self._execute_with_retry(
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_title}'!A2:O{end_row}",
                valueInputOption="USER_ENTERED",  # Allow formulas
                body={"values": rows},
            )
        )

        # Add Total CBM formulas (column K = F * J)
        formulas = []
        for row_num in range(2, end_row + 1):
            formulas.append([f"=IF(AND(F{row_num}<>\"\",J{row_num}<>\"\"),F{row_num}*J{row_num},\"\")"])

        if formulas:
            self._execute_with_retry(
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{sheet_title}'!K2:K{end_row}",
                    valueInputOption="USER_ENTERED",
                    body={"values": formulas},
                )
            )

        logger.debug(f"Wrote {len(rows)} items to sheet '{sheet_title}'")
        return image_count

    def _format_sheet(self, spreadsheet_id: str, sheet_id: int, row_count: int) -> None:
        """Apply Fairmont formatting to sheet."""
        service = self._get_service()

        requests = []

        # 1. Set column widths
        for col_idx, (_, _, width) in enumerate(self.COLUMNS):
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": col_idx,
                        "endIndex": col_idx + 1,
                    },
                    "properties": {
                        "pixelSize": width,
                    },
                    "fields": "pixelSize",
                }
            })

        # 2. Set header row height
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {
                    "pixelSize": 40,
                },
                "fields": "pixelSize",
            }
        })

        # 3. Set data row heights (for images)
        if row_count > 1:
            requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": 1,
                        "endIndex": row_count,
                    },
                    "properties": {
                        "pixelSize": 100,  # Height for images
                    },
                    "fields": "pixelSize",
                }
            })

        # 4. Format header row (dark blue background, white bold text)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 15,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {
                            "red": 0.212,
                            "green": 0.376,
                            "blue": 0.573,
                        },
                        "textFormat": {
                            "foregroundColor": {
                                "red": 1.0,
                                "green": 1.0,
                                "blue": 1.0,
                            },
                            "bold": True,
                            "fontSize": 11,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
            }
        })

        # 5. Format data cells (borders and alignment)
        if row_count > 1:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": row_count,
                        "startColumnIndex": 0,
                        "endColumnIndex": 15,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "verticalAlignment": "TOP",
                            "wrapStrategy": "WRAP",
                            "borders": {
                                "top": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                                "bottom": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                                "left": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                                "right": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                            },
                        }
                    },
                    "fields": "userEnteredFormat(verticalAlignment,wrapStrategy,borders)",
                }
            })

        # 6. Add borders to header
        requests.append({
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 15,
                },
                "top": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "bottom": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "left": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "right": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "innerHorizontal": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "innerVertical": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
            }
        })

        # 7. Center align specific columns (A, D, F, G, J, K)
        center_columns = [0, 3, 5, 6, 9, 10]  # A, D, F, G, J, K
        for col_idx in center_columns:
            if row_count > 1:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": row_count,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "CENTER",
                            }
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                })

        # 8. Right align price columns (H, I)
        price_columns = [7, 8]  # H, I
        for col_idx in price_columns:
            if row_count > 1:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": row_count,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "horizontalAlignment": "RIGHT",
                            }
                        },
                        "fields": "userEnteredFormat.horizontalAlignment",
                    }
                })

        # Execute all formatting requests
        if requests:
            self._execute_with_retry(
                service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": requests},
                )
            )

        logger.debug("Applied formatting to spreadsheet")

    def _set_sharing(
        self,
        spreadsheet_id: str,
        share_mode: Literal["view", "edit"],
        sheet_id: Optional[int] = None,
    ) -> str:
        """
        Set public link sharing.

        Args:
            spreadsheet_id: Spreadsheet ID
            share_mode: "view" for read-only, "edit" for editable
            sheet_id: Optional sheet ID for direct link to specific tab

        Returns:
            Shareable link
        """
        try:
            # Build Drive API client with same credentials
            creds_path = settings.google_credentials_path_resolved
            credentials = service_account.Credentials.from_service_account_file(
                str(creds_path),
                scopes=SCOPES,
            )
            drive = build("drive", "v3", credentials=credentials)

            permission = {
                "type": "anyone",
                "role": "writer" if share_mode == "edit" else "reader",
            }

            drive.permissions().create(
                fileId=spreadsheet_id,
                body=permission,
                fields="id",
            ).execute()

            logger.info(f"Set sharing for spreadsheet: {spreadsheet_id} (mode: {share_mode})")

        except Exception as e:
            logger.warning(f"Failed to set sharing permissions: {e}")
            # Don't fail the entire operation - may already be shared

        # Generate shareable link with sheet ID if provided
        gid_param = f"#gid={sheet_id}" if sheet_id is not None else ""
        if share_mode == "edit":
            return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit?usp=sharing{gid_param}"
        else:
            return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/view?usp=sharing{gid_param}"


# Global generator instance
_generator_instance: Optional[GoogleSheetsGeneratorService] = None


def get_google_sheets_generator() -> GoogleSheetsGeneratorService:
    """Get or create Google Sheets generator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = GoogleSheetsGeneratorService()
    return _generator_instance
