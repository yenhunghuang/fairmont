# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

家具報價單自動化系統 - 上傳 BOQ（Bill of Quantities）PDF 檔案，使用 Google Gemini AI 解析內容，自動產出惠而蒙格式 Excel 報價單（17 欄）。

**API 基礎路徑**: `/api/v1/`

## 常用開發指令

### 後端 (FastAPI)

```bash
cd backend
pip install -r requirements.txt
pip install -e ".[dev]"

# 啟動
uvicorn app.main:app --reload

# 測試
pytest                              # 所有測試（含覆蓋率）
pytest tests/unit/                  # 單元測試
pytest tests/integration/           # 整合測試
pytest -k "test_specific_name"      # 特定測試
pytest -v --cov-report=term-missing # 覆蓋率報告

# 程式碼品質
ruff check . --fix && black .       # 檢查 + 格式化（行寬 100）
```

### 前端 (Streamlit)

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### Docker 部署

#### 本地開發環境（前端 + 後端）

```bash
docker-compose up -d --build      # 啟動前後端
docker-compose restart            # 重啟（.env 變更後）
docker-compose logs -f backend    # 查看後端日誌
docker-compose logs -f frontend   # 查看前端日誌
docker-compose down               # 停止
```

#### 生產/測試環境（僅後端）

前端由前端工程師團隊獨立部署，測試機僅需啟動後端：

```bash
docker-compose -f docker-compose.prod.yml up -d --build      # 啟動後端
docker-compose -f docker-compose.prod.yml restart            # 重啟
docker-compose -f docker-compose.prod.yml logs -f backend    # 查看日誌
docker-compose -f docker-compose.prod.yml down               # 停止
```

### 環境設定

在專案根目錄建立 `.env`：

**必填**：`GEMINI_API_KEY`, `API_KEY`

**選用**（含預設值）：
- `GEMINI_MODEL=gemini-3-flash-preview`, `GEMINI_TIMEOUT_SECONDS=300`, `GEMINI_MAX_RETRIES=2`
- `SKILLS_CACHE_ENABLED=true`（開發時設 `false` 以即時載入 YAML 變更）
- `BACKEND_DEBUG=false`（設 `true` 啟用詳細日誌）
- `MAX_FILE_SIZE_MB=50`, `MAX_FILES=5`
- Langfuse 可觀測性：`LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`

**Swagger UI**: `http://localhost:8000/docs`（需輸入 API_KEY）

## 非協商性標準

- **測試優先**: 編寫測試 → 驗證失敗 → 實作 → 驗證通過
- **覆蓋率**: >= 80%（關鍵路徑 100%）
- **效能**: API < 200ms (p95)，PDF 解析 1-6 分鐘（含 Skills 載入 + Gemini AI）
- **語言**: 錯誤訊息、文件使用繁體中文；程式碼可用英文
- **Python 版本**: >= 3.11

## 架構概述

### 資料流程

```
上傳 PDF → Skills 載入 → PDFParserService (Gemini AI) → BOQItem 列表 + 圖片匹配 → Excel 產出
```

### 關鍵檔案

| 檔案 | 用途 |
|------|------|
| `backend/app/api/routes/process.py` | 主要 API 端點（/process, /process/stream）|
| `backend/app/services/pdf_parser.py` | Gemini AI 解析核心 |
| `backend/app/services/quantity_parser.py` | 數量總表解析 |
| `backend/app/services/merge_service.py` | 跨表合併與面料排序 |
| `backend/app/services/fabric_validator.py` | 面料驗證與過濾 |
| `backend/app/services/skill_loader.py` | Skills YAML 配置載入 |
| `backend/app/models/boq_item.py` | BOQItem 資料模型 |
| `backend/app/models/progress.py` | SSE 進度追蹤模型 |
| `backend/app/store.py` | 記憶體儲存（InMemoryStore）|

### 關鍵架構模式

1. **記憶體儲存** (`store.py`): `InMemoryStore` 單例 + TTL 快取（1 小時），無資料庫
2. **服務單例**: 透過 `get_*()` 工廠函式取得（如 `get_pdf_parser()`）
3. **依賴注入**: `dependencies.py` 提供 `StoreDep`、`FileManagerDep` 等
4. **錯誤處理**: `raise_error(ErrorCode.XXX, "訊息")` 拋出 API 錯誤
5. **Skills 架構**: YAML 配置取代硬編碼（供應商規則、輸出格式、合併規則）

## Skills 配置架構

### 配置化邊界設計

| 變動來源 | 頻率 | 配置策略 |
|---------|------|---------|
| 客戶輸出格式（惠而蒙 Excel） | 低 | 硬編碼或 `output-formats/` |
| 供應商 PDF 格式（Habitus 等） | 高 | `vendors/{id}/` 目錄或 `vendors/{id}.yaml` |
| 排序演算法、Item No. 正規化 | 低 | 硬編碼（`merge_service.py`） |
| 面料偵測 Pattern、圖片規則 | 高 | `vendors/{id}/` 目錄配置 |

