# Tasks: 家具報價單系統 (Furniture Quotation System)

**Input**: Design documents from `/specs/001-furniture-quotation-system/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/openapi.yaml

**Tests**: TDD approach required per constitution (測試優先開發). Tests are included in each user story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Updated**: 2025-12-19 - Excel 輸出格式更新為完全比照範本 15 欄，圖片使用 Base64 編碼

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/` for FastAPI, `frontend/` for Streamlit
- See plan.md for detailed project structure

## Key Changes from Previous Version

| 變更項目 | 舊版 | 新版 |
|----------|------|------|
| Excel 欄位數 | 10 欄 | 15 欄（完全比照範本） |
| 圖片儲存 | `photo_path` (檔案路徑) | `photo_base64` (Base64 編碼) |
| 新增欄位 | - | `unit_cbm`, `brand` |
| 移除欄位 | `source_type`, `qty_verified`, `qty_source` | *(保留於內部使用)* |
| 留空欄位 | - | H: Unit Rate, I: Amount |
| 公式欄位 | - | K: Total CBM (=F*J) |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create backend project structure per plan.md in backend/
- [x] T002 Create frontend project structure per plan.md in frontend/
- [x] T003 [P] Initialize backend Python project with pyproject.toml in backend/pyproject.toml
- [x] T004 [P] Create backend requirements.txt with FastAPI, google-generativeai, PyMuPDF, openpyxl, Pillow, pydantic in backend/requirements.txt
- [x] T005 [P] Create backend dev requirements with pytest, pytest-asyncio, pytest-cov, httpx, ruff, black in backend/requirements-dev.txt
- [x] T006 [P] Create frontend requirements.txt with streamlit, httpx, Pillow in frontend/requirements.txt
- [x] T007 [P] Configure ruff and black in backend/pyproject.toml
- [x] T008 [P] Create .env.example with GEMINI_API_KEY, BACKEND_HOST, BACKEND_PORT, FRONTEND_PORT, TEMP_DIR, MAX_FILE_SIZE_MB in .env.example
- [x] T009 [P] Create Docker configuration files: Dockerfile.backend, Dockerfile.frontend, docker-compose.yml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T010 Implement config module with Gemini API key and settings in backend/app/config.py
- [x] T011 [P] Implement error handling utilities with ErrorCode enum and raise_error function (繁體中文訊息) in backend/app/utils/errors.py
- [x] T012 [P] Implement file manager utility for temp file storage and cleanup in backend/app/utils/file_manager.py
- [x] T013 [P] Implement input validators for PDF files in backend/app/utils/validators.py
- [x] T014 **[UPDATED]** Update BOQItem Pydantic model per data-model.md (15 欄: 新增 unit_cbm, brand, 改用 photo_base64) in backend/app/models/boq_item.py
- [x] T015 [P] Create SourceDocument Pydantic model per data-model.md in backend/app/models/source_document.py
- [x] T016 [P] Create Quotation Pydantic model per data-model.md in backend/app/models/quotation.py
- [x] T017 [P] Create ProcessingTask Pydantic model per data-model.md in backend/app/models/processing_task.py
- [x] T018 [P] Create ExtractedImage Pydantic model per data-model.md in backend/app/models/extracted_image.py
- [x] T019 [P] Create API response models (APIResponse, ErrorResponse, PaginatedResponse) in backend/app/models/responses.py
- [x] T020 Create models __init__.py to export all models in backend/app/models/__init__.py
- [x] T021 Implement InMemoryStore class for documents, tasks, quotations, images storage in backend/app/store.py
- [x] T022 Implement FastAPI application with CORS, error handlers in backend/app/main.py
- [x] T023 Implement API dependencies (get_store, file validation) in backend/app/api/dependencies.py
- [x] T024 [P] Implement health check endpoint per openapi.yaml in backend/app/api/routes/health.py
- [x] T025 Register all routers in FastAPI app in backend/app/main.py
- [x] T026 Create utils __init__.py in backend/app/utils/__init__.py
- [x] T027 Create services __init__.py in backend/app/services/__init__.py
- [x] T028 Create api __init__.py in backend/app/api/__init__.py
- [x] T029 Create api/routes __init__.py in backend/app/api/routes/__init__.py
- [x] T030 Create app __init__.py in backend/app/__init__.py
- [x] T031 Create pytest conftest.py with fixtures for FastAPI test client, mock store in backend/tests/conftest.py
- [x] T032 Create tests __init__.py files in backend/tests/__init__.py, backend/tests/unit/__init__.py, backend/tests/integration/__init__.py, backend/tests/contract/__init__.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - 上傳 PDF 並生成報價單 (Priority: P1) 🎯 MVP

