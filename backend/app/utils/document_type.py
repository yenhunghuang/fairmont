"""Document type detection utilities."""

from typing import Literal

DocumentTypeStr = Literal[
    "furniture_specification",
    "fabric_specification",
    "quantity_summary",
]


def detect_document_type_from_filename(filename: str) -> DocumentTypeStr:
    """從檔名偵測文件類型（用於圖片匹配）.

    Args:
        filename: PDF 檔案名稱

    Returns:
        文件類型字串，用於圖片匹配的 page_offset 配置
    """
    filename_lower = filename.lower()

    if any(kw in filename_lower for kw in ["casegoods", "seating", "lighting"]):
        return "furniture_specification"
    elif any(kw in filename_lower for kw in ["fabric", "leather", "vinyl"]):
        return "fabric_specification"
    elif any(kw in filename_lower for kw in ["qty", "overall", "summary", "quantity"]):
        return "quantity_summary"

    return "furniture_specification"
