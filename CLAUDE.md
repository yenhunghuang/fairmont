# Claude Code Context: 家具報價單系統

## 專案概述

家具報價單自動化系統，讓客戶上傳 BOQ（Bill of Quantities）PDF 文件，使用 Google Gemini AI 解析內容，自動產出惠而蒙格式 Excel 報價單。

## 技術堆疊

<!-- SPECIFY:TECH_STACK:START -->
- **語言**: Python 3.11+
- **後端框架**: FastAPI
- **前端框架**: Streamlit
- **AI 服務**: Google Gemini 3 Flash Preview (gemini-3-flash-preview)
- **PDF 處理**: PyMuPDF (fitz)
- **Excel 產出**: openpyxl
- **圖片處理**: Pillow
- **測試**: pytest, pytest-asyncio, Playwright
- **程式碼品質**: ruff, black
<!-- SPECIFY:TECH_STACK:END -->

## 專案結構

```
backend/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 設定（含 Gemini API Key）
│   ├── models/              # Pydantic 資料模型
│   ├── services/            # 業務邏輯服務
│   │   ├── pdf_parser.py    # PDF 解析（Gemini 整合）
│   │   ├── image_extractor.py
│   │   ├── excel_generator.py
│   │   └── floor_plan_analyzer.py
│   ├── api/routes/          # API 路由
│   └── utils/               # 工具函式
├── tests/
└── requirements.txt

frontend/
├── app.py                   # Streamlit 主程式
├── pages/                   # 頁面
├── components/              # UI 元件
├── services/api_client.py   # 後端 API 客戶端
└── requirements.txt
```

## 開發指引

### 啟動服務

```bash
# 後端
cd backend && uvicorn app.main:app --reload

# 前端
cd frontend && streamlit run app.py
```

### 程式碼規範

- 使用 type hints
- 遵循 PEP 8（使用 ruff + black）
- 公共 API 必須有 docstrings
- 錯誤訊息使用繁體中文
- 測試覆蓋率 ≥ 80%

### 關鍵檔案

- 規格: `specs/001-furniture-quotation-system/spec.md`
- 計畫: `specs/001-furniture-quotation-system/plan.md`
- 資料模型: `specs/001-furniture-quotation-system/data-model.md`
- API 規格: `specs/001-furniture-quotation-system/contracts/openapi.yaml`

## 惠而蒙格式說明

Excel 報價單使用 10 欄格式（排除價格/金額欄位）：

| 欄位 | 說明 |
|------|------|
| A: NO. | 序號（系統產生） |
| B: Item No. | 項目編號 |
| C: Description | 描述 |
| D: Photo | 照片（嵌入圖片） |
| E: Dimension | 尺寸 WxDxH (mm) |
| F: Qty | 數量 |
| G: UOM | 單位 |
| H: Note | 備註 |
| I: Location | 位置 |
| J: Materials Used / Specs | 材料/規格 |

**範例檔案**: `docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx`

## 重要注意事項

1. **無 Redis**: 使用記憶體儲存任務狀態
2. **無資料庫**: 使用檔案系統暫存
3. **Gemini API**: 需設定 `GEMINI_API_KEY` 環境變數
4. **檔案限制**: 單檔最大 50MB，最多 5 個檔案
5. **價格欄位**: Unit Rate, Amount, CBM 由用戶手動填寫，系統不產生

## 憲法規範

- 測試優先開發
- 代碼覆蓋率 ≥ 80%
- API 回應 <200ms (標準請求)
- 所有 UI 文字使用繁體中文