**Goal**: 客戶上傳 BOQ PDF 檔案，系統解析並產出惠而蒙格式 Excel 報價單（**15 欄，完全比照範本**）

**Independent Test**: 上傳單一 BOQ PDF 檔案，驗證是否產出正確格式的 Excel 檔（15 欄，圖片以 Base64 嵌入）

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T033 [P] [US1] Contract test for POST /api/upload endpoint in backend/tests/contract/test_upload_api.py
- [x] T034 [P] [US1] Contract test for POST /api/parse/{document_id} endpoint in backend/tests/contract/test_parse_api.py
- [x] T035 [P] [US1] Contract test for GET /api/parse/{document_id}/result endpoint in backend/tests/contract/test_parse_api.py
- [x] T036 [P] [US1] Contract test for POST /api/quotation endpoint in backend/tests/contract/test_export_api.py
- [x] T037 [P] [US1] Contract test for POST /api/export/{quotation_id}/excel endpoint in backend/tests/contract/test_export_api.py
- [x] T038 [P] [US1] Contract test for GET /api/export/{quotation_id}/download endpoint in backend/tests/contract/test_export_api.py
- [x] T039 [P] [US1] Contract test for GET /api/task/{task_id} endpoint in backend/tests/contract/test_task_api.py
- [x] T040 [P] [US1] Unit test for pdf_parser service (Gemini integration) in backend/tests/unit/test_pdf_parser.py
- [x] T041 [P] [US1] Unit test for image_extractor service (PyMuPDF, Base64 output) in backend/tests/unit/test_image_extractor.py
- [x] T042 [P] [US1] Unit test for excel_generator service (openpyxl, 15 columns, Base64 image embed) in backend/tests/unit/test_excel_generator.py
- [x] T043 [US1] Integration test for upload-parse-export flow in backend/tests/integration/test_upload_flow.py

### Implementation for User Story 1

- [x] T044 **[UPDATED]** [US1] Update PDF parser service to extract all 15 fields (including unit_cbm, brand) in backend/app/services/pdf_parser.py
- [x] T045 **[UPDATED]** [US1] Update image extractor service to output Base64 instead of file path in backend/app/services/image_extractor.py
- [x] T046 **[UPDATED]** [US1] Update Excel generator service to output 15 columns per template (embed Base64 photos, add formulas for Total CBM) in backend/app/services/excel_generator.py
- [x] T047 [US1] Implement upload route with file validation, BackgroundTasks per openapi.yaml in backend/app/api/routes/upload.py
- [x] T048 [US1] Implement parse route with start parsing and get result endpoints in backend/app/api/routes/parse.py
- [x] T049 [US1] Implement export route with create quotation, generate excel, download endpoints in backend/app/api/routes/export.py
- [x] T050 [US1] Implement task status route per openapi.yaml in backend/app/api/routes/task.py
- [x] T051 [US1] Implement image serving route for GET /api/images/{image_id} in backend/app/api/routes/upload.py
- [x] T052 [US1] Create Streamlit API client with upload_pdf, get_task_status, wait_for_completion methods in frontend/services/api_client.py
- [x] T053 [US1] Create frontend services __init__.py in frontend/services/__init__.py
- [x] T054 [US1] Implement file uploader component with progress display in frontend/components/file_uploader.py
- [x] T055 [US1] Implement progress display component with status messages in frontend/components/progress_display.py
- [x] T056 [US1] Implement material table component for preview in frontend/components/material_table.py
- [x] T057 [US1] Implement source reference component for PDF location display in frontend/components/source_reference.py
- [x] T058 [US1] Create frontend components __init__.py in frontend/components/__init__.py
- [x] T059 [US1] Implement upload page with file selection, processing, progress bar in frontend/pages/upload.py
- [x] T060 [US1] Implement preview page with material table, Excel download button in frontend/pages/preview.py
- [x] T061 [US1] Create frontend pages __init__.py in frontend/pages/__init__.py
- [x] T062 [US1] Implement Streamlit main app with navigation in frontend/app.py
- [x] T063 [US1] Add temp file cleanup background task on app startup in backend/app/main.py

**Checkpoint**: User Story 1 should be fully functional - single PDF upload, parse, preview, and Excel download (15 columns)

---

## Phase 4: User Story 2 - 多檔案上傳與合併處理 (Priority: P2)

**Goal**: 上傳多個 PDF 檔案，合併處理後產出單一 Excel 報價單（15 欄格式）

**Independent Test**: 上傳 2-3 份不同的 PDF 檔案，驗證系統能正確合併資料並產出單一整合報價單

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T064 [P] [US2] Contract test for multi-file upload in POST /api/upload in backend/tests/contract/test_upload_api.py
- [ ] T065 [P] [US2] Contract test for GET /api/documents listing in backend/tests/contract/test_upload_api.py
- [ ] T066 [P] [US2] Unit test for multi-document quotation creation in backend/tests/unit/test_quotation_merge.py
- [ ] T067 [US2] Integration test for multi-file upload, merge, export flow in backend/tests/integration/test_parse_export_flow.py

