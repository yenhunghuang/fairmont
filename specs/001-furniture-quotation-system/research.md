# Research: 家具報價單系統技術研究

**Feature Branch**: `001-furniture-quotation-system`
**Date**: 2025-12-19
**Status**: Completed
**Updated**: 2025-12-19 - Excel 輸出格式更新（完全比照範本 15 欄）

---

## 0. Excel 範本欄位結構分析

### 研究結果

**來源檔案**: `docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`

**決定**: Excel 輸出共 **15 欄**，完全比照範本格式，不需額外追蹤欄位

**理由**: 使用者明確要求「輸出欄位完全比照範本」

**欄位定義**:

| 欄位 | Excel Column | 寬度 | 說明 | 資料來源 |
|------|--------------|------|------|----------|
| NO. | A | 4.66 | 序號 | 系統自動產生 |
| Item no. | B | 12.66 | 項目編號 | PDF 解析 |
| Description | C | 16.66 | 品名描述 | PDF 解析 |
| Photo | D | 13.0 | 圖片 | PDF 提取，**Base64 編碼** |
| Dimension WxDxH (mm) | E | 29.11 | 尺寸規格 | PDF 解析 |
| Qty | F | 6.66 | 數量 | PDF 解析 |
| UOM | G | 5.66 | 單位 | PDF 解析 |
| Unit Rate (USD) | H | 13.33 | 單價 | **留空**（使用者填寫） |
| Amount (USD) | I | 14.66 | 金額 | **留空**（使用者填寫） |
| Unit CBM | J | 6.66 | 單位材積 | PDF 解析（若有） |
| Total CBM | K | 7.33 | 總材積 | 公式計算 `=F*J` |
| Note | L | 25.66 | 備註 | PDF 解析 |
| Location | M | 13.0 | 位置 | PDF 解析 |
| Materials Used / Specs | N | 13.0 | 材料規格 | PDF 解析 |
| Brand | O | 13.0 | 品牌 | PDF 解析（若有） |

**表頭位置**: Row 16（Row 17 為單位說明行）
**資料起始行**: Row 18

### 圖片處理方式

**決定**: 使用 **Base64 編碼**儲存圖片

**理由**: 使用者明確指定使用 Base64

**實作方式**:
```python
import base64
from io import BytesIO
from openpyxl.drawing.image import Image as XLImage

def embed_base64_image(worksheet, cell: str, base64_data: str, height_cm: float = 3.0):
    """將 Base64 圖片嵌入 Excel 儲存格"""
    image_data = base64.b64decode(base64_data)
    image_stream = BytesIO(image_data)
    img = XLImage(image_stream)

    # 設定尺寸
    pixels_per_cm = 37.795275591
    target_height_px = height_cm * pixels_per_cm
    aspect_ratio = img.width / img.height
    img.height = target_height_px
    img.width = target_height_px * aspect_ratio
    img.anchor = cell

    worksheet.add_image(img)
```

---

## 1. Google Gemini API PDF 解析

### Decision
使用 Google Gemini 3 Flash Preview (`gemini-3-flash-preview`) 透過 `google-generativeai` Python SDK 處理 PDF 文件解析。

### Rationale
1. **原生 PDF 支援**：Gemini API 支援直接上傳 PDF 文件，無需預先轉換為圖片
2. **多模態能力**：可同時處理文字和圖片，適合 BOQ 表格提取
3. **結構化輸出**：支援 JSON 結構化回應，便於資料解析
4. **成本效益**：Flash 模型提供較低成本與較快回應速度

### Alternatives Considered
| 方案 | 優點 | 缺點 | 決定 |
|------|------|------|------|
| Gemini Pro | 更高準確度 | 成本較高、速度較慢 | 備選 |
| OpenAI GPT-4V | 市場成熟 | 需額外 API 金鑰、成本 | 拒絕 |
| 本地 OCR (Tesseract) | 無 API 成本 | 表格識別準確度低 | 拒絕 |
| AWS Textract | 表格識別優秀 | 額外 AWS 費用、複雜度 | 拒絕 |

### Implementation Notes

