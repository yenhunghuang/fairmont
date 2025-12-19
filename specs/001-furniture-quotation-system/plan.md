# Implementation Plan: 家具報價單系統 (Furniture Quotation System)

**Branch**: `001-furniture-quotation-system` | **Date**: 2025-12-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-furniture-quotation-system/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

建立一個家具報價單自動化系統，讓客戶上傳 BOQ（Bill of Quantities）PDF 文件，系統使用 Google Gemini 3 Flash Preview 模型解析文件內容，自動提取活動家具及物料資料（包含圖片），並產出惠而蒙格式的 Excel 報價單。系統採用 Python FastAPI 後端 + Streamlit 前端架構，支援多檔案上傳與平面圖數量核對功能。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI (後端 API)、Streamlit (前端 UI)、google-generativeai (Gemini API)、PyMuPDF (PDF 處理)、openpyxl (Excel 產出)、Pillow (圖片處理)
**Storage**: 本地檔案系統（暫存上傳檔案與產出檔案），無需資料庫
**Testing**: pytest + pytest-asyncio (單元/整合測試)、Playwright (E2E 測試)
**Target Platform**: Linux/Windows Server、Docker 容器化部署
**Project Type**: Web Application (前後端分離)
**Performance Goals**: 單檔 PDF (<50MB) 解析完成時間 <5 分鐘、API 回應 <200ms (標準請求)、Gemini API 呼叫 <15 秒
**Constraints**: 無 Redis 快取、單機部署、支援 10+ 併發使用者、暫存檔案定期清理
**Scale/Scope**: 單機服務、支援同時處理 5 個 PDF 檔案、每檔最大 50MB

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. 代碼品質 (Code Quality)
| 要求 | 符合性 | 說明 |
|------|--------|------|
| 自文檔化代碼，命名清晰 | ✅ PASS | 使用 Python type hints、清晰函數/變數命名 |
| 合併前強制代碼審查 | ✅ PASS | Git workflow 執行 PR review |
| 語法檢查/格式化零警告 | ✅ PASS | 使用 ruff + black 確保代碼品質 |
| 公共 API 內嵌文件 | ✅ PASS | FastAPI OpenAPI 自動產生、docstrings |
| 第三方依賴安全審查 | ✅ PASS | 使用知名套件、定期更新 |

### II. 測試標準 (Testing Standards - NON-NEGOTIABLE)
| 要求 | 符合性 | 說明 |
|------|--------|------|
| 測試優先開發 | ✅ PASS | 採用 TDD 流程 |
| 最低 80% 代碼覆蓋率 | ✅ PASS | pytest-cov 監控覆蓋率 |
| 單元/整合/E2E 測試 | ✅ PASS | pytest + Playwright |
| 合併前測試通過 | ✅ PASS | CI/CD pipeline 驗證 |

### III. UX 一致性 (UX Consistency)
| 要求 | 符合性 | 說明 |
|------|--------|------|
| WCAG 2.1 Level AA | ✅ PASS | Streamlit 預設支援基本可訪問性 |
| 響應式設計 | ✅ PASS | Streamlit 自動響應式佈局 |
| 繁體中文錯誤訊息 | ✅ PASS | 所有使用者訊息使用繁體中文 |
| 載入狀態 (>100ms) | ✅ PASS | Streamlit spinner/progress bar |
| 國際化支援 | ⚠️ N/A | 初版僅支援繁體中文 |

### IV. 效能要求 (Performance Standards)
| 要求 | 符合性 | 說明 |
|------|--------|------|
| API <200ms (p95) | ✅ PASS | 標準請求符合、PDF 解析例外（長時間任務） |
| Q&A <15 秒 | ✅ PASS | Gemini API 單次呼叫 <15 秒 |
| 頁面載入 <2 秒 | ✅ PASS | Streamlit 輕量化前端 |
| 10+ 併發使用者 | ✅ PASS | FastAPI async 支援 |
| 資料庫查詢索引 | ⚠️ N/A | 無資料庫，使用檔案系統 |
| 快取機制 | ⚠️ N/A | 無 Redis（使用者指定），使用記憶體快取替代 |

### V. 語言要求 (Language Requirements)
| 要求 | 符合性 | 說明 |
|------|--------|------|
| 繁體中文文件/UI | ✅ PASS | 規格、UI、錯誤訊息皆使用繁體中文 |
| 英文代碼註解 | ✅ PASS | 代碼註解允許使用英文 |

**Constitution Gate**: ✅ **PASS** - 所有必要項目符合或標示為不適用

## Project Structure

### Documentation (this feature)

