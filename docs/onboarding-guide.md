# 新人上手指南

歡迎加入家具報價單自動化系統專案！本指南將幫助你快速了解專案架構和開發流程。

## 快速開始

### 1. 環境設定

```bash
# 1. Clone 專案
git clone <repository-url>
cd Fairmont

# 2. 建立 .env 檔案（從範本複製）
cp .env.example .env
# 編輯 .env，填入必要的 API Key

# 3. 後端設定
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
pip install -e ".[dev]"

# 4. 啟動後端
uvicorn app.main:app --reload

# 5. 驗證
curl http://localhost:8000/api/v1/health
```

### 2. 必要環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `GEMINI_API_KEY` | ✅ | Google Gemini AI API Key |
| `API_KEY` | ✅ | 後端 API 認證金鑰 |
| `BACKEND_DEBUG` | 選填 | 設 `true` 啟用詳細日誌 |
| `SKILLS_CACHE_ENABLED` | 選填 | 設 `false` 可即時載入 YAML 變更 |

### 3. Docker 部署

#### 本地開發環境（前端 + 後端）

```bash
docker-compose up -d --build      # 啟動前後端
docker-compose logs -f backend    # 查看後端日誌
docker-compose down               # 停止
```

#### 測試機部署（僅後端）

測試機僅需啟動後端，前端由前端團隊獨立部署，**不會佔用 8501 port**：

```bash
docker-compose -f docker-compose.prod.yml up -d --build   # 啟動後端
docker-compose -f docker-compose.prod.yml logs -f backend # 查看日誌
docker-compose -f docker-compose.prod.yml down            # 停止
```

---

## 專案架構速覽

```
Fairmont/
├── backend/                 # FastAPI 後端
│   ├── app/
│   │   ├── api/routes/     # API 端點（process.py 是主要入口）
│   │   ├── services/       # 業務邏輯（16 個服務）
│   │   ├── models/         # Pydantic 資料模型
│   │   └── utils/          # 工具函式
│   └── tests/              # 測試
├── frontend/               # Streamlit 前端
├── skills/                 # YAML 配置（供應商、輸出格式）
└── docs/                   # 文件
```

### 核心服務說明

| 服務 | 檔案 | 職責 |
|------|------|------|
| **PDFParser** | `pdf_parser.py` | 使用 Gemini AI 解析 PDF 內容 |
| **QuantityParser** | `quantity_parser.py` | 解析數量總表 |
| **MergeService** | `merge_service.py` | 跨表合併邏輯 |
| **ExcelGenerator** | `excel_generator.py` | 產出 Excel 報價單 |
| **SkillLoader** | `skill_loader.py` | 載入 YAML 配置 |

---

## 資料流程

```
上傳 PDF → 文件角色偵測 → PDF 解析 (Gemini AI)
       ↓
   數量總表解析 → 跨表合併 → 面料驗證
       ↓
   圖片提取 + 配對 → Excel 輸出 (17 欄)
```

### 處理階段與進度

| 階段 | 進度 | 說明 |
|------|------|------|
| validating | 0-5% | 驗證 PDF 格式 |
| detecting_roles | 5-10% | 識別文件類型 |
| parsing_detail_specs | 10-70% | Gemini 解析明細表 |
| parsing_quantity_summary | 70-85% | 解析數量總表 |
| merging | 85-95% | 跨表合併 |
| converting | 95-99% | 轉換輸出格式 |
| completed | 100% | 完成 |

---

## Skills 配置系統

這是專案的核心特色，用 YAML 配置取代硬編碼：

```
skills/
├── vendors/habitus.yaml        # 供應商配置（Prompt 模板、圖片規則）
├── output-formats/fairmont.yaml # 輸出格式（欄位、樣式）
└── core/merge-rules.yaml       # 合併規則
```

### 常見修改場景

#### 修改 Prompt 模板

編輯 `skills/vendors/habitus.yaml`：

```yaml
prompts:
  parse_specification:
    user_template: |
      從以下 PDF 內容提取家具項目...
      {pdf_content}
```

#### 修改輸出欄位

編輯 `skills/output-formats/fairmont.yaml`：

