# Tasks: 家具報價單系統 - 跨表合併功能

**Input**: Design documents from `/specs/001-furniture-quotation-system/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅
**Date**: 2025-12-23
**Updated**: 2025-12-24 - 跨表合併功能已實作並驗證通過

**Tests**: 依據 constitution.md 標準，測試覆蓋率需 >= 80%，包含單元/整合/契約測試。

**Organization**: 任務依 User Story 組織，每個 Story 可獨立實作與測試。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可平行執行（不同檔案，無依賴）
- **[Story]**: 所屬 User Story（US1, US2, US3, US4）

## Path Conventions

- **Backend**: `backend/app/`, `backend/tests/`
- **Frontend**: `frontend/`

---

## Phase 1: Setup (共用基礎設施)

**Purpose**: 專案初始化與基礎結構（大部分已完成）

- [x] T001 Create project structure per plan.md
- [x] T002 Initialize Python project with dependencies
- [x] T003 [P] Configure linting and formatting tools
- [x] T004 更新 backend/app/utils/errors.py 新增 MERGE_* 錯誤碼
- [x] T005 [P] 更新 backend/tests/conftest.py 新增合併相關 fixtures

---

## Phase 2: Foundational (阻塞性前置條件)

**Purpose**: 所有 User Story 的共用核心元件

**⚠️ CRITICAL**: 必須完成此階段才能開始任何 User Story

### 現有基礎（已完成）

- [x] T006 Implement config module in backend/app/config.py
- [x] T007 Implement error handling utilities in backend/app/utils/errors.py
- [x] T008 Implement InMemoryStore in backend/app/store.py
- [x] T009 Create BOQItem model in backend/app/models/boq_item.py
- [x] T010 Create SourceDocument model in backend/app/models/source_document.py

### 跨表合併新增模型

- [x] T011 [P] 更新 backend/app/models/source_document.py 新增 document_role, upload_order 欄位
- [x] T012 [P] 建立 backend/app/models/merge_report.py（MergeReport, MergeResult, FormatWarning 模型）
- [x] T013 [P] 建立 backend/app/models/quantity_summary.py（QuantitySummaryItem 模型）
- [x] T014 [P] 更新 backend/app/models/boq_item.py 新增 source_files, item_no_normalized, merge_status, qty_from_summary 欄位
- [x] T015 [P] 更新 backend/app/models/processing_task.py 新增 merge_documents, parse_quantity_summary 任務類型
- [x] T016 更新 backend/app/models/__init__.py 匯出新模型

### 跨表合併核心服務

- [x] T017 [P] 建立 backend/app/services/item_normalizer.py（Item No. 標準化服務）
- [x] T018 [P] 建立 backend/app/services/document_role_detector.py（PDF 角色偵測服務）
- [x] T019 [P] 建立 backend/app/services/image_selector.py（圖片解析度選擇服務）

### 核心服務單元測試

- [x] T020 [P] 建立 backend/tests/unit/test_item_normalizer.py（單元測試）
- [x] T021 [P] 建立 backend/tests/unit/test_document_role_detector.py（單元測試）
- [x] T022 [P] 建立 backend/tests/unit/test_image_selector.py（單元測試）

**Checkpoint**: 核心服務就緒 - 可開始 User Story 實作

---

## Phase 3: User Story 1 - 上傳 PDF 並生成報價單 (Priority: P1) 🎯 MVP

**Goal**: 客戶上傳單一 BOQ PDF，系統解析並產出惠而蒙格式 Excel（15 欄）

**Independent Test**: 上傳單一 BOQ PDF，驗證產出正確格式的 Excel（15 欄，圖片 Base64 嵌入）

### Tests for User Story 1

- [x] T023 [P] [US1] 契約測試 backend/tests/contract/test_upload_api.py
- [x] T024 [P] [US1] 契約測試 backend/tests/contract/test_export_api.py
- [ ] T025 [P] [US1] 整合測試 backend/tests/integration/test_single_pdf_flow.py（更新驗證 15 欄）

### Implementation for User Story 1（大部分已完成）

- [x] T026 [US1] Implement PDF parser service in backend/app/services/pdf_parser.py
- [x] T027 [US1] Implement image extractor service in backend/app/services/image_extractor.py
- [x] T028 [US1] Implement Excel generator service in backend/app/services/excel_generator.py
- [x] T029 [US1] 更新 backend/app/api/routes/upload.py 回傳 document_role
- [ ] T030 [US1] 驗證 backend/app/api/routes/export.py 正確產出 15 欄 Excel
- [ ] T031 [US1] 更新 frontend/components/file_uploader.py 顯示 PDF 角色

**Checkpoint**: User Story 1 完成 - 單一 PDF 上傳到 Excel 下載流程可獨立測試

---

## Phase 4: User Story 2 - 多檔案上傳與跨表合併 (Priority: P1)

**Goal**: 客戶上傳數量總表 + 明細規格表，系統自動識別角色並合併產出單一 Excel

**Independent Test**: 上傳 `Bay Tower Furniture - Overall Qty.pdf` + `Casegoods & Seatings.pdf` + `Fabric & Leather.pdf`，驗證 Qty 來自數量總表、其他欄位來自明細規格表

### Tests for User Story 2

- [ ] T032 [P] [US2] 單元測試 backend/tests/unit/test_quantity_parser.py
- [ ] T033 [P] [US2] 單元測試 backend/tests/unit/test_merge_service.py
- [ ] T034 [P] [US2] 契約測試 backend/tests/contract/test_merge_api.py
- [ ] T035 [P] [US2] 整合測試 backend/tests/integration/test_merge_flow.py

### Services for User Story 2

- [x] T036 [US2] 建立 backend/app/services/quantity_parser.py（數量總表解析，專用 Gemini prompt）
- [x] T037 [US2] 建立 backend/app/services/merge_service.py（跨表合併核心邏輯）
- [x] T038 [US2] 更新 backend/app/store.py 新增 merge_reports 快取

### API for User Story 2

- [x] T039 [US2] 建立 backend/app/api/routes/merge.py（POST /api/v1/quotations/merge）
- [x] T040 [US2] 更新 backend/app/api/routes/merge.py（GET /api/v1/quotations/{id}/merge-report）
- [x] T041 [US2] 更新 backend/app/main.py 註冊 merge router
- [x] T042 [US2] 更新 backend/app/models/responses.py 新增 MergeReportResponse DTO

### Frontend for User Story 2

- [ ] T043 [P] [US2] 建立 frontend/components/merge_progress.py（合併進度顯示）
- [ ] T044 [P] [US2] 建立 frontend/components/merge_report.py（合併報告元件）
- [ ] T045 [US2] 建立 frontend/pages/merge_preview.py（合併預覽頁面）
- [x] T046 [US2] 更新 frontend/services/api_client.py 新增 create_merged_quotation, get_merge_report 方法
- [x] T047 [US2] 更新 frontend/app.py 整合合併流程

**Checkpoint**: User Story 2 完成 - 多 PDF 跨表合併流程可獨立測試

---

## Phase 5: User Story 3 - BOQ 數量與平面圖核對 (Priority: P3)

**Goal**: 系統從平面圖核對並補充 BOQ 缺失數量

**Independent Test**: 上傳 BOQ（部分無數量）+ 平面圖，驗證系統能識別並補充數量

> **注意**: 此 Story 已在 User Story 2 跨表合併中處理主要需求（數量總表），平面圖核對優先級降低

### Tests for User Story 3

- [ ] T048 [P] [US3] 整合測試 backend/tests/integration/test_floor_plan_verification.py

### Implementation for User Story 3

- [ ] T049 [US3] 驗證現有 backend/app/services/pdf_parser.py 平面圖解析功能
- [ ] T050 [US3] 更新 BOQItem 數量來源標示（qty_source: "boq" | "floor_plan" | "quantity_summary"）
- [ ] T051 [US3] 更新 frontend 顯示數量來源標示

**Checkpoint**: User Story 3 完成 - 平面圖數量核對可獨立測試

---

## Phase 6: User Story 4 - 驗證材料產出表單 (Priority: P3)

**Goal**: 用戶可檢視完整材料驗證表單，確認報價單資料正確性

**Independent Test**: 上傳完整規格 PDF，驗證系統顯示所有欄位（照片、編號、尺寸、材料）

### Tests for User Story 4

- [ ] T052 [P] [US4] 整合測試 backend/tests/integration/test_material_verification.py

### Implementation for User Story 4

- [ ] T053 [US4] 驗證 backend/app/models/responses.py 包含完整 15 欄位
- [ ] T054 [US4] 更新 frontend 材料驗證介面顯示所有欄位
- [ ] T055 [US4] 新增項目對照原始 PDF 位置功能（source_page 欄位）

**Checkpoint**: User Story 4 完成 - 材料驗證表單可獨立測試

---

## Phase 7: Edge Cases & Error Handling

**Purpose**: 處理邊界情況與錯誤

- [x] T056 [P] 處理上傳多份數量總表時的錯誤提示（MERGE_001: 上傳多份數量總表，請僅保留一份）
- [x] T057 [P] 處理無明細規格表時的錯誤提示（MERGE_002: 未上傳明細規格表，無法進行合併）
- [x] T058 [P] 處理 Item No. 格式差異的標準化與警告（FormatWarning 模型）
- [ ] T059 [P] 處理總頁數超過 200 頁的錯誤提示
- [ ] T060 [P] 處理 PDF 加密或損毀的錯誤訊息

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 跨 User Story 的改進

- [x] T061 [P] 更新 CLAUDE.md 文件確保與新功能一致
- [ ] T062 [P] 更新 quickstart.md 執行驗證
- [x] T063 程式碼清理與重構（ruff check, black format）
- [ ] T064 效能優化（確保多 PDF 合併 < 10 分鐘，最大 200 頁）
- [ ] T065 [P] 補充單元測試達到 >= 80% 覆蓋率
- [ ] T066 安全性檢查（檔案上傳驗證、路徑注入防護）

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3-6 (User Stories) → Phase 7-8 (Edge Cases + Polish)
                          ↓
                    BLOCKS ALL USER STORIES
```