```text
specs/001-furniture-quotation-system/
├── plan.md              # 實作計畫（本文件）
├── research.md          # Phase 0 研究輸出
├── data-model.md        # Phase 1 資料模型設計
├── quickstart.md        # Phase 1 快速開始指南
├── contracts/           # Phase 1 API 規格
│   └── openapi.yaml     # OpenAPI 3.0 規格
└── tasks.md             # Phase 2 任務清單（由 /speckit.tasks 產生）
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 應用程式入口
│   ├── config.py            # 設定檔（Gemini API Key 等）
│   ├── models/
│   │   ├── __init__.py
│   │   ├── boq_item.py      # BOQ 項目資料模型
│   │   ├── quotation.py     # 報價單資料模型
│   │   └── source_document.py  # 來源文件資料模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py    # PDF 解析服務（Gemini 整合）
│   │   ├── image_extractor.py  # 圖片提取服務
│   │   ├── excel_generator.py  # Excel 產出服務（惠而蒙格式）
│   │   └── floor_plan_analyzer.py  # 平面圖分析服務
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py    # 檔案上傳 API
│   │   │   ├── parse.py     # PDF 解析 API
│   │   │   └── export.py    # Excel 匯出 API
│   │   └── dependencies.py  # API 依賴注入
│   └── utils/
│       ├── __init__.py
│       ├── file_manager.py  # 暫存檔案管理
│       └── validators.py    # 輸入驗證
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures
│   ├── unit/
│   │   ├── test_pdf_parser.py
│   │   ├── test_excel_generator.py
│   │   └── test_image_extractor.py
│   ├── integration/
│   │   ├── test_upload_flow.py
│   │   └── test_parse_export_flow.py
│   └── contract/
│       └── test_api_contracts.py
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml

frontend/
├── app.py                   # Streamlit 主程式
├── pages/
│   ├── __init__.py
│   ├── upload.py            # 上傳頁面
│   ├── preview.py           # 預覽頁面
│   └── verification.py      # 驗證頁面
├── components/
│   ├── __init__.py
│   ├── file_uploader.py     # 檔案上傳元件
│   ├── progress_display.py  # 進度顯示元件
│   ├── material_table.py    # 材料表格元件
│   └── source_reference.py  # 來源參照元件
├── services/
│   ├── __init__.py
│   └── api_client.py        # 後端 API 客戶端
├── tests/
│   ├── __init__.py
│   └── e2e/
│       └── test_full_flow.py  # E2E 測試（Playwright）
└── requirements.txt

# 根目錄設定檔
├── docker-compose.yml       # 容器化部署
├── Dockerfile.backend
├── Dockerfile.frontend
├── .env.example             # 環境變數範本
└── README.md
```

**Structure Decision**: 採用 Web Application 結構（Option 2），前後端分離。後端使用 FastAPI 提供 RESTful API，前端使用 Streamlit 作為使用者介面。選擇此結構因為：
1. 符合 FR-013 前後端分離架構要求
2. FastAPI 提供高效能 async 處理，適合 PDF 解析長時間任務
3. Streamlit 快速建構可視化介面，符合 POC 需求

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 無 Redis 快取 | 使用者明確要求不使用 Redis | 使用 Python 記憶體快取 (cachetools) 作為替代方案，足以應付 10+ 併發使用者 |

**備註**：無其他憲法違規事項需要說明。

---

## Post-Design Constitution Re-Check (Phase 1 Complete)

*驗證日期*: 2025-12-19

設計階段完成後重新評估憲法符合性：

| 設計產出 | 憲法要求 | 評估結果 |
|----------|----------|----------|
| data-model.md | Pydantic 模型含完整 type hints 和驗證 | ✅ 符合代碼品質 |
| contracts/openapi.yaml | OpenAPI 3.0 完整規格、繁體中文描述 | ✅ 符合文件要求 |
| research.md | 技術決策有明確理由、替代方案評估 | ✅ 符合決策透明度 |
| quickstart.md | 繁體中文指南、含測試執行說明 | ✅ 符合語言和測試要求 |
| Project Structure | 前後端分離、tests/ 目錄規劃 | ✅ 符合架構要求 |

**Post-Design Gate**: ✅ **PASS** - 所有設計產出符合憲法要求

---

## Phase 1 設計產出摘要

| 產出物 | 檔案路徑 | 狀態 |
|--------|----------|------|
| 技術研究 | `specs/001-furniture-quotation-system/research.md` | ✅ 完成 |
| 資料模型 | `specs/001-furniture-quotation-system/data-model.md` | ✅ 完成 |
| API 規格 | `specs/001-furniture-quotation-system/contracts/openapi.yaml` | ✅ 完成 |
| 快速開始 | `specs/001-furniture-quotation-system/quickstart.md` | ✅ 完成 |
| Agent Context | `CLAUDE.md` | ✅ 完成 |

**下一步**：執行 `/speckit.tasks` 產生開發任務清單
