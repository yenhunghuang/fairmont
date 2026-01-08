# Google Gemini 3 Flash Preview - PDF 文件解析最佳實踐

**文檔版本**: 1.0
**建立日期**: 2025-12-19
**適用模型**: gemini-3-flash-preview (gemini-flash-1.5 fallback)
**專案**: 家具報價單系統 (Furniture Quotation System)

---

## 目錄

1. [Gemini API PDF 處理機制](#1-gemini-api-pdf-處理機制)
2. [Python SDK 最佳實踐](#2-python-sdk-最佳實踐)
3. [BOQ 表格資料提取（結構化輸出）](#3-boq-表格資料提取結構化輸出)
4. [PDF 圖片提取](#4-pdf-圖片提取)
5. [API 限制與配額](#5-api-限制與配額)
6. [錯誤處理最佳實踐](#6-錯誤處理最佳實踐)
7. [完整實作範例](#7-完整實作範例)

---

## 1. Gemini API PDF 處理機制

### 1.1 原生 PDF 支援

**重要**: Gemini API **原生支援 PDF 檔案**，無需預先轉換為圖片。

```python
import google.generativeai as genai

# Gemini API 支援兩種 PDF 處理方式:

# 方式 1: 直接上傳 PDF 檔案 (推薦用於小型檔案 < 20MB)
genai.configure(api_key="YOUR_API_KEY")
model = genai.GenerativeModel("gemini-1.5-flash")

# 直接傳入 PDF 檔案
with open("boq_document.pdf", "rb") as f:
    pdf_file = genai.upload_file(f, mime_type="application/pdf")

response = model.generate_content([
    "請提取這份 BOQ 文件中的所有活動家具項目",
    pdf_file
])

# 方式 2: 使用 File API (推薦用於大型檔案或需要重複使用)
uploaded_file = genai.upload_file("boq_document.pdf")
print(f"Uploaded file: {uploaded_file.name}")

# 等待檔案處理完成
import time
while uploaded_file.state.name == "PROCESSING":
    time.sleep(2)
    uploaded_file = genai.get_file(uploaded_file.name)

if uploaded_file.state.name == "ACTIVE":
    response = model.generate_content([uploaded_file, "提取 BOQ 資料"])
```

### 1.2 PDF vs 圖片的選擇策略

| 情境 | 建議方式 | 原因 |
|------|---------|------|
| 標準 PDF (文字可選取) | **直接使用 PDF** | 保留文字結構、更準確的表格解析 |
| 掃描版 PDF (圖片型) | **直接使用 PDF** | Gemini 自動 OCR 處理，無需手動轉換 |
| 多頁 PDF (>50 頁) | **PDF + File API** | 避免超過 token 限制 |
| 平面圖 (CAD 輸出) | **轉換為高解析度圖片** | 保持尺寸標註清晰度 |

**最佳實踐**: 對於您的 BOQ 文件，**優先使用原生 PDF 上傳**，這樣可以：
- 保留文字層資訊，提高表格解析準確度
- 減少預處理時間
- 降低檔案大小（相比圖片）

---

## 2. Python SDK 最佳實踐

### 2.1 安裝與初始化

```bash
# 安裝 SDK
pip install google-generativeai>=0.8.0

# 可選：安裝額外依賴用於進階功能
pip install pillow PyMuPDF  # 圖片處理與 PDF 元數據讀取
```

```python
# config.py - 集中管理設定
import os
from typing import Optional
import google.generativeai as genai
from pydantic_settings import BaseSettings

class GeminiConfig(BaseSettings):
    """Gemini API 設定"""

    api_key: str
    model_name: str = "gemini-3-flash-preview"  # gemini-3-flash-preview 尚未正式釋出，使用 1.5-flash
    temperature: float = 0.1  # 低溫度提高一致性
    max_output_tokens: int = 8192
    timeout_seconds: int = 120

    class Config:
        env_file = ".env"
        env_prefix = "GEMINI_"

# 初始化
config = GeminiConfig()
genai.configure(api_key=config.api_key)
```

### 2.2 模型配置與安全設定

```python
# services/pdf_parser.py
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai

class GeminiPDFParser:
    """Gemini PDF 解析服務"""

    def __init__(self, config: GeminiConfig):
        self.config = config

        # 安全設定（BOQ 文件通常不包含敏感內容）
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        # 模型設定
        self.generation_config = genai.GenerationConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            top_p=0.95,
            top_k=40,
        )

        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings,
        )

    async def parse_pdf(self, pdf_path: str, prompt: str) -> str:
        """解析 PDF 檔案（async 版本）"""
        import asyncio

        # 上傳檔案
        uploaded_file = await asyncio.to_thread(
            genai.upload_file, pdf_path, mime_type="application/pdf"
        )

        # 等待處理完成
        while uploaded_file.state.name == "PROCESSING":
            await asyncio.sleep(2)
            uploaded_file = await asyncio.to_thread(
                genai.get_file, uploaded_file.name
            )

        if uploaded_file.state.name != "ACTIVE":
            raise ValueError(f"檔案處理失敗: {uploaded_file.state.name}")

        # 生成內容
        response = await asyncio.to_thread(
            self.model.generate_content, [uploaded_file, prompt]
        )

        # 清理檔案（避免配額耗盡）
        await asyncio.to_thread(genai.delete_file, uploaded_file.name)

        return response.text
```

### 2.3 批次處理與速率控制

```python
import asyncio
from asyncio import Semaphore
from typing import List

class BatchPDFProcessor:
    """批次 PDF 處理器，包含速率限制"""

    def __init__(self, parser: GeminiPDFParser, max_concurrent: int = 3):
        self.parser = parser
        self.semaphore = Semaphore(max_concurrent)  # 限制並發數

    async def process_single(self, pdf_path: str, prompt: str) -> dict:
        """處理單一 PDF，包含錯誤處理"""
        async with self.semaphore:
            try:
                result = await self.parser.parse_pdf(pdf_path, prompt)
                return {"success": True, "file": pdf_path, "data": result}
            except Exception as e:
                return {"success": False, "file": pdf_path, "error": str(e)}

    async def process_batch(self, pdf_files: List[str], prompt: str) -> List[dict]:
        """批次處理多個 PDF"""
        tasks = [self.process_single(pdf, prompt) for pdf in pdf_files]
        results = await asyncio.gather(*tasks)
        return results

# 使用範例
async def main():
    config = GeminiConfig()
    parser = GeminiPDFParser(config)
    batch_processor = BatchPDFProcessor(parser, max_concurrent=3)

    pdf_files = ["boq1.pdf", "boq2.pdf", "boq3.pdf"]
    prompt = "提取所有 BOQ 項目資料"

    results = await batch_processor.process_batch(pdf_files, prompt)
    for result in results:
        if result["success"]:
            print(f"✓ {result['file']}: {len(result['data'])} 字元")
        else:
            print(f"✗ {result['file']}: {result['error']}")
```

---

## 3. BOQ 表格資料提取（結構化輸出）

### 3.1 使用 JSON Schema 強制結構化輸出

Gemini 1.5+ 支援 **Function Calling** 和 **JSON Mode**，適合提取結構化資料。

```python
from typing import List, Optional
from pydantic import BaseModel, Field

# 定義 BOQ 項目結構
class BOQItem(BaseModel):
    """BOQ 項目資料模型"""
    item_no: str = Field(..., description="項次編號")
    description: str = Field(..., description="品名描述")
    dimension: Optional[str] = Field(None, description="尺寸")
    qty: Optional[float] = Field(None, description="數量")
    uom: Optional[str] = Field(None, description="單位")
    location: Optional[str] = Field(None, description="位置")
    materials_used: Optional[str] = Field(None, description="使用材料/規格")
    page_number: Optional[int] = Field(None, description="來源頁碼")

class BOQExtraction(BaseModel):
    """BOQ 提取結果"""
    items: List[BOQItem]
    total_items: int
    source_file: str

# Gemini 結構化輸出實作
class StructuredBOQParser(GeminiPDFParser):
    """支援結構化輸出的 BOQ 解析器"""

    def __init__(self, config: GeminiConfig):
        super().__init__(config)

        # 使用 JSON Mode (Gemini 1.5+)
        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            generation_config={
                **self.generation_config.__dict__,
                "response_mime_type": "application/json",  # 強制 JSON 輸出
            }
        )

    async def extract_boq_structured(self, pdf_path: str) -> BOQExtraction:
        """提取 BOQ 資料並返回結構化物件"""

        # 詳細的 Prompt Engineering
        prompt = f"""
請分析這份 PDF 文件，提取所有「活動家具及物料」相關的 BOQ (Bill of Quantities) 項目。

**輸出格式要求 (JSON)**:
{{
  "items": [
    {{
      "item_no": "項次編號（如 A-01, 1.1 等）",
      "description": "品名描述（簡短品名）",
      "dimension": "尺寸（如 1200x800x750mm）",
      "qty": 數量（數值型態，如 5.0）,
      "uom": "單位（如 PCS, SET, M2）",
      "location": "位置（如 會議室, 辦公區）",
      "materials_used": "使用材料/詳細規格",
      "page_number": PDF 頁碼（數值）
    }}
  ],
  "total_items": 項目總數,
  "source_file": "{pdf_path}"
}}

**提取規則**:
1. 只提取「活動家具」相關項目（桌、椅、櫃等），忽略固定裝修
2. 如果數量欄位為空或標示 TBD，qty 設為 null
3. 尺寸需包含單位（優先 mm）
4. materials_used 欄位提取完整規格描述
5. 確保 item_no 唯一且保持原始編號格式

**範例輸出**:
{{
  "items": [
    {{
      "item_no": "A-01",
      "description": "會議桌",
      "dimension": "2400x1200x750mm",
      "qty": 2.0,
      "uom": "張",
      "location": "會議室A",
      "materials_used": "桌面: 25mm美耐板; 腳架: 鋼製烤漆",
      "page_number": 3
    }}
  ],
  "total_items": 1,
  "source_file": "{pdf_path}"
}}
"""

        # 呼叫 Gemini API
        result_json = await self.parse_pdf(pdf_path, prompt)

        # 解析 JSON 並驗證
        import json
        data = json.loads(result_json)
        return BOQExtraction(**data)

# 使用範例
async def extract_example():
    config = GeminiConfig()
    parser = StructuredBOQParser(config)

    result = await parser.extract_boq_structured("sample_boq.pdf")

    print(f"提取了 {result.total_items} 個項目:")
    for item in result.items:
        print(f"  [{item.item_no}] {item.description} - {item.qty} {item.uom}")
```

### 3.2 增強準確度的 Prompt Engineering 技巧

```python
# 多階段提取策略（提高準確度）
class AdvancedBOQParser(StructuredBOQParser):
    """進階 BOQ 解析器：兩階段提取"""

    async def extract_with_verification(self, pdf_path: str) -> BOQExtraction:
        """兩階段提取：粗提取 -> 精修"""

        # Stage 1: 粗提取（快速識別所有項目）
        stage1_prompt = """
請快速掃描這份 PDF，識別所有包含以下關鍵字的表格行：
- 「桌」「椅」「櫃」「屏風」「沙發」
- 項次編號模式（如 A-01, 1.1, F-001）
- 數量欄位（Qty, 數量, QTY）

返回 JSON 陣列，包含：
- 項目所在頁碼
- 識別到的項次編號
- 初步判斷的品名
"""
        rough_items = await self.parse_pdf(pdf_path, stage1_prompt)

        # Stage 2: 精確提取（針對識別到的頁面進行詳細解析）
        stage2_prompt = f"""
已初步識別到以下項目：
{rough_items}

請針對這些項目，在對應頁碼進行精確提取，填寫完整的 8 個欄位：
Item No., Description, Photo, Dimension, Qty, UOM, Location, Materials Used/Specs

返回完整的結構化 JSON（按照 BOQExtraction 格式）
"""
        final_result = await self.parse_pdf(pdf_path, stage2_prompt)

        import json
        return BOQExtraction(**json.loads(final_result))
```

### 3.3 處理複雜表格（跨頁、合併儲存格）

```python
# 處理複雜表格的 Prompt 策略
COMPLEX_TABLE_PROMPT = """
**特殊情況處理指引**:

1. **跨頁表格**: 如果表格延續到下一頁，請合併資料為單一項目
   - 判斷依據: 下一頁首行無標題列（Item No. 欄位為空或數值接續）

2. **合併儲存格**:
   - 縱向合併: 代表多行共用同一屬性（如同一位置的多個項目）
   - 橫向合併: 代表該欄位資料較長，完整複製內容

3. **多層次編號**:
   - 主項目: A-01
   - 子項目: A-01.1, A-01.2
   - 將子項目展開為獨立項目，但在 description 前加上主項目品名

4. **數量計算公式**: 如遇到「2間 x 3張 = 6張」，qty 欄位填寫計算結果 6.0

5. **尺寸變化**: 如同一項目有多種尺寸，拆分為多個項目:
   - A-01a: 會議桌 (2400mm)
   - A-01b: 會議桌 (1800mm)

**錯誤處理**:
- 無法識別的儲存格: 設為 null
- 模糊的單位: 保留原始文字（如「組」「式」）
- 缺失的項次編號: 使用 "UNKNOWN-{序號}" 並在 materials_used 備註
"""

# 整合到 Parser
class RobustBOQParser(AdvancedBOQParser):
    async def extract_robust(self, pdf_path: str) -> BOQExtraction:
        combined_prompt = f"""
{COMPLEX_TABLE_PROMPT}

{self._get_base_extraction_prompt(pdf_path)}
"""
        result_json = await self.parse_pdf(pdf_path, combined_prompt)
        import json
        return BOQExtraction(**json.loads(result_json))
```

---

## 4. PDF 圖片提取

### 4.1 策略：Gemini API vs PyMuPDF

| 需求 | 推薦方案 | 原因 |
|------|---------|------|
| 提取 BOQ 表格中的產品照片 | **PyMuPDF** | 精確提取、保留原始解析度 |
| 識別圖片中的文字標註 | **Gemini API** | 強大的 OCR 與理解能力 |
| 平面圖數量核對 | **Gemini API** | 需要理解圖面語意 |

### 4.2 使用 PyMuPDF 提取圖片

```python
# services/image_extractor.py
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Tuple
import io
from PIL import Image

class PDFImageExtractor:
    """PDF 圖片提取服務"""

    def __init__(self, output_dir: str = "temp/images"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_images(self, pdf_path: str) -> List[dict]:
        """
        提取 PDF 中所有圖片

        Returns:
            List[dict]: [
                {
                    "page": 頁碼,
                    "image_index": 圖片索引,
                    "bbox": (x0, y0, x1, y1),  # 邊界框
                    "image_path": "儲存路徑",
                    "width": 寬度,
                    "height": 高度
                }
            ]
        """
        doc = fitz.open(pdf_path)
        extracted_images = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]

                # 提取圖片資料
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # 取得圖片位置
                bbox = self._get_image_bbox(page, xref)

                # 儲存圖片
                image_filename = f"page{page_num+1}_img{img_index+1}.{image_ext}"
                image_path = self.output_dir / image_filename

                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)

                # 取得尺寸
                with Image.open(io.BytesIO(image_bytes)) as pil_img:
                    width, height = pil_img.size

                extracted_images.append({
                    "page": page_num + 1,
                    "image_index": img_index + 1,
                    "bbox": bbox,
                    "image_path": str(image_path),
                    "width": width,
                    "height": height,
                    "format": image_ext
                })

        doc.close()
        return extracted_images

    def _get_image_bbox(self, page: fitz.Page, xref: int) -> Tuple[float, float, float, float]:
        """取得圖片在頁面上的邊界框"""
        image_rects = page.get_image_rects(xref)
        if image_rects:
            rect = image_rects[0]
            return (rect.x0, rect.y0, rect.x1, rect.y1)
        return (0, 0, 0, 0)

    def extract_images_near_text(
        self,
        pdf_path: str,
        keywords: List[str],
        proximity_threshold: float = 100.0  # points (約 35mm)
    ) -> List[dict]:
        """
        提取特定文字附近的圖片（用於 BOQ 項目照片）

        Args:
            pdf_path: PDF 檔案路徑
            keywords: 關鍵字列表（如項次編號 ["A-01", "A-02"]）
            proximity_threshold: 鄰近距離閾值（點）
        """
        doc = fitz.open(pdf_path)
        matched_images = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # 搜尋關鍵字位置
            for keyword in keywords:
                text_instances = page.search_for(keyword)

                if text_instances:
                    # 取得該關鍵字的邊界框
                    text_rect = text_instances[0]

                    # 找出鄰近圖片
                    image_list = page.get_images(full=True)
                    for img_index, img_info in enumerate(image_list):
                        xref = img_info[0]
                        img_bbox = self._get_image_bbox(page, xref)

                        # 計算距離
                        if self._is_nearby(text_rect, img_bbox, proximity_threshold):
                            # 提取圖片
                            base_image = doc.extract_image(xref)
                            image_path = self.output_dir / f"{keyword.replace('/', '-')}.{base_image['ext']}"

                            with open(image_path, "wb") as img_file:
                                img_file.write(base_image["image"])

                            matched_images.append({
                                "keyword": keyword,
                                "page": page_num + 1,
                                "image_path": str(image_path),
                                "bbox": img_bbox
                            })

        doc.close()
        return matched_images

    def _is_nearby(
        self,
        text_rect: fitz.Rect,
        img_bbox: Tuple[float, float, float, float],
        threshold: float
    ) -> bool:
        """判斷文字與圖片是否鄰近"""
        img_rect = fitz.Rect(img_bbox)

        # 計算兩個矩形的最短距離
        # 如果重疊，距離為 0
        if text_rect.intersects(img_rect):
            return True

        # 計算中心點距離
        text_center = ((text_rect.x0 + text_rect.x1) / 2, (text_rect.y0 + text_rect.y1) / 2)
        img_center = ((img_rect.x0 + img_rect.x1) / 2, (img_rect.y0 + img_rect.y1) / 2)

        distance = ((text_center[0] - img_center[0]) ** 2 +
                   (text_center[1] - img_center[1]) ** 2) ** 0.5

        return distance <= threshold
```

### 4.3 使用 Gemini 識別圖片內容

```python
class GeminiImageAnalyzer:
    """使用 Gemini 分析圖片內容"""

    def __init__(self, config: GeminiConfig):
        self.config = config
        self.model = genai.GenerativeModel(config.model_name)

    async def analyze_furniture_photo(self, image_path: str, item_description: str) -> dict:
        """
        分析家具照片，驗證是否匹配 BOQ 描述

        Returns:
            {
                "matches": bool,  # 是否匹配描述
                "confidence": float,  # 信心分數 0-1
                "detected_features": List[str],  # 識別到的特徵
                "suggested_description": str  # 建議的描述
            }
        """
        import asyncio

        # 上傳圖片
        uploaded_image = await asyncio.to_thread(
            genai.upload_file, image_path, mime_type="image/jpeg"
        )

        prompt = f"""
分析這張家具照片，並與以下描述比對：
「{item_description}」

請提供 JSON 格式分析結果：
{{
  "matches": true/false,
  "confidence": 0.0-1.0,
  "detected_features": ["特徵1", "特徵2"],
  "suggested_description": "建議的品名描述"
}}

檢查項目：
- 家具類型是否正確（桌/椅/櫃等）
- 材質是否相符
- 尺寸比例是否合理
"""

        response = await asyncio.to_thread(
            self.model.generate_content, [uploaded_image, prompt]
        )

        # 清理檔案
        await asyncio.to_thread(genai.delete_file, uploaded_image.name)

        import json
        return json.loads(response.text)

    async def extract_quantity_from_floor_plan(
        self,
        floor_plan_path: str,
        item_symbol: str
    ) -> dict:
        """
        從平面圖提取家具數量

        Args:
            floor_plan_path: 平面圖檔案路徑
            item_symbol: 家具符號（如 "CH-01" 代表椅子）

        Returns:
            {
                "symbol": str,
                "quantity": int,
                "locations": List[str],  # 識別到的位置
                "confidence": float
            }
        """
        import asyncio

        uploaded_plan = await asyncio.to_thread(
            genai.upload_file, floor_plan_path, mime_type="image/jpeg"
        )

        prompt = f"""
這是一張建築平面圖。請計算符號「{item_symbol}」在圖面上出現的次數。

返回 JSON 格式：
{{
  "symbol": "{item_symbol}",
  "quantity": 總數量,
  "locations": ["位置1", "位置2"],  // 如「會議室」「辦公區A」
  "confidence": 0.0-1.0  // 信心分數
}}

計數規則：
1. 只計算清楚標示的符號
2. 模糊或部分遮擋的符號標註為「不確定」
3. 識別房間/區域名稱作為位置資訊
"""

        response = await asyncio.to_thread(
            self.model.generate_content, [uploaded_plan, prompt]
        )

        await asyncio.to_thread(genai.delete_file, uploaded_plan.name)

        import json
        return json.loads(response.text)
```

---

## 5. API 限制與配額

### 5.1 官方限制（截至 2025 年 1 月）

**注意**: Gemini 3 Flash Preview 尚未正式釋出，以下為 Gemini 1.5 Flash 的限制，作為參考。

| 限制類型 | Free Tier | Pay-as-you-go |
|---------|-----------|---------------|
| **RPM (Requests Per Minute)** | 15 | 1000 |
| **TPM (Tokens Per Minute)** | 1M | 4M |
| **RPD (Requests Per Day)** | 1500 | 無限制 |
| **Input Token Limit** | 128K | 1M (1.5 Pro) |
| **Output Token Limit** | 8K | 8K |
| **File Size Limit** | 20MB | 20MB |
| **Max Files Per Request** | 10 | 10 |

### 5.2 實作速率限制控制

```python
# utils/rate_limiter.py
import asyncio
import time
from collections import deque
from typing import Deque

class TokenBucketRateLimiter:
    """Token Bucket 演算法實作速率限制"""

    def __init__(
        self,
        requests_per_minute: int = 15,
        tokens_per_minute: int = 1_000_000,
        burst_size: int = 5
    ):
        self.rpm = requests_per_minute
        self.tpm = tokens_per_minute
        self.burst_size = burst_size

        # Request tracking
        self.request_times: Deque[float] = deque(maxlen=requests_per_minute)
        self.lock = asyncio.Lock()

        # Token tracking (估算)
        self.token_count = 0
        self.token_reset_time = time.time() + 60

    async def acquire(self, estimated_tokens: int = 1000):
        """取得執行許可"""
        async with self.lock:
            now = time.time()

            # 檢查 RPM
            if len(self.request_times) >= self.rpm:
                oldest_request = self.request_times[0]
                wait_time = 60 - (now - oldest_request)
                if wait_time > 0:
                    print(f"⏳ RPM 限制: 等待 {wait_time:.1f} 秒")
                    await asyncio.sleep(wait_time)
                    now = time.time()

            # 檢查 TPM
            if now > self.token_reset_time:
                self.token_count = 0
                self.token_reset_time = now + 60

            if self.token_count + estimated_tokens > self.tpm:
                wait_time = self.token_reset_time - now
                print(f"⏳ TPM 限制: 等待 {wait_time:.1f} 秒")
                await asyncio.sleep(wait_time)
                self.token_count = 0
                self.token_reset_time = time.time() + 60

            # 記錄
            self.request_times.append(time.time())
            self.token_count += estimated_tokens

# 整合到 Parser
class RateLimitedParser(RobustBOQParser):
    """包含速率限制的 Parser"""

    def __init__(self, config: GeminiConfig, rate_limiter: TokenBucketRateLimiter):
        super().__init__(config)
        self.rate_limiter = rate_limiter

    async def parse_pdf(self, pdf_path: str, prompt: str) -> str:
        # 估算 token 數量（粗估：1 頁 PDF ≈ 1000 tokens）
        import fitz
        doc = fitz.open(pdf_path)
        estimated_tokens = len(doc) * 1000 + len(prompt.split()) * 2
        doc.close()

        # 取得許可
        await self.rate_limiter.acquire(estimated_tokens)

        # 執行解析
        return await super().parse_pdf(pdf_path, prompt)
```

### 5.3 檔案大小管理

```python
# utils/file_manager.py
import os
import fitz
from pathlib import Path

class PDFFileManager:
    """PDF 檔案管理器"""

    MAX_FILE_SIZE_MB = 50  # 專案限制
    GEMINI_MAX_SIZE_MB = 20  # Gemini API 限制

    @staticmethod
    def check_file_size(file_path: str) -> dict:
        """檢查檔案大小"""
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)

        return {
            "size_mb": size_mb,
            "within_project_limit": size_mb <= PDFFileManager.MAX_FILE_SIZE_MB,
            "within_gemini_limit": size_mb <= PDFFileManager.GEMINI_MAX_SIZE_MB,
            "requires_splitting": size_mb > PDFFileManager.GEMINI_MAX_SIZE_MB
        }

    @staticmethod
    def split_pdf_if_needed(file_path: str, output_dir: str = "temp/split") -> list:
        """
        如果 PDF 超過 Gemini 限制，分割成多個檔案

        Returns:
            List[str]: 分割後的檔案路徑列表
        """
        size_check = PDFFileManager.check_file_size(file_path)

        if not size_check["requires_splitting"]:
            return [file_path]

        # 分割策略：依頁數平均分割
        doc = fitz.open(file_path)
        total_pages = len(doc)

        # 估算需要分成幾份（保守估計：15MB per file）
        num_splits = int(size_check["size_mb"] / 15) + 1
        pages_per_split = total_pages // num_splits

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        split_files = []
        base_name = Path(file_path).stem

        for i in range(num_splits):
            start_page = i * pages_per_split
            end_page = min((i + 1) * pages_per_split, total_pages)

            # 建立分割文件
            split_doc = fitz.open()
            split_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)

            split_filename = f"{base_name}_part{i+1}.pdf"
            split_path = output_path / split_filename
            split_doc.save(split_path)
            split_doc.close()

            split_files.append(str(split_path))

        doc.close()
        return split_files
```

---

## 6. 錯誤處理最佳實踐

### 6.1 常見錯誤與處理策略

```python
# utils/error_handler.py
from typing import Optional, Callable
import asyncio
from google.api_core import exceptions as google_exceptions
import google.generativeai as genai

class GeminiErrorHandler:
    """Gemini API 錯誤處理器"""

    # 錯誤分類
    RETRYABLE_ERRORS = (
        google_exceptions.ResourceExhausted,  # 配額超限
        google_exceptions.ServiceUnavailable,  # 服務暫時不可用
        google_exceptions.DeadlineExceeded,   # 超時
    )

    PERMANENT_ERRORS = (
        google_exceptions.InvalidArgument,    # 參數錯誤
        google_exceptions.PermissionDenied,   # 權限拒絕
        google_exceptions.NotFound,           # 資源不存在
    )

    @staticmethod
    async def execute_with_retry(
        func: Callable,
        max_retries: int = 3,
        base_delay: float = 2.0,
        backoff_factor: float = 2.0,
        *args,
        **kwargs
    ):
        """
        執行函數並在失敗時重試（Exponential Backoff）

        Args:
            func: 要執行的函數
            max_retries: 最大重試次數
            base_delay: 基礎延遲（秒）
            backoff_factor: 退避係數
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)

            except GeminiErrorHandler.PERMANENT_ERRORS as e:
                # 永久性錯誤：不重試
                raise ValueError(f"永久性錯誤，無法重試: {str(e)}") from e

            except GeminiErrorHandler.RETRYABLE_ERRORS as e:
                last_exception = e

                if attempt < max_retries:
                    delay = base_delay * (backoff_factor ** attempt)
                    print(f"⚠️ 錯誤 (嘗試 {attempt + 1}/{max_retries + 1}): {str(e)}")
                    print(f"   {delay:.1f} 秒後重試...")
                    await asyncio.sleep(delay)
                else:
                    raise ValueError(f"達到最大重試次數: {str(e)}") from e

            except Exception as e:
                # 未預期錯誤：記錄並重新拋出
                print(f"❌ 未預期錯誤: {type(e).__name__}: {str(e)}")
                raise

        # 不應到達此處
        raise last_exception

    @staticmethod
    def get_error_message_zh(exception: Exception) -> str:
        """將錯誤轉換為繁體中文訊息"""
        error_messages = {
            google_exceptions.ResourceExhausted: "API 配額已用盡，請稍後再試",
            google_exceptions.InvalidArgument: "請求參數錯誤，請檢查上傳的檔案格式",
            google_exceptions.PermissionDenied: "API 金鑰無效或權限不足",
            google_exceptions.NotFound: "找不到指定的資源",
            google_exceptions.DeadlineExceeded: "請求超時，檔案可能過大",
            google_exceptions.ServiceUnavailable: "Gemini 服務暫時無法使用",
        }

        for error_type, message in error_messages.items():
            if isinstance(exception, error_type):
                return message

        return f"發生未知錯誤: {str(exception)}"

# 整合到 API 路由
from fastapi import HTTPException

async def parse_pdf_endpoint(file_path: str):
    """API 端點範例"""
    try:
        parser = RateLimitedParser(config, rate_limiter)

        result = await GeminiErrorHandler.execute_with_retry(
            parser.extract_robust,
            max_retries=3,
            file_path=file_path
        )

        return {"success": True, "data": result}

    except ValueError as e:
        # 已知錯誤
        error_msg = GeminiErrorHandler.get_error_message_zh(e.__cause__ or e)
        raise HTTPException(status_code=400, detail=error_msg)

    except Exception as e:
        # 未知錯誤
        print(f"❌ 系統錯誤: {e}")
        raise HTTPException(status_code=500, detail="系統內部錯誤，請聯絡管理員")
```

### 6.2 檔案上傳錯誤處理

```python
class FileUploadValidator:
    """檔案上傳驗證器"""

    ALLOWED_MIME_TYPES = ["application/pdf"]
    MAX_FILE_SIZE_MB = 50

    @staticmethod
    def validate_upload(file_path: str) -> dict:
        """
        驗證上傳檔案

        Returns:
            {"valid": bool, "error": Optional[str]}
        """
        # 檢查檔案存在
        if not os.path.exists(file_path):
            return {"valid": False, "error": "檔案不存在"}

        # 檢查檔案大小
        size_check = PDFFileManager.check_file_size(file_path)
        if not size_check["within_project_limit"]:
            return {
                "valid": False,
                "error": f"檔案過大（{size_check['size_mb']:.1f}MB），限制為 {FileUploadValidator.MAX_FILE_SIZE_MB}MB"
            }

        # 檢查檔案類型
        import magic
        mime = magic.Magic(mime=True)
        file_mime = mime.from_file(file_path)

        if file_mime not in FileUploadValidator.ALLOWED_MIME_TYPES:
            return {"valid": False, "error": f"不支援的檔案類型: {file_mime}"}

        # 檢查 PDF 是否損壞
        try:
            doc = fitz.open(file_path)
            if len(doc) == 0:
                return {"valid": False, "error": "PDF 檔案為空"}
            doc.close()
        except Exception as e:
            return {"valid": False, "error": f"PDF 檔案損壞: {str(e)}"}

        return {"valid": True, "error": None}

# FastAPI 路由範例
from fastapi import UploadFile, File

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """上傳 PDF 檔案 API"""

    # 儲存暫存檔案
    temp_path = f"temp/uploads/{file.filename}"
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)

    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 驗證檔案
    validation = FileUploadValidator.validate_upload(temp_path)
    if not validation["valid"]:
        os.remove(temp_path)
        raise HTTPException(status_code=400, detail=validation["error"])

    return {
        "success": True,
        "file_id": Path(temp_path).stem,
        "file_path": temp_path,
        "size_mb": os.path.getsize(temp_path) / (1024 * 1024)
    }
```

### 6.3 內容安全過濾處理

```python
from google.generativeai.types import BlockedPromptException

async def safe_generate_content(model, prompt, file):
    """安全的內容生成（處理 Safety Filter）"""
    try:
        response = await asyncio.to_thread(
            model.generate_content, [file, prompt]
        )

        # 檢查回應是否被過濾
        if hasattr(response, 'prompt_feedback'):
            if response.prompt_feedback.block_reason:
                return {
                    "success": False,
                    "error": f"內容被安全過濾器阻擋: {response.prompt_feedback.block_reason}"
                }

        return {"success": True, "content": response.text}

    except BlockedPromptException as e:
        return {
            "success": False,
            "error": "提示詞包含不當內容，請調整後重試"
        }
```

---

## 7. 完整實作範例

### 7.1 端到端 BOQ 解析流程

```python
# services/boq_processing_service.py
"""完整的 BOQ 處理服務"""

import asyncio
from typing import List, Optional
from pathlib import Path
import json

class BOQProcessingService:
    """BOQ 處理服務：整合所有功能"""

    def __init__(self, config: GeminiConfig):
        # 初始化所有依賴
        self.rate_limiter = TokenBucketRateLimiter(
            requests_per_minute=15,
            tokens_per_minute=1_000_000
        )
        self.parser = RateLimitedParser(config, self.rate_limiter)
        self.image_extractor = PDFImageExtractor()
        self.image_analyzer = GeminiImageAnalyzer(config)
        self.file_manager = PDFFileManager()

    async def process_boq_pdf(
        self,
        pdf_path: str,
        extract_images: bool = True,
        verify_images: bool = False
    ) -> dict:
        """
        完整處理單一 BOQ PDF

        Args:
            pdf_path: PDF 檔案路徑
            extract_images: 是否提取圖片
            verify_images: 是否驗證圖片匹配描述

        Returns:
            {
                "boq_data": BOQExtraction,
                "images": List[dict],
                "verification_results": Optional[List[dict]],
                "processing_time": float
            }
        """
        import time
        start_time = time.time()

        # Step 1: 驗證檔案
        validation = FileUploadValidator.validate_upload(pdf_path)
        if not validation["valid"]:
            raise ValueError(validation["error"])

        # Step 2: 檢查檔案大小，必要時分割
        split_files = self.file_manager.split_pdf_if_needed(pdf_path)

        # Step 3: 解析 BOQ 資料
        if len(split_files) == 1:
            boq_data = await self.parser.extract_robust(split_files[0])
        else:
            # 多檔案合併
            all_items = []
            for split_file in split_files:
                partial_data = await self.parser.extract_robust(split_file)
                all_items.extend(partial_data.items)

            boq_data = BOQExtraction(
                items=all_items,
                total_items=len(all_items),
                source_file=pdf_path
            )

        # Step 4: 提取圖片
        extracted_images = []
        if extract_images:
            # 提取所有 BOQ 項目編號
            item_numbers = [item.item_no for item in boq_data.items]

            extracted_images = self.image_extractor.extract_images_near_text(
                pdf_path,
                item_numbers,
                proximity_threshold=100.0
            )

        # Step 5: 驗證圖片（可選）
        verification_results = None
        if verify_images and extracted_images:
            verification_results = await self._verify_images(
                boq_data.items,
                extracted_images
            )

        processing_time = time.time() - start_time

        return {
            "boq_data": boq_data,
            "images": extracted_images,
            "verification_results": verification_results,
            "processing_time": processing_time,
            "metadata": {
                "total_items": boq_data.total_items,
                "total_images": len(extracted_images),
                "was_split": len(split_files) > 1,
                "split_parts": len(split_files)
            }
        }

    async def _verify_images(
        self,
        boq_items: List[BOQItem],
        images: List[dict]
    ) -> List[dict]:
        """驗證圖片與 BOQ 項目的匹配度"""
        verification_tasks = []

        for image in images:
            # 找到對應的 BOQ 項目
            matching_item = next(
                (item for item in boq_items if item.item_no == image["keyword"]),
                None
            )

            if matching_item:
                task = self.image_analyzer.analyze_furniture_photo(
                    image["image_path"],
                    matching_item.description
                )
                verification_tasks.append(task)

        results = await asyncio.gather(*verification_tasks, return_exceptions=True)

        return [
            {"image": img, "verification": res}
            for img, res in zip(images, results)
            if not isinstance(res, Exception)
        ]

    async def process_multiple_pdfs(
        self,
        pdf_paths: List[str],
        merge_results: bool = True
    ) -> dict:
        """
        批次處理多個 PDF 檔案

        Args:
            pdf_paths: PDF 檔案路徑列表
            merge_results: 是否合併結果
        """
        # 並行處理（受速率限制器控制）
        tasks = [
            self.process_boq_pdf(pdf, extract_images=True, verify_images=False)
            for pdf in pdf_paths
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 分離成功與失敗
        successful_results = [r for r in results if not isinstance(r, Exception)]
        failed_results = [
            {"file": pdf_paths[i], "error": str(r)}
            for i, r in enumerate(results)
            if isinstance(r, Exception)
        ]

        # 合併結果
        if merge_results and successful_results:
            merged_items = []
            merged_images = []

            for result in successful_results:
                merged_items.extend(result["boq_data"].items)
                merged_images.extend(result["images"])

            merged_boq = BOQExtraction(
                items=merged_items,
                total_items=len(merged_items),
                source_file="merged"
            )

            return {
                "success": True,
                "merged_data": merged_boq,
                "merged_images": merged_images,
                "individual_results": successful_results,
                "failed_files": failed_results,
                "summary": {
                    "total_files": len(pdf_paths),
                    "successful": len(successful_results),
                    "failed": len(failed_results),
                    "total_items": len(merged_items),
                    "total_images": len(merged_images)
                }
            }

        return {
            "success": True,
            "individual_results": successful_results,
            "failed_files": failed_results
        }

    async def process_with_floor_plan(
        self,
        boq_pdf_path: str,
        floor_plan_path: str
    ) -> dict:
        """
        處理 BOQ + 平面圖核對數量

        Args:
            boq_pdf_path: BOQ PDF 路徑
            floor_plan_path: 平面圖路徑
        """
        # Step 1: 解析 BOQ
        boq_result = await self.process_boq_pdf(boq_pdf_path, extract_images=True)
        boq_data = boq_result["boq_data"]

        # Step 2: 識別缺少數量的項目
        items_missing_qty = [
            item for item in boq_data.items
            if item.qty is None or item.qty == 0
        ]

        if not items_missing_qty:
            return {
                **boq_result,
                "floor_plan_analysis": None,
                "message": "所有項目已有數量，無需平面圖核對"
            }

        # Step 3: 從平面圖提取數量
        floor_plan_tasks = [
            self.image_analyzer.extract_quantity_from_floor_plan(
                floor_plan_path,
                item.item_no
            )
            for item in items_missing_qty
        ]

        floor_plan_results = await asyncio.gather(
            *floor_plan_tasks,
            return_exceptions=True
        )

        # Step 4: 更新數量
        updated_items = []
        for item in boq_data.items:
            if item.qty is None or item.qty == 0:
                # 找到對應的平面圖結果
                matching_result = next(
                    (r for r in floor_plan_results
                     if not isinstance(r, Exception) and r.get("symbol") == item.item_no),
                    None
                )

                if matching_result and matching_result.get("confidence", 0) > 0.7:
                    # 更新數量（標註來源）
                    item.qty = matching_result["quantity"]
                    item.materials_used = (
                        f"{item.materials_used or ''} "
                        f"[數量來自平面圖，信心分數: {matching_result['confidence']:.2f}]"
                    ).strip()

            updated_items.append(item)

        updated_boq = BOQExtraction(
            items=updated_items,
            total_items=len(updated_items),
            source_file=boq_pdf_path
        )

        return {
            **boq_result,
            "boq_data": updated_boq,
            "floor_plan_analysis": {
                "items_analyzed": len(items_missing_qty),
                "items_updated": sum(
                    1 for r in floor_plan_results
                    if not isinstance(r, Exception) and r.get("confidence", 0) > 0.7
                ),
                "detailed_results": [
                    r for r in floor_plan_results if not isinstance(r, Exception)
                ]
            }
        }
```

### 7.2 FastAPI 路由實作

```python
# backend/app/api/routes/parse.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import asyncio

router = APIRouter(prefix="/api/parse", tags=["PDF Parsing"])

# Request/Response Models
class ParseRequest(BaseModel):
    file_paths: List[str]
    extract_images: bool = True
    verify_images: bool = False
    merge_results: bool = True

class ParseResponse(BaseModel):
    success: bool
    job_id: str
    message: str

class ParseStatusResponse(BaseModel):
    job_id: str
    status: str  # "processing" | "completed" | "failed"
    progress: float
    result: Optional[dict] = None
    error: Optional[str] = None

# 全局服務實例
from app.config import GeminiConfig
config = GeminiConfig()
boq_service = BOQProcessingService(config)

# 簡單的任務追蹤（生產環境應使用 Redis/DB）
processing_jobs = {}

@router.post("/parse", response_model=ParseResponse)
async def parse_pdfs(
    request: ParseRequest,
    background_tasks: BackgroundTasks
):
    """
    解析一個或多個 PDF 檔案

    返回 job_id，可透過 /parse/status/{job_id} 查詢進度
    """
    import uuid
    job_id = str(uuid.uuid4())

    # 初始化任務狀態
    processing_jobs[job_id] = {
        "status": "processing",
        "progress": 0.0,
        "result": None,
        "error": None
    }

    # 背景處理
    background_tasks.add_task(
        _process_pdfs_background,
        job_id,
        request
    )

    return ParseResponse(
        success=True,
        job_id=job_id,
        message=f"已開始處理 {len(request.file_paths)} 個檔案"
    )

async def _process_pdfs_background(job_id: str, request: ParseRequest):
    """背景處理任務"""
    try:
        if len(request.file_paths) == 1:
            # 單檔處理
            result = await boq_service.process_boq_pdf(
                request.file_paths[0],
                extract_images=request.extract_images,
                verify_images=request.verify_images
            )
        else:
            # 多檔處理
            result = await boq_service.process_multiple_pdfs(
                request.file_paths,
                merge_results=request.merge_results
            )

        # 轉換 Pydantic 模型為 dict
        if "boq_data" in result:
            result["boq_data"] = result["boq_data"].model_dump()
        if "merged_data" in result:
            result["merged_data"] = result["merged_data"].model_dump()

        processing_jobs[job_id] = {
            "status": "completed",
            "progress": 1.0,
            "result": result,
            "error": None
        }

    except Exception as e:
        processing_jobs[job_id] = {
            "status": "failed",
            "progress": 0.0,
            "result": None,
            "error": GeminiErrorHandler.get_error_message_zh(e)
        }

@router.get("/parse/status/{job_id}", response_model=ParseStatusResponse)
async def get_parse_status(job_id: str):
    """查詢解析任務狀態"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="找不到該任務")

    job_data = processing_jobs[job_id]
    return ParseStatusResponse(job_id=job_id, **job_data)

@router.post("/parse/with-floor-plan")
async def parse_with_floor_plan(
    boq_file: str,
    floor_plan_file: str,
    background_tasks: BackgroundTasks
):
    """解析 BOQ + 平面圖核對"""
    import uuid
    job_id = str(uuid.uuid4())

    processing_jobs[job_id] = {
        "status": "processing",
        "progress": 0.0,
        "result": None,
        "error": None
    }

    async def _process():
        try:
            result = await boq_service.process_with_floor_plan(
                boq_file, floor_plan_file
            )
            result["boq_data"] = result["boq_data"].model_dump()
            processing_jobs[job_id] = {
                "status": "completed",
                "progress": 1.0,
                "result": result,
                "error": None
            }
        except Exception as e:
            processing_jobs[job_id] = {
                "status": "failed",
                "progress": 0.0,
                "result": None,
                "error": str(e)
            }

    background_tasks.add_task(_process)

    return {"success": True, "job_id": job_id}
```

### 7.3 測試範例

```python
# tests/integration/test_boq_processing.py
import pytest
import asyncio
from pathlib import Path

@pytest.mark.asyncio
async def test_single_pdf_processing():
    """測試單一 PDF 處理"""
    config = GeminiConfig(api_key="test-key")
    service = BOQProcessingService(config)

    # 使用測試 PDF
    test_pdf = "tests/fixtures/sample_boq.pdf"

    result = await service.process_boq_pdf(
        test_pdf,
        extract_images=True,
        verify_images=False
    )

    assert result["boq_data"].total_items > 0
    assert len(result["images"]) >= 0
    assert result["processing_time"] < 60.0  # 應在 60 秒內完成

@pytest.mark.asyncio
async def test_multiple_pdf_merge():
    """測試多 PDF 合併"""
    config = GeminiConfig(api_key="test-key")
    service = BOQProcessingService(config)

    test_pdfs = [
        "tests/fixtures/boq_part1.pdf",
        "tests/fixtures/boq_part2.pdf"
    ]

    result = await service.process_multiple_pdfs(
        test_pdfs,
        merge_results=True
    )

    assert result["success"]
    assert result["summary"]["total_files"] == 2
    assert result["merged_data"].total_items > 0

@pytest.mark.asyncio
async def test_floor_plan_integration():
    """測試平面圖整合"""
    config = GeminiConfig(api_key="test-key")
    service = BOQProcessingService(config)

    result = await service.process_with_floor_plan(
        "tests/fixtures/boq_incomplete.pdf",
        "tests/fixtures/floor_plan.pdf"
    )

    assert "floor_plan_analysis" in result
    assert result["floor_plan_analysis"]["items_updated"] >= 0
```

---

## 總結與建議

### 核心要點

1. **原生 PDF 支援**: Gemini API 原生支援 PDF，無需轉圖片
2. **結構化輸出**: 使用 JSON Mode + Pydantic 確保資料一致性
3. **速率控制**: 實作 Token Bucket 演算法避免超限
4. **錯誤處理**: Exponential Backoff 重試機制
5. **圖片提取**: PyMuPDF 提取 + Gemini 分析組合

### 推薦架構

```
BOQ PDF → FastAPI Upload →
  ├─ Validation (檔案大小、格式)
  ├─ Rate Limiter (控制 API 呼叫)
  ├─ Gemini Parser (結構化提取)
  ├─ PyMuPDF (圖片提取)
  ├─ Gemini Analyzer (圖片驗證/平面圖分析)
  └─ Excel Generator → 惠而蒙格式輸出
```

### 下一步行動

1. **Phase 0 研究**: 驗證 Gemini API 金鑰與配額
2. **Phase 1 實作**: 依照本文檔建立服務架構
3. **Phase 2 測試**: 使用真實 BOQ 文件測試準確度
4. **Phase 3 優化**: 根據測試結果調整 Prompt 與參數

**注意事項**:
- Gemini 3 Flash Preview 尚未正式釋出，請先使用 `gemini-1.5-flash`
- 生產環境建議使用付費版 API 以獲得更高配額
- 定期清理上傳的檔案避免配額耗盡
- 敏感資料（如報價金額）不應傳送至 Gemini API

---

**文檔版本**: 1.0
**最後更新**: 2025-12-19
**作者**: Claude (Anthropic)
**授權**: MIT License