### Skills 目錄結構

```
skills/
├── vendors/
│   └── habitus/                    # 供應商配置（目錄結構）
│       ├── _vendor.yaml            # 供應商基本資訊（必要）
│       ├── document-types.yaml     # 文件類型定義
│       ├── document-structure.yaml # 頁面結構
│       ├── image-extraction.yaml   # 圖片抓取規則
│       ├── dimension-rules.yaml    # Dimension 格式化
│       ├── fabric-detection.yaml   # 面料偵測規則
│       ├── field-extraction.yaml   # 欄位提取規則
│       └── prompts/                # Prompt 模板
│           ├── parse-specification.yaml
│           ├── parse-quantity-summary.yaml
│           └── parse-project-metadata.yaml
├── output-formats/fairmont.yaml    # 輸出格式（15 欄定義、樣式、條款）
└── core/merge-rules.yaml           # 合併規則（角色偵測、欄位合併策略）
```

**載入優先順序**：目錄結構 > 單檔（`{vendor_id}.yaml`）

**POC 階段固定使用**：`vendor_id="habitus"`, `format_id="fairmont"`

### 服務與 Skill 對應

| 服務 | 使用的 Skill | 用途 |
|------|-------------|------|
| `pdf_parser.py` | VendorSkill | Prompt 模板 |
| `quantity_parser.py` | VendorSkill | 數量總表 Prompt |
| `excel_generator.py` | OutputFormatSkill | 欄位/樣式 |
| `merge_service.py` | MergeRulesSkill + VendorSkill | 合併策略、面料偵測 |
| `document_role_detector.py` | MergeRulesSkill | 角色偵測關鍵字 |
| `image_matcher_deterministic.py` | VendorSkill | 圖片排除規則、頁面偏移 |
| `dimension_formatter.py` | VendorSkill | Dimension 格式化關鍵字 |

### 欄位格式規範（habitus/prompts/parse-specification.yaml）

| 欄位 | 家具 (furniture) | 面料 (fabric) |
|------|-----------------|--------------|
| dimension | `W x D x H mm` 或 `Dia.直徑 x H高` | `材料類型-Vendor-Pattern-Color-Width` |
| materials_specs | FURNITURE COM: 區塊的搭配材料清單 | 完整規格（Pattern/Color/Content 等）|
| description | 品名（如 King Bed） | `<類型> to <家具編號>`（如 Vinyl to DLX-100）|
| brand | 明確品牌名或 null | **必填**：從 Vendor 提取 |

## 合併與排序邏輯

### 面料跟隨家具排序

硬編碼於 `merge_service.py`（客戶輸出格式需求）：
- 家具按 item_no 排序
- 面料插入到其引用的家具之後
- 同一面料引用多個家具時，重複出現在每個家具後
- 面料偵測 Pattern 從 `vendors/*.yaml` 載入

```python
# 輸入: A-001, B-001, FAB-001 (to A-001 and to B-001)
# 輸出: A-001, FAB-001, B-001, FAB-001
```

### 欄位合併策略

從 `core/merge-rules.yaml` 載入：
- `fill_empty`: 先上傳優先，空值填補（預設）
- `concatenate`: 串接多個值
  - `location`: 用 `, ` 分隔
  - `note`: 用 `; ` 分隔

## 圖片匹配系統

確定性演算法（非 Vision API）：
- **演算法**: 頁面偏移匹配（第 N 頁項目 → 第 N+offset 頁圖片）
- **偏移配置**: `vendors/*.yaml` 的 `image_extraction.page_offset`
- **排除規則**: Logo、色票、工程圖過濾
- **效能**: < 100ms/PDF

```yaml
# skills/vendors/habitus/image-extraction.yaml
image_extraction:
  page_offset:
    default: 1
    by_document_type:
      furniture_specification: 1
      quantity_summary: 0
```

## 技術限制

- 無 Redis/資料庫，狀態存於記憶體（1 小時 TTL）
- 單檔最大 50MB，每次最多 5 個檔案
- 單次處理最大 200 頁 PDF
- 跨表合併：最多 1 個數量總表

## 關鍵模式

### Response DTO

```python
# 內部使用
BOQItem          # 完整資料模型，含追蹤欄位（source_type, qty_verified, merge_status 等）

# API 回傳（/process 端點）
ProcessResponse  # 包含 project_name + items 列表
FairmontItemResponse  # 17 欄位 DTO（含 category, affiliate）
# 轉換：FairmontItemResponse.from_boq_item(item)
```

### 錯誤處理