```python
import google.generativeai as genai
from pathlib import Path

# 設定 API Key
genai.configure(api_key="YOUR_API_KEY")

# 上傳 PDF 文件
def upload_pdf(file_path: str) -> genai.File:
    """上傳 PDF 到 Gemini File API"""
    return genai.upload_file(
        path=file_path,
        mime_type="application/pdf"
    )

# 解析 BOQ 表格
def parse_boq(pdf_file: genai.File) -> dict:
    """使用 Gemini 解析 BOQ 表格資料"""
    model = genai.GenerativeModel("gemini-3-flash-preview")

    prompt = """
    請分析這份 PDF 文件中的 BOQ（Bill of Quantities）表格，
    提取所有活動家具及物料資料，以 JSON 格式回傳：

    {
        "items": [
            {
                "item_no": "項次編號",
                "description": "品名描述",
                "dimension": "尺寸",
                "qty": 數量,
                "uom": "單位",
                "location": "位置",
                "materials_specs": "使用材料/規格"
            }
        ]
    }
    """

    response = model.generate_content(
        [prompt, pdf_file],
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )

    return response.text
```

### API Limits
- **檔案大小**：單檔最大 2GB（PDF 符合需求）
- **Token 限制**：Flash 模型支援 1M tokens context window
- **Rate Limits**：15 RPM（免費版）、1000 RPM（付費版）
- **建議**：實作指數退避重試機制

---

## 2. FastAPI 檔案上傳與長時間任務處理

### Decision
使用 FastAPI 的 `UploadFile` 處理大檔案上傳，搭配 `BackgroundTasks` 處理 PDF 解析長時間任務，使用記憶體字典 + 輪詢機制追蹤任務狀態。

### Rationale
1. **無 Redis 依賴**：使用者明確要求不使用 Redis
2. **簡單部署**：單機環境，無需分散式任務隊列
3. **足夠併發**：`BackgroundTasks` 配合 `asyncio` 可處理 10+ 併發
4. **即時進度**：任務狀態存在記憶體，輪詢回應速度快

### Alternatives Considered
| 方案 | 優點 | 缺點 | 決定 |
|------|------|------|------|
| Celery + Redis | 可靠的任務隊列 | 需 Redis，複雜度高 | 拒絕（使用者要求）|
| ARQ (Redis) | 輕量 async 隊列 | 需 Redis | 拒絕（使用者要求）|
| asyncio.create_task | 簡單 | 無法跨請求追蹤 | 拒絕 |
| BackgroundTasks | 內建、簡單 | 進程重啟任務遺失 | 採用 |
| 檔案系統狀態 | 持久化 | I/O 開銷 | 備選 |

### Implementation Notes

```python
from fastapi import FastAPI, UploadFile, BackgroundTasks, File
from pydantic import BaseModel
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional

app = FastAPI()

# 任務狀態儲存（記憶體）
task_store: Dict[str, dict] = {}

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    message: str
    result: Optional[dict] = None
    error: Optional[str] = None

async def process_pdf_task(task_id: str, file_path: str):
    """背景任務：處理 PDF"""
    try:
        task_store[task_id]["status"] = "processing"

        # 階段 1：上傳到 Gemini
        task_store[task_id]["progress"] = 20
        task_store[task_id]["message"] = "正在上傳文件..."
        await asyncio.sleep(1)  # 實際呼叫 Gemini upload_file

        # 階段 2：解析 BOQ
        task_store[task_id]["progress"] = 50
        task_store[task_id]["message"] = "正在解析 BOQ 表格..."
        await asyncio.sleep(3)  # 實際呼叫 Gemini generate_content

        # 階段 3：提取圖片
        task_store[task_id]["progress"] = 70
        task_store[task_id]["message"] = "正在提取圖片..."
        await asyncio.sleep(2)  # 實際圖片提取

        # 階段 4：產生結果
        task_store[task_id]["progress"] = 100
        task_store[task_id]["status"] = "completed"
        task_store[task_id]["message"] = "處理完成"
        task_store[task_id]["result"] = {"items": [...]}

    except Exception as e:
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["error"] = str(e)

@app.post("/api/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    # 驗證檔案類型與大小
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "僅支援 PDF 檔案")

    # 儲存檔案
    task_id = str(uuid.uuid4())
    file_path = f"temp/{task_id}.pdf"

    with open(file_path, "wb") as f:
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(400, "檔案大小超過 50MB 限制")
        f.write(content)

    # 初始化任務
    task_store[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "等待處理",
        "created_at": datetime.now().isoformat()
    }

    # 加入背景任務
    background_tasks.add_task(process_pdf_task, task_id, file_path)

    return {"task_id": task_id}

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in task_store:
        raise HTTPException(404, "找不到任務")
    return task_store[task_id]
```