```yaml
columns:
  - key: item_no
    header: "Item no."
    width: 15
```

#### 修改面料偵測

編輯 `skills/vendors/habitus.yaml`：

```yaml
fabric_detection:
  patterns:
    - "Vinyl to"
    - "Fabric to"
```

**注意**：開發時設定 `SKILLS_CACHE_ENABLED=false` 可即時看到 YAML 變更。

---

## 主要 API 端點

### POST /api/v1/process

主要整合端點，上傳 PDF 返回解析結果。

```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "files=@test.pdf" \
  -F "extract_images=true"
```

### POST /api/v1/process/stream

SSE 串流版本，返回即時進度：

```bash
curl -N -H "Authorization: Bearer YOUR_API_KEY" \
  -F "files=@test.pdf" \
  http://localhost:8000/api/v1/process/stream
```

**Swagger UI**: `http://localhost:8000/docs`

---

## 資料模型

### BOQItem (核心模型)

```python
class BOQItem:
    no: int                    # 序號
    item_no: str              # 項目編號（如 DLX-100）
    description: str          # 品名
    category: int             # 分類（1=家具, 5=面料）
    affiliate: Optional[str]  # 面料來源家具編號
    dimension: Optional[str]  # 尺寸
    qty: Optional[float]      # 數量
    uom: Optional[str]        # 單位
    # ... 其他欄位
```

### API 回傳 (17 欄 DTO)

| 欄位 | 說明 |
|------|------|
| no | 序號 |
| item_no | 項目編號 |
| description | 品名 |
| photo | Base64 圖片 |
| ... | |
| **category** | 分類（供排序）|
| **affiliate** | 附屬關係 |

---

## 測試

```bash
cd backend

# 執行所有測試
pytest

# 只執行單元測試
pytest -m unit

# 執行特定測試
pytest -k "test_merge"

# 查看覆蓋率
pytest --cov=app --cov-report=term-missing
```

### 測試標記

- `@pytest.mark.unit` - 單元測試
- `@pytest.mark.integration` - 整合測試
- `@pytest.mark.contract` - API 契約測試

---

## 常見問題

### Q: Gemini API 呼叫超時？

A: 檢查 `.env` 中的 `GEMINI_TIMEOUT_SECONDS`（預設 300 秒）。大型 PDF 可能需要更長時間。

### Q: Skills 配置修改沒有生效？

A: 設定 `SKILLS_CACHE_ENABLED=false` 停用快取，或重啟服務。

### Q: 記憶體使用量持續增長？

A: `InMemoryStore` 有 1 小時 TTL，資料會自動清理。若仍有問題，檢查是否有物件引用未釋放。

### Q: 如何新增供應商配置？

A:
1. 複製 `skills/vendors/habitus.yaml` 為新檔案
2. 修改配置內容
3. 在呼叫服務時傳入新的 `vendor_id`

---

## 關鍵程式碼位置

| 功能 | 位置 |
|------|------|
| 主要 API 端點 | `backend/app/api/routes/process.py` |
| PDF 解析核心 | `backend/app/services/pdf_parser.py` |
| 跨表合併邏輯 | `backend/app/services/merge_service.py` |
| Skills 配置載入 | `backend/app/services/skill_loader.py` |
| 資料模型 | `backend/app/models/boq_item.py` |
| 錯誤處理 | `backend/app/utils/errors.py` |

---

## 開發工作流程

1. **建立功能分支**
   ```bash
   git checkout -b feature/xxx
   ```

2. **開發與測試**
   ```bash
   # 啟動開發伺服器
   uvicorn app.main:app --reload

   # 執行測試
   pytest -v
   ```

3. **代碼品質檢查**
   ```bash
   ruff check . --fix
   black .
   ```

4. **提交變更**
   - 使用中文 commit 訊息
   - 遵循專案現有風格

---

## 延伸閱讀

- [架構流程圖](./architecture-flow.md)
- [Excel 輸出規格](./excel-output-spec.md)
- [部署指南](./deployment.md)
- [前端 API 文件](./frontend-api.md)
- [CLAUDE.md](../CLAUDE.md) - 完整專案說明

---

## 聯絡方式

有問題歡迎在 PR 或 Issue 中討論！