```python
from app.utils.errors import raise_error, ErrorCode
raise_error(ErrorCode.DOCUMENT_NOT_FOUND, "文件不存在", status_code=404)
```

### 新增服務

```python
# services/my_service.py
class MyService:
    def __init__(self, skill_loader: SkillLoader):
        self.skill_loader = skill_loader

_my_service: MyService | None = None

def get_my_service() -> MyService:
    global _my_service
    if _my_service is None:
        _my_service = MyService(get_skill_loader())
    return _my_service
```

## 輸出格式

### API 回傳（17 欄）

供前端同事設計 UI 與 Excel 輸出使用：
- 前 15 欄：對應客戶 Excel 格式
- **category**: 分類（1=家具, 5=面料）— 供排序與分組
- **affiliate**: 附屬（面料來源的家具編號，多個用 `, ` 分隔）— 供關聯顯示

### 客戶 Excel 輸出（15 欄）

NO. / Item no. / Description / Photo / Dimension / Qty / UOM / Unit Rate / Amount / Unit CBM / Total CBM / Note / Location / Materials / Brand

- Unit Rate、Amount 留空由使用者填寫
- 配置：`skills/output-formats/fairmont.yaml`

## API 端點

### 主要端點（前端使用）

```http
POST /api/v1/process
Authorization: Bearer <API_KEY>
Content-Type: multipart/form-data
```

上傳 PDF → 返回 `ProcessResponse`（含 `project_name` + `items` 列表）。處理時間約 1-6 分鐘，前端 timeout 建議 **360 秒以上**。

| 參數 | 類型 | 說明 |
|------|------|------|
| files | File[] | PDF 檔案（最多 5 個，單檔 ≤ 50MB）|
| extract_images | bool | 是否提取圖片（預設 true）|

**回傳結構**：
```json
{
  "project_name": "SOLAIRE BAY TOWER",
  "items": [{ "no": 1, "item_no": "DLX-100", ... }]
}
```

### SSE 串流端點（即時進度）

```http
POST /api/v1/process/stream
```

與 `/process` 相同參數，透過 SSE 串流返回即時進度。

**SSE 事件類型**：
- `progress`: 進度更新 `{stage, progress, message, detail?}`
- `result`: 處理完成 `{project_name, items[], statistics}`
- `error`: 錯誤 `{code, message, stage?}`

**進度階段**：validating (0-5%) → detecting_roles (5-10%) → parsing_detail_specs (10-70%) → parsing_quantity_summary (70-85%) → merging (85-95%) → converting (95-99%) → completed (100%)

```bash
curl -N -H "Authorization: Bearer YOUR_API_KEY" \
     -F "files=@test.pdf" \
     http://localhost:8000/api/v1/process/stream
```

### 其他端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/api/v1/health` | GET | 健康檢查 |
| `/api/v1/documents` | POST | 上傳 PDF |
| `/api/v1/documents/{id}/parse-result` | GET | 取得 BOQ 項目 |
| `/api/v1/quotations` | POST | 建立報價單 |
| `/api/v1/quotations/{id}/excel` | GET | 下載 Excel |
| `/api/v1/tasks/{id}` | GET | 查詢任務狀態 |

## 規格文件

- 功能規格：`specs/001-furniture-quotation-system/spec.md`
- 資料模型：`specs/001-furniture-quotation-system/data-model.md`
- OpenAPI：`specs/001-furniture-quotation-system/contracts/openapi.yaml`

## 測試

### 測試標記與執行

```bash
pytest -m unit           # 單元測試
pytest -m integration    # 整合測試
pytest -m contract       # 契約測試
pytest -m slow           # 慢速測試
```

### 測試 Fixtures（conftest.py）

| Fixture | 用途 |
|---------|------|
| `client` | FastAPI TestClient |
| `mock_store` | InMemoryStore（TTL 60s）|
| `temp_dir` | 自動清理的暫存目錄 |
| `sample_pdf_file` | 最小化 PDF 測試檔 |
| `sample_boq_item_data` | BOQ 項目資料 dict |
| `sample_boq_items_for_merge` | 合併測試用 BOQ 列表 |
| `sample_quantity_summary_items` | 數量總表項目 |

**API 測試常數**：`API_PREFIX = "/api/v1"`（定義於 conftest.py）

### 手動 API 測試

```bash
# 健康檢查
curl -s http://localhost:8000/api/v1/health

# PDF 解析（timeout 建議 300s+）
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "files=@path/to/file.pdf" \
  -F "extract_images=false" \
  --max-time 300
```

## Windows/Git Bash 注意事項

- **路徑**: 使用正斜線（`cd backend`）而非反斜線
- **空格/特殊字元**: 用雙引號包覆（`curl -F "files=@docs/Casegoods & Seatings.pdf"`）
- **pytest**: 使用 `python -m pytest` 確保模組路徑正確
