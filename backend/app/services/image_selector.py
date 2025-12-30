"""圖片解析度選擇服務.

在跨表合併時，從多個來源的圖片中選擇解析度最高的圖片。
"""

import base64
import struct
from typing import Optional, List, Tuple, NamedTuple


class ImageInfo(NamedTuple):
    """圖片資訊."""

    source_id: str  # 來源文件 ID
    base64_data: str  # Base64 編碼圖片
    width: int  # 寬度
    height: int  # 高度
    resolution: int  # 解析度 (width × height)


class ImageSelectorService:
    """圖片解析度選擇服務."""

    # 單例模式
    _instance: Optional["ImageSelectorService"] = None

    def __new__(cls) -> "ImageSelectorService":
        """確保單例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_image_dimensions(self, base64_data: str) -> Tuple[int, int]:
        """
        從 Base64 編碼的圖片中取得尺寸.

        支援 PNG, JPEG, GIF 格式。

        Args:
            base64_data: Base64 編碼的圖片資料（可包含 data:image/xxx;base64, 前綴）

        Returns:
            (寬度, 高度) 元組，若無法解析則返回 (0, 0)
        """
        try:
            # 移除 data URI 前綴（如 data:image/png;base64,）
            if "," in base64_data:
                base64_data = base64_data.split(",", 1)[1]

            # 解碼 Base64
            image_data = base64.b64decode(base64_data)

            # 檢測圖片格式並取得尺寸
            if image_data[:8] == b"\x89PNG\r\n\x1a\n":
                # PNG 格式
                return self._get_png_dimensions(image_data)
            elif image_data[:2] == b"\xff\xd8":
                # JPEG 格式
                return self._get_jpeg_dimensions(image_data)
            elif image_data[:6] in (b"GIF87a", b"GIF89a"):
                # GIF 格式
                return self._get_gif_dimensions(image_data)
            else:
                return (0, 0)

        except Exception:
            return (0, 0)

    def _get_png_dimensions(self, data: bytes) -> Tuple[int, int]:
        """從 PNG 資料取得尺寸."""
        try:
            # PNG IHDR chunk 位於 offset 16-24
            width = struct.unpack(">I", data[16:20])[0]
            height = struct.unpack(">I", data[20:24])[0]
            return (width, height)
        except Exception:
            return (0, 0)

    def _get_jpeg_dimensions(self, data: bytes) -> Tuple[int, int]:
        """從 JPEG 資料取得尺寸."""
        try:
            # JPEG 格式較複雜，需要找到 SOFn marker
            offset = 2
            while offset < len(data):
                if data[offset] != 0xFF:
                    offset += 1
                    continue

                marker = data[offset + 1]

                # SOF0, SOF1, SOF2 markers
                if marker in (0xC0, 0xC1, 0xC2):
                    height = struct.unpack(">H", data[offset + 5 : offset + 7])[0]
                    width = struct.unpack(">H", data[offset + 7 : offset + 9])[0]
                    return (width, height)

                # 跳過其他 marker
                if marker in (0xD8, 0xD9):  # SOI, EOI
                    offset += 2
                elif marker == 0xFF:
                    offset += 1
                else:
                    segment_length = struct.unpack(
                        ">H", data[offset + 2 : offset + 4]
                    )[0]
                    offset += 2 + segment_length

            return (0, 0)
        except Exception:
            return (0, 0)

    def _get_gif_dimensions(self, data: bytes) -> Tuple[int, int]:
        """從 GIF 資料取得尺寸."""
        try:
            # GIF 尺寸位於 offset 6-10
            width = struct.unpack("<H", data[6:8])[0]
            height = struct.unpack("<H", data[8:10])[0]
            return (width, height)
        except Exception:
            return (0, 0)

    def calculate_resolution(self, width: int, height: int) -> int:
        """
        計算圖片解析度（像素總數）.

        Args:
            width: 寬度
            height: 高度

        Returns:
            解析度 (width × height)
        """
        return width * height

    def select_highest_resolution(
        self, images: List[Tuple[str, str]]
    ) -> Optional[ImageInfo]:
        """
        從多張圖片中選擇解析度最高的.

        Args:
            images: [(source_id, base64_data), ...] 列表

        Returns:
            解析度最高的圖片資訊，若無有效圖片則返回 None

        Examples:
            >>> service = ImageSelectorService()
            >>> images = [
            ...     ("doc1", "data:image/png;base64,..."),
            ...     ("doc2", "data:image/png;base64,..."),
            ... ]
            >>> result = service.select_highest_resolution(images)
        """
        if not images:
            return None

        best_image: Optional[ImageInfo] = None
        best_resolution = 0

        for source_id, base64_data in images:
            if not base64_data:
                continue

            width, height = self.get_image_dimensions(base64_data)
            resolution = self.calculate_resolution(width, height)

            if resolution > best_resolution:
                best_resolution = resolution
                best_image = ImageInfo(
                    source_id=source_id,
                    base64_data=base64_data,
                    width=width,
                    height=height,
                    resolution=resolution,
                )

        return best_image

    def get_image_info(self, source_id: str, base64_data: str) -> ImageInfo:
        """
        取得單張圖片的資訊.

        Args:
            source_id: 來源文件 ID
            base64_data: Base64 編碼圖片

        Returns:
            圖片資訊
        """
        width, height = self.get_image_dimensions(base64_data)
        resolution = self.calculate_resolution(width, height)
        return ImageInfo(
            source_id=source_id,
            base64_data=base64_data,
            width=width,
            height=height,
            resolution=resolution,
        )


# 工廠函式
def get_image_selector_service() -> ImageSelectorService:
    """
    取得 ImageSelectorService 單例實例.

    Returns:
        ImageSelectorService 實例
    """
    return ImageSelectorService()