### 暫存檔案清理策略
```python
import os
import time
from pathlib import Path

TEMP_DIR = Path("temp")
MAX_AGE_HOURS = 24

async def cleanup_temp_files():
    """定期清理過期暫存檔案"""
    while True:
        now = time.time()
        for f in TEMP_DIR.iterdir():
            if now - f.stat().st_mtime > MAX_AGE_HOURS * 3600:
                f.unlink()
        await asyncio.sleep(3600)  # 每小時執行

# 在應用啟動時啟動清理任務
@app.on_event("startup")
async def startup():
    asyncio.create_task(cleanup_temp_files())
```

---

## 3. PDF 圖片提取

### Decision
使用 PyMuPDF (fitz) 提取 PDF 中的嵌入圖片，配合 Pillow 進行圖片處理。

### Rationale
1. **高效能**：PyMuPDF 是 C 實作，處理速度快
2. **完整功能**：支援圖片提取、頁面渲染、文字提取
3. **跨平台**：Windows/Linux/macOS 皆可使用
4. **主動維護**：持續更新，社群活躍

### Alternatives Considered
| 方案 | 優點 | 缺點 | 決定 |
|------|------|------|------|
| PyMuPDF (fitz) | 快速、功能完整 | 授權 AGPL | 採用 |
| pdf2image + Poppler | 簡單 | 需安裝 Poppler | 備選 |
| pdfplumber | 表格提取強 | 圖片提取弱 | 拒絕 |
| pikepdf | 低階操作 | 學習曲線高 | 拒絕 |

### Implementation Notes

```python
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

def extract_images_from_pdf(
    pdf_path: str,
    output_dir: str,
    min_size: Tuple[int, int] = (100, 100)
) -> List[dict]:
    """
    從 PDF 提取所有圖片

    Args:
        pdf_path: PDF 檔案路徑
        output_dir: 圖片輸出目錄
        min_size: 最小圖片尺寸（過濾小圖示）

    Returns:
        提取的圖片資訊列表
    """
    doc = fitz.open(pdf_path)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    images = []

    for page_num, page in enumerate(doc):
        image_list = page.get_images()

        for img_index, img in enumerate(image_list):
            xref = img[0]  # 圖片 xref

            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # 載入圖片檢查尺寸
                pil_image = Image.open(BytesIO(image_bytes))

                if pil_image.size[0] < min_size[0] or pil_image.size[1] < min_size[1]:
                    continue  # 跳過太小的圖片

                # 儲存圖片
                filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                filepath = output_path / filename

                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                images.append({
                    "filename": filename,
                    "path": str(filepath),
                    "page": page_num + 1,
                    "width": pil_image.size[0],
                    "height": pil_image.size[1],
                    "format": image_ext
                })

            except Exception as e:
                print(f"無法提取圖片 xref={xref}: {e}")
                continue

    doc.close()
    return images
```

---

## 4. Excel 圖片嵌入（惠而蒙格式）

### Decision
使用 openpyxl 產生 Excel 檔案，搭配 `openpyxl.drawing.image.Image` 嵌入圖片到儲存格。

### Rationale
1. **原生 xlsx 支援**：無需額外依賴
2. **圖片嵌入**：完整支援圖片插入與定位
3. **格式控制**：可設定欄寬、列高、樣式
4. **廣泛使用**：社群資源豐富

### Alternatives Considered
| 方案 | 優點 | 缺點 | 決定 |
|------|------|------|------|
| openpyxl | 功能完整 | 大量圖片效能較慢 | 採用 |
| xlsxwriter | 效能好 | 不支援讀取現有檔案 | 備選 |
| pandas + openpyxl | 資料處理方便 | 圖片嵌入仍需 openpyxl | 搭配使用 |

### Implementation Notes