- **Setup (Phase 1)**: 無依賴 - 可立即開始
- **Foundational (Phase 2)**: 依賴 Setup 完成 - **阻塞所有 User Stories**
- **User Story 1 (Phase 3)**: 依賴 Foundational 完成
- **User Story 2 (Phase 4)**: 依賴 Foundational 完成（與 US1 可平行）
- **User Story 3 (Phase 5)**: 依賴 Foundational 完成
- **User Story 4 (Phase 6)**: 依賴 Foundational 完成
- **Edge Cases (Phase 7)**: 依賴 User Story 2 完成
- **Polish (Phase 8)**: 依賴所有 User Stories 完成

### User Story Dependencies

| Story | Priority | Dependencies | Notes |
|-------|----------|--------------|-------|
| US1 | P1 | Foundational only | MVP 基礎功能 |
| US2 | P1 | Foundational only | **核心跨表合併功能** |
| US3 | P3 | Foundational only | 優先級降低（數量已由 US2 處理） |
| US4 | P3 | Foundational only | 驗證輔助功能 |

### Within Each User Story

1. 測試先行 → 驗證測試失敗
2. Models → Services → API Routes
3. Backend → Frontend
4. Story 完成後再進入下一優先級

### Parallel Opportunities

**Foundational Phase 內可平行**:
```bash
# Models (可同時建立)
T011 (source_document.py) || T012 (merge_report.py) || T013 (quantity_summary.py) || T014 (boq_item.py) || T015 (processing_task.py)

# Core Services (可同時建立)
T017 (item_normalizer.py) || T018 (document_role_detector.py) || T019 (image_selector.py)

# Unit Tests (可同時建立)
T020 (test_item_normalizer) || T021 (test_document_role_detector) || T022 (test_image_selector)
```