### Implementation for User Story 2

- [ ] T068 [US2] Update upload route to handle multiple files (max 5) per openapi.yaml in backend/app/api/routes/upload.py
- [ ] T069 [US2] Implement document listing endpoint GET /api/documents in backend/app/api/routes/upload.py
- [ ] T070 [US2] Implement document detail endpoint GET /api/documents/{document_id} in backend/app/api/routes/upload.py
- [ ] T071 [US2] Implement document delete endpoint DELETE /api/documents/{document_id} in backend/app/api/routes/upload.py
- [ ] T072 [US2] Update quotation creation to merge items from multiple documents in backend/app/api/routes/export.py
- [ ] T073 [US2] Implement duplicate item_no detection and conflict handling in backend/app/services/quotation_merger.py
- [ ] T074 [US2] Update file uploader component to support multiple file selection in frontend/components/file_uploader.py
- [ ] T075 [US2] Update upload page to display file list and batch processing in frontend/pages/upload.py
- [ ] T076 [US2] Update preview page to show merged results from multiple sources in frontend/pages/preview.py

**Checkpoint**: User Stories 1 AND 2 should both work - single and multi-file upload with merge

---

## Phase 5: User Story 3 - BOQ 數量與平面圖核對 (Priority: P2)

**Goal**: 從平面圖 PDF 核對並補充 BOQ 中缺失的數量資訊

**Independent Test**: 上傳一份 BOQ（部分項目無數量）與對應平面圖，驗證系統能識別並補充缺失數量

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T077 [P] [US3] Contract test for POST /api/floor-plan/analyze endpoint in backend/tests/contract/test_floor_plan_api.py
- [ ] T078 [P] [US3] Unit test for floor_plan_analyzer service with Gemini vision in backend/tests/unit/test_floor_plan_analyzer.py
- [ ] T079 [US3] Integration test for BOQ + floor plan verification flow in backend/tests/integration/test_floor_plan_flow.py

### Implementation for User Story 3

- [ ] T080 [US3] Implement floor plan analyzer service with Gemini vision (analyze_floor_plan) in backend/app/services/floor_plan_analyzer.py
- [ ] T081 [US3] Implement floor plan analyze route POST /api/floor-plan/analyze in backend/app/api/routes/parse.py
- [ ] T082 [US3] Add optional qty_verified and qty_source fields to BOQItem for internal tracking (not exported to Excel) in backend/app/models/boq_item.py
- [ ] T083 [US3] Update material table component to display qty source indicator (BOQ/平面圖) in frontend/components/material_table.py
- [ ] T084 [US3] Update upload page to support floor plan selection and verification trigger in frontend/pages/upload.py
- [ ] T085 [US3] Add verification status display showing which items were verified from floor plan in frontend/pages/preview.py

**Checkpoint**: User Stories 1, 2, AND 3 should all work - including floor plan quantity verification

---

## Phase 6: User Story 4 - 驗證材料產出表單 (Priority: P3)

**Goal**: 提供完整的材料驗證介面，包含照片、編號、尺寸、使用材料及詳細規格

**Independent Test**: 上傳包含完整規格的 PDF，驗證系統能正確提取並顯示所有 15 欄位資訊

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T086 [P] [US4] Contract test for GET /api/quotation/{quotation_id}/items endpoint in backend/tests/contract/test_export_api.py
- [ ] T087 [P] [US4] Contract test for PATCH /api/quotation/{quotation_id}/items endpoint in backend/tests/contract/test_export_api.py
- [ ] T088 [US4] Integration test for item editing and source reference in backend/tests/integration/test_verification_flow.py

### Implementation for User Story 4

- [ ] T089 [US4] Implement quotation items listing endpoint GET /api/quotation/{quotation_id}/items in backend/app/api/routes/export.py
- [ ] T090 [US4] Implement quotation items update endpoint PATCH /api/quotation/{quotation_id}/items in backend/app/api/routes/export.py
- [ ] T091 [US4] Implement verification page with full material details display (all 15 fields) in frontend/pages/verification.py
- [ ] T092 [US4] Update source reference component to show PDF page and location in frontend/components/source_reference.py
- [ ] T093 [US4] Add item editing capability in verification page in frontend/pages/verification.py
- [ ] T094 [US4] Update main app navigation to include verification page in frontend/app.py