```python
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, Border, Side
from PIL import Image as PILImage
from io import BytesIO
from typing import List
import os

# 惠而蒙格式欄位定義（15 欄，完全比照範本）
# 參考範例：docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx
COLUMNS = [
    ("A", "NO.", 5),
    ("B", "Item no.", 13),
    ("C", "Description", 17),
    ("D", "Photo", 13),
    ("E", "Dimension\nWxDxH", 29),
    ("F", "Qty", 7),
    ("G", "UOM", 6),
    ("H", "Unit Rate", 13),    # 留空 - 使用者填寫
    ("I", "Amount", 15),       # 留空 - 使用者填寫
    ("J", "Unit\nCBM", 7),
    ("K", "Total\nCBM", 7),    # 公式: =F*J
    ("L", "Note", 26),
    ("M", "Location", 13),
    ("N", "Materials Used / Specs", 13),
    ("O", "Brand", 13),
]

def create_quotation_excel(
    items: List[dict],
    output_path: str,
    image_height_cm: float = 3.0
) -> str:
    """
    產生惠而蒙格式 Excel 報價單

    Args:
        items: BOQ 項目列表
        output_path: 輸出檔案路徑
        image_height_cm: 圖片高度（公分）

    Returns:
        輸出檔案路徑
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "報價單"

    # 設定標題樣式
    header_font = Font(bold=True, size=12)
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    # 設定欄位標題與欄寬
    for col_letter, title, width in COLUMNS:
        ws.column_dimensions[col_letter].width = width
        cell = ws[f"{col_letter}1"]
        cell.value = title
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = thin_border

    # 寫入資料
    row_height_points = image_height_cm * 28.35  # 1 cm ≈ 28.35 points

    for row_idx, item in enumerate(items, start=2):
        # 設定列高（容納圖片）
        ws.row_dimensions[row_idx].height = row_height_points

        # 寫入資料（15 欄，完全比照範本）
        ws[f"A{row_idx}"] = item.get("no", row_idx - 1)      # A: NO.
        ws[f"B{row_idx}"] = item.get("item_no", "")          # B: Item no.
        ws[f"C{row_idx}"] = item.get("description", "")      # C: Description
        # D 欄：Photo（Base64 圖片嵌入）
        ws[f"E{row_idx}"] = item.get("dimension", "")        # E: Dimension
        ws[f"F{row_idx}"] = item.get("qty", "")              # F: Qty
        ws[f"G{row_idx}"] = item.get("uom", "")              # G: UOM
        # H: Unit Rate - 留空（使用者填寫）
        # I: Amount - 留空（使用者填寫）
        ws[f"J{row_idx}"] = item.get("unit_cbm", "")         # J: Unit CBM
        # K: Total CBM - 公式
        if item.get("unit_cbm"):
            ws[f"K{row_idx}"] = f"=F{row_idx}*J{row_idx}"
        ws[f"L{row_idx}"] = item.get("note", "")             # L: Note
        ws[f"M{row_idx}"] = item.get("location", "")         # M: Location
        ws[f"N{row_idx}"] = item.get("materials_specs", "")  # N: Materials Used / Specs
        ws[f"O{row_idx}"] = item.get("brand", "")            # O: Brand

        # 嵌入 Base64 圖片
        photo_base64 = item.get("photo_base64")
        if photo_base64:
            try:
                image_data = base64.b64decode(photo_base64)
                image_stream = BytesIO(image_data)
                img = XLImage(image_stream)

                # 調整圖片尺寸
                target_height = image_height_cm * 37.795  # cm to pixels
                aspect_ratio = img.width / img.height
                target_width = target_height * aspect_ratio

                img.width = target_width
                img.height = target_height

                # 定位到 D 欄 (Photo)
                img.anchor = f"D{row_idx}"
                ws.add_image(img)

            except Exception as e:
                ws[f"D{row_idx}"] = f"(圖片載入失敗: {e})"

        # 設定邊框
        for col_letter, _, _ in COLUMNS:
            ws[f"{col_letter}{row_idx}"].border = thin_border
            ws[f"{col_letter}{row_idx}"].alignment = Alignment(
                vertical="center",
                wrap_text=True
            )

    wb.save(output_path)
    return output_path
```

### 效能考量
- 大量圖片（>100 張）時，考慮分批處理
- 圖片預先壓縮到適當尺寸（減少檔案大小）
- 使用 `write_only` 模式處理超大資料集

---

## 5. Streamlit 與 FastAPI 整合

### Decision
Streamlit 透過 `requests` 或 `httpx` 呼叫 FastAPI 後端 API，使用輪詢機制追蹤長時間任務進度。