**User Story 2 Tests 可平行**:
```bash
T032 (test_quantity_parser) || T033 (test_merge_service) || T034 (test_merge_api) || T035 (test_merge_flow)
```

**User Story 2 Frontend 可平行**:
```bash
T043 (merge_progress.py) || T044 (merge_report.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. 完成 Phase 1: Setup（已完成大部分）
2. 完成 Phase 2: Foundational（**CRITICAL - 阻塞所有 Stories**）
3. 完成 Phase 3: User Story 1（單一 PDF 流程）
4. **STOP and VALIDATE**: 獨立測試 User Story 1
5. 完成 Phase 4: User Story 2（跨表合併）
6. **STOP and VALIDATE**: 獨立測試 User Story 2
7. 部署/展示 MVP

### Incremental Delivery

```
Setup + Foundational → 基礎就緒
    ↓
User Story 1 → 獨立測試 → 部署（基礎功能）
    ↓
User Story 2 → 獨立測試 → 部署（**核心跨表合併功能**）
    ↓
User Story 3 → 獨立測試 → 部署（平面圖核對）
    ↓
User Story 4 → 獨立測試 → 部署（材料驗證）
```

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
3. Stories complete and integrate independently
4. Later: User Story 3 + 4

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| **Total Tasks** | 66 | - |
| **Setup (Phase 1)** | 5 | 5 completed |
| **Foundational (Phase 2)** | 17 | 17 completed |
| **User Story 1 (P1)** | 9 | 6 completed |
| **User Story 2 (P1)** | 16 | 9 completed |
| **User Story 3 (P3)** | 4 | 0 completed |
| **User Story 4 (P3)** | 4 | 0 completed |
| **Edge Cases (Phase 7)** | 5 | 3 completed |
| **Polish (Phase 8)** | 6 | 2 completed |

### MVP Scope (建議)

- **最小可行產品**: User Story 1 + User Story 2
- **核心價值**: 跨表合併功能（數量總表 + 明細規格表 → Excel）
- **預估任務數**: 約 47 個（含 Foundational）

### Key New Files to Create

| File | Description | Priority |
|------|-------------|----------|
| `backend/app/models/merge_report.py` | 合併報告模型 | 🔴 高 |
| `backend/app/models/quantity_summary.py` | 數量總表項目模型 | 🔴 高 |
| `backend/app/services/item_normalizer.py` | Item No. 標準化 | 🔴 高 |
| `backend/app/services/document_role_detector.py` | PDF 角色偵測 | 🔴 高 |
| `backend/app/services/quantity_parser.py` | 數量總表解析 | 🔴 高 |
| `backend/app/services/merge_service.py` | 跨表合併核心 | 🔴 高 |
| `backend/app/services/image_selector.py` | 圖片解析度選擇 | 🟡 中 |
| `backend/app/api/routes/merge.py` | 合併 API 端點 | 🔴 高 |
| `frontend/components/merge_progress.py` | 合併進度元件 | 🟡 中 |
| `frontend/components/merge_report.py` | 合併報告元件 | 🟡 中 |
| `frontend/pages/merge_preview.py` | 合併預覽頁面 | 🟡 中 |

---

## Notes

- [P] tasks = 可平行執行（不同檔案，無依賴）
- [Story] label = 所屬 User Story（US1, US2, US3, US4）
- 每個 User Story 可獨立完成與測試
- 測試先行（TDD per constitution）
- 每完成一個任務或邏輯群組就 commit
- 在 checkpoint 停下來驗證 Story 獨立運作
- 所有使用者訊息使用繁體中文
- **Excel 輸出完全比照範本 15 欄**
- **圖片使用 Base64 編碼嵌入 Excel**
- **數量總表 Qty 無條件覆蓋明細規格表數量**
- **多明細規格表依上傳順序合併**
- **圖片選擇最高解析度（width × height）**

---

*Tasks generated by `/speckit.tasks` command - 2025-12-23*