**Checkpoint**: All 4 user stories should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T095 [P] Add edge case handling for invalid/corrupted PDF files in backend/app/services/pdf_parser.py
- [ ] T096 [P] Add edge case handling for encrypted/password-protected PDFs in backend/app/services/pdf_parser.py
- [ ] T097 [P] Add edge case handling for PDFs without BOQ data in backend/app/services/pdf_parser.py
- [ ] T098 [P] Implement file size validation (max 50MB per file, max 5 files) in backend/app/utils/validators.py
- [ ] T099 [P] Add rate limiting for Gemini API calls with exponential backoff in backend/app/services/pdf_parser.py
- [ ] T100 [P] Implement memory cache using cachetools for frequently accessed data in backend/app/store.py
- [ ] T101 [P] Add comprehensive logging throughout services in backend/app/services/
- [ ] T102 [P] Create E2E test for full flow using Playwright in frontend/tests/e2e/test_full_flow.py
- [ ] T103 [P] Create frontend tests __init__.py files in frontend/tests/__init__.py, frontend/tests/e2e/__init__.py
- [ ] T104 Run all tests and ensure coverage >= 80%
- [ ] T105 Run ruff and black to ensure code quality
- [ ] T106 Validate quickstart.md instructions by following them on clean environment
- [ ] T107 [P] Add README.md with project overview and setup instructions in README.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P2 → P3)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Builds on US1 upload/parse infrastructure but independently testable
- **User Story 3 (P2)**: Builds on US1 parse infrastructure but independently testable
- **User Story 4 (P3)**: Builds on US1 quotation infrastructure but independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation (per constitution TDD requirement)
- Models before services
- Services before endpoints
- Backend before frontend
- Core implementation before UI integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all contract tests for User Story 1 together:
Task: "Contract test for POST /api/upload endpoint in backend/tests/contract/test_upload_api.py"
Task: "Contract test for POST /api/parse/{document_id} endpoint in backend/tests/contract/test_parse_api.py"
Task: "Contract test for GET /api/parse/{document_id}/result endpoint in backend/tests/contract/test_parse_api.py"
Task: "Contract test for POST /api/quotation endpoint in backend/tests/contract/test_export_api.py"
# ... etc

# Launch all unit tests for User Story 1 together:
Task: "Unit test for pdf_parser service (Gemini integration) in backend/tests/unit/test_pdf_parser.py"
Task: "Unit test for image_extractor service (PyMuPDF, Base64 output) in backend/tests/unit/test_image_extractor.py"
Task: "Unit test for excel_generator service (openpyxl, 15 columns, Base64 image embed) in backend/tests/unit/test_excel_generator.py"
```

---

## Parallel Example: Foundational Phase

```bash
# Launch all model creation tasks together:
Task: "Update BOQItem Pydantic model (15 欄) in backend/app/models/boq_item.py"
Task: "Create SourceDocument Pydantic model in backend/app/models/source_document.py"
Task: "Create Quotation Pydantic model in backend/app/models/quotation.py"
Task: "Create ProcessingTask Pydantic model in backend/app/models/processing_task.py"
Task: "Create ExtractedImage Pydantic model in backend/app/models/extracted_image.py"
Task: "Create API response models in backend/app/models/responses.py"

# Launch all utility tasks together:
Task: "Implement error handling utilities in backend/app/utils/errors.py"
Task: "Implement file manager utility in backend/app/utils/file_manager.py"
Task: "Implement input validators in backend/app/utils/validators.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (**優先完成 T014, T044, T045, T046 以支援 15 欄格式**)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (P1 - MVP)
   - Developer B: User Story 2 (P2 - after US1 foundation ready)
   - Developer C: User Story 3 (P2 - after US1 foundation ready)
   - Developer D: User Story 4 (P3 - after US1 foundation ready)
3. Stories complete and integrate independently

---

## Priority Tasks for 15-Column Format Update

以下任務需要優先更新以支援新的 15 欄格式：

| 優先級 | Task ID | 說明 |
|--------|---------|------|
| 🔴 高 | T014 | 更新 BOQItem 模型（新增 unit_cbm, brand, photo_base64） |
| 🔴 高 | T044 | 更新 PDF 解析服務（提取所有 15 欄資料） |
| 🔴 高 | T045 | 更新圖片提取服務（輸出 Base64 而非檔案路徑） |
| 🔴 高 | T046 | 更新 Excel 產生器（15 欄、Base64 圖片嵌入、Total CBM 公式） |
| 🟡 中 | T040-T042 | 更新相關單元測試 |
| 🟡 中 | T056 | 更新材料表元件以顯示新欄位 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD per constitution)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All user-facing messages must be in 繁體中文
- **Excel 輸出必須完全比照範本 15 欄，不包含額外追蹤欄位**
- **圖片必須使用 Base64 編碼嵌入 Excel 儲存格**
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