### Rationale
1. **架構分離**：前後端獨立，易於維護
2. **進度追蹤**：輪詢簡單可靠，無需 WebSocket
3. **Session State**：Streamlit 內建狀態管理
4. **繁體中文**：完全控制 UI 文字

### Alternatives Considered
| 方案 | 優點 | 缺點 | 決定 |
|------|------|------|------|
| REST + 輪詢 | 簡單、可靠 | 輪詢開銷 | 採用 |
| WebSocket | 即時推送 | Streamlit 支援有限 | 拒絕 |
| SSE | 伺服器推送 | 實作複雜 | 拒絕 |

### Implementation Notes

```python
# frontend/services/api_client.py
import httpx
import streamlit as st
from typing import Optional
import time

API_BASE_URL = "http://localhost:8000"

class APIClient:
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def upload_pdf(self, file_bytes: bytes, filename: str) -> dict:
        """上傳 PDF 檔案"""
        response = self.client.post(
            f"{self.base_url}/api/upload",
            files={"file": (filename, file_bytes, "application/pdf")}
        )
        response.raise_for_status()
        return response.json()

    def get_task_status(self, task_id: str) -> dict:
        """取得任務狀態"""
        response = self.client.get(f"{self.base_url}/api/task/{task_id}")
        response.raise_for_status()
        return response.json()

    def wait_for_completion(
        self,
        task_id: str,
        progress_callback=None,
        poll_interval: float = 1.0
    ) -> dict:
        """等待任務完成，並更新進度"""
        while True:
            status = self.get_task_status(task_id)

            if progress_callback:
                progress_callback(status)

            if status["status"] in ("completed", "failed"):
                return status

            time.sleep(poll_interval)

# frontend/pages/upload.py
import streamlit as st
from services.api_client import APIClient

st.set_page_config(page_title="上傳 PDF", page_icon="📄")
st.title("📄 上傳 BOQ PDF")

# 初始化 API 客戶端
if "api_client" not in st.session_state:
    st.session_state.api_client = APIClient()

# 檔案上傳
uploaded_files = st.file_uploader(
    "選擇 PDF 檔案（最多 5 個）",
    type=["pdf"],
    accept_multiple_files=True,
    help="支援標準 PDF 格式，單檔最大 50MB"
)

if uploaded_files:
    st.write(f"已選擇 {len(uploaded_files)} 個檔案")

    if st.button("開始處理", type="primary"):
        for file in uploaded_files:
            with st.status(f"處理中: {file.name}", expanded=True) as status:
                # 上傳檔案
                st.write("正在上傳...")
                result = st.session_state.api_client.upload_pdf(
                    file.getvalue(),
                    file.name
                )
                task_id = result["task_id"]

                # 進度條
                progress_bar = st.progress(0)
                status_text = st.empty()

                # 等待完成
                while True:
                    task_status = st.session_state.api_client.get_task_status(task_id)
                    progress = task_status["progress"]
                    message = task_status["message"]

                    progress_bar.progress(progress / 100)
                    status_text.write(message)

                    if task_status["status"] == "completed":
                        status.update(label=f"✅ {file.name} 處理完成", state="complete")
                        st.session_state[f"result_{task_id}"] = task_status["result"]
                        break
                    elif task_status["status"] == "failed":
                        status.update(label=f"❌ {file.name} 處理失敗", state="error")
                        st.error(task_status["error"])
                        break

                    time.sleep(1)

        st.success("所有檔案處理完成！")
        st.page_link("pages/preview.py", label="前往預覽結果", icon="👉")
```

### Session State 管理
```python
# frontend/utils/session.py
import streamlit as st
from typing import Any, Optional

def get_session(key: str, default: Any = None) -> Any:
    """安全取得 session state 值"""
    return st.session_state.get(key, default)

def set_session(key: str, value: Any):
    """設定 session state 值"""
    st.session_state[key] = value

def clear_session():
    """清除所有 session state"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# 使用範例
# set_session("uploaded_files", files)
# files = get_session("uploaded_files", [])
```

---

## 6. 平面圖數量核對（P2 功能）

### Decision
使用 Gemini 視覺能力分析平面圖，識別家具符號並計數。

### Rationale
1. **多模態 AI**：Gemini 可理解建築圖面
2. **無需訓練**：使用 prompt engineering 引導識別
3. **彈性擴展**：可針對不同圖面調整 prompt

### Implementation Notes

```python
def analyze_floor_plan(
    pdf_file: genai.File,
    missing_items: List[dict]
) -> dict:
    """
    分析平面圖，核對缺失數量

    Args:
        pdf_file: 平面圖 PDF
        missing_items: 需要核對的項目清單

    Returns:
        核對結果
    """
    model = genai.GenerativeModel("gemini-3-flash-preview")

    items_list = "\n".join([
        f"- {item['item_no']}: {item['description']}"
        for item in missing_items
    ])

    prompt = f"""
    這是一份建築平面圖。請分析圖面中的家具符號，
    並核對以下項目的數量：

    {items_list}

    請以 JSON 格式回傳結果：
    {{
        "verified_items": [
            {{
                "item_no": "項次編號",
                "count_from_floor_plan": 數量,
                "confidence": "high/medium/low",
                "notes": "備註（如何識別的說明）"
            }}
        ],
        "unverified_items": ["無法識別的項目 item_no 列表"]
    }}
    """

    response = model.generate_content(
        [prompt, pdf_file],
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )

    return response.text
```

---

## 7. 錯誤處理與繁體中文訊息

### Decision
建立統一的錯誤處理機制，所有使用者可見訊息皆使用繁體中文。

### Implementation Notes

```python
# backend/app/utils/errors.py
from enum import Enum
from fastapi import HTTPException

class ErrorCode(Enum):
    FILE_TOO_LARGE = ("FILE_001", "檔案大小超過限制（最大 50MB）")
    INVALID_FILE_TYPE = ("FILE_002", "不支援的檔案格式，請上傳 PDF 檔案")
    FILE_UPLOAD_FAILED = ("FILE_003", "檔案上傳失敗，請重試")

    PARSE_FAILED = ("PARSE_001", "PDF 解析失敗，請確認檔案格式正確")
    NO_BOQ_FOUND = ("PARSE_002", "未在 PDF 中找到 BOQ 資料")
    IMAGE_EXTRACT_FAILED = ("PARSE_003", "圖片提取失敗")

    GEMINI_API_ERROR = ("API_001", "AI 服務暫時無法使用，請稍後重試")
    RATE_LIMIT_EXCEEDED = ("API_002", "請求過於頻繁，請稍後重試")

    TASK_NOT_FOUND = ("TASK_001", "找不到指定的任務")
    TASK_FAILED = ("TASK_002", "任務執行失敗")

    EXPORT_FAILED = ("EXPORT_001", "Excel 匯出失敗")

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

def raise_error(error: ErrorCode, detail: str = None):
    """拋出標準化錯誤"""
    message = error.message
    if detail:
        message = f"{message}：{detail}"

    raise HTTPException(
        status_code=400,
        detail={
            "error_code": error.code,
            "message": message
        }
    )

# 使用範例
# raise_error(ErrorCode.FILE_TOO_LARGE)
# raise_error(ErrorCode.PARSE_FAILED, "第 3 頁表格格式異常")
```

---

## 8. 依賴套件清單

### Backend (requirements.txt)
```
# Web Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6

# AI/ML
google-generativeai>=0.3.0

# PDF Processing
PyMuPDF>=1.23.0
Pillow>=10.0.0

# Excel Generation
openpyxl>=3.1.0

# Utilities
pydantic>=2.5.0
python-dotenv>=1.0.0
cachetools>=5.3.0

# Dev Dependencies (requirements-dev.txt)
pytest>=7.4.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
httpx>=0.26.0
ruff>=0.1.0
black>=23.0.0
```

### Frontend (requirements.txt)
```
streamlit>=1.30.0
httpx>=0.26.0
Pillow>=10.0.0
```

### E2E Testing
```
playwright>=1.40.0
pytest-playwright>=0.4.0
```

---

## Summary

| 決策項目 | 選定方案 | 關鍵理由 |
|----------|----------|----------|
| PDF 解析 | Gemini 3 Flash Preview | 原生 PDF 支援、結構化輸出 |
| 長時間任務 | BackgroundTasks + 輪詢 | 無 Redis、簡單可靠 |
| 圖片提取 | PyMuPDF | 高效能、功能完整 |
| Excel 產出 | openpyxl | 圖片嵌入支援、格式控制 |
| 前後端通訊 | REST + 輪詢 | 簡單、Streamlit 友好 |
| 平面圖分析 | Gemini 視覺分析 | 多模態 AI、無需訓練 |
