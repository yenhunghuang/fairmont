# Feature Specification: 家具報價單系統 (Furniture Quotation System)

**Feature Branch**: `001-furniture-quotation-system`
**Created**: 2025-12-19
**Status**: Clarified
**Input**: 提供客戶簡單、可視化的報價單系統，客戶上傳PDF文件，自動生成報價單，支援BOQ解析與惠而蒙格式Excel輸出

## Clarifications

### Session 2025-12-19

- Q: 系統是否需要用戶登入認證？ → A: 不需登入，公開使用
- Q: 惠而蒙格式Excel報價單需要包含哪些必要欄位？ → A: NO., Item No., Description, Photo, Dimension, Qty, UOM, Note, Location, Materials Used/Specs（共10欄，排除價格/金額欄位）
- Q: Excel報價單中的Photo欄位應如何呈現？ → A: 從PDF提取圖片，嵌入Excel儲存格

### Session 2025-12-23

- Q: 多 PDF 上傳時如何區分「數量總表」與「明細規格表」？
  → A: 根據檔名自動偵測，檔名含 "Qty"、"Overall"、"Summary"、"數量" 視為數量總表
- Q: 數量總表與明細規格表的數量欄位衝突時如何處理？
  → A: 數量總表的 Qty 完全覆蓋明細規格表的數量
- Q: 多份明細規格表有相同 Item No. 時如何處理？
  → A: 合併欄位，不同欄位取不同來源（如 Casegoods 取尺寸，Fabric 取材料規格）
- Q: 多明細規格表合併時，「第一個出現」的判定依據？
  → A: 依上傳順序（先上傳的 PDF 優先）
- Q: 多 PDF 同時包含相同 Item No. 的圖片時如何處理？
  → A: 選擇解析度較高的圖片
- Q: 預期單次處理的最大 PDF 總頁數？
  → A: 200 頁
- Q: 多 PDF 跨表合併的最大處理時間目標？
  → A: 10 分鐘
- Q: 明確排除的功能範圍（Out of Scope）？
  → A: Google Sheets 功能先不實作

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 上傳PDF並生成報價單 (Priority: P1)

客戶上傳包含BOQ（Bill of Quantities）的PDF檔案，系統自動解析活動家具及物料資料，生成惠而蒙格式的Excel報價單供下載。

**Why this priority**: 這是系統的核心價值主張。沒有PDF解析和報價單生成功能，系統無法提供任何實際價值。

**Independent Test**: 可透過上傳單一BOQ PDF檔案並驗證是否產出正確格式的Excel檔來完成測試，驗證系統能正確解析家具資料並輸出報價單。

**Acceptance Scenarios**:

1. **Given** 用戶已進入系統首頁, **When** 用戶上傳一份包含BOQ資料的PDF檔案, **Then** 系統顯示解析進度，完成後顯示解析結果預覽
2. **Given** 系統已成功解析PDF中的BOQ資料, **When** 用戶點擊「下載Excel」按鈕, **Then** 系統產出惠而蒙格式的xls檔案供用戶下載
3. **Given** 系統已解析BOQ資料, **When** 解析完成, **Then** 系統顯示材料表，包含編號、品項名稱、數量等資訊，並標示對照原始資料位置

---

### User Story 2 - 多檔案上傳與跨表合併 (Priority: P1)

客戶上傳「數量總表」PDF（包含所有項目的總數量）與多份「明細規格表」PDF（包含項目詳細規格、圖片、尺寸等），系統根據檔名自動識別 PDF 角色，以 Item No. 為匹配鍵，將數量總表的 Qty 合併至明細規格表的項目，產出單一惠而蒙格式 Excel。

**Why this priority**: 此為客戶實際工作流程的核心需求。數量總表提供正確的總量，明細規格表提供完整的項目資訊，兩者必須正確合併才能產出準確報價單。

**Independent Test**: 上傳 `Bay Tower Furniture - Overall Qty.pdf`（數量總表）與 `Casegoods & Seatings.pdf`、`Fabric & Leather.pdf`（明細規格表），驗證輸出 Excel 的 Qty 欄位數值來自數量總表，其他欄位來自明細規格表。

**Acceptance Scenarios**:

1. **Given** 用戶上傳多個 PDF 檔案（含 1 份檔名包含 "Qty" 的數量總表）,
   **When** 系統完成檔案接收,
   **Then** 系統自動識別並標示各檔案角色（數量總表/明細規格表）

2. **Given** 數量總表包含項目 "DLX-100" 數量為 239,
   **When** 明細規格表 `Casegoods & Seatings.pdf` 也包含 "DLX-100",
   **Then** 合併後該項目的 Qty 欄位為 239（來自數量總表），其他欄位（Description、Dimension、Photo）來自明細規格表

3. **Given** `Casegoods & Seatings.pdf` 包含 "DLX-100" 的尺寸規格,
   **When** `Fabric & Leather.pdf` 包含 "DLX-500" 的材料規格,
   **Then** 兩者均正確匹配至對應項目，不同欄位從不同來源合併

4. **Given** 明細規格表有項目 "DLX-999" 但數量總表無對應,
   **When** 系統完成合併,
   **Then** 該項目 Qty 欄位保留明細規格表原值並標示「數量未驗證」

5. **Given** 數量總表有項目 "DLX-888" 但明細規格表無對應,
   **When** 系統完成合併,
   **Then** 系統在匹配報告中列出「未找到明細的項目」清單

---

### User Story 3 - BOQ數量與平面圖核對 (Priority: P3)

當BOQ中某些項目缺少數量資料時，系統從同時上傳的平面圖PDF中核對並補充數量資訊。

**Why this priority**: 此功能解決實際業務痛點，確保報價單數據完整性。因 User Story 2 已處理數量總表合併，平面圖核對優先級降低。

**Independent Test**: 可透過上傳一份BOQ（部分項目無數量）與對應平面圖，驗證系統能從平面圖中識別並補充缺失數量。

**Acceptance Scenarios**:

1. **Given** 用戶上傳BOQ PDF（部分項目數量為空）, **When** 用戶同時上傳對應的平面圖PDF, **Then** 系統標示哪些項目需要從平面圖核對
2. **Given** 系統已識別需核對的項目, **When** 系統分析平面圖, **Then** 系統嘗試從平面圖中提取對應數量並填入
3. **Given** 平面圖核對完成, **When** 用戶檢視結果, **Then** 系統明確標示哪些數量來自BOQ原始資料，哪些是從平面圖補充

---

### User Story 4 - 驗證材料產出表單 (Priority: P3)

用戶可檢視完整的材料驗證表單，包含照片、編號、尺寸、使用材料及詳細規格（DESCRIPTION欄位），確認報價單資料正確性。

**Why this priority**: 此為資料驗證功能，在核心解析功能完成後提供額外的資料確認能力。

**Independent Test**: 可透過上傳包含完整規格的PDF，驗證系統能正確提取並顯示所有欄位資訊。

**Acceptance Scenarios**:

1. **Given** 系統已解析PDF資料, **When** 用戶進入驗證介面, **Then** 系統顯示材料表包含：照片、編號、尺寸、使用材料欄位
2. **Given** 驗證表單已顯示, **When** 用戶檢視任一項目, **Then** 該項目的DESCRIPTION欄位顯示詳細規格資訊
3. **Given** 驗證表單中有家具項目, **When** 用戶點擊該項目, **Then** 系統顯示該項目對照至原始PDF的位置

---

### Edge Cases

- BOQ PDF格式異常或無法解析時，系統應顯示明確錯誤訊息並指出問題位置
- 上傳的PDF不包含BOQ資料時，系統應提示用戶確認檔案內容
- 平面圖中無法識別對應數量時，系統保留該項目為空並標示「無法自動核對」
- 上傳檔案超過系統限制時，系統應提示檔案大小或數量限制
- 多個PDF中出現重複編號的項目時，系統應合併或提示用戶處理衝突
- 上傳檔案中無數量總表時，系統應提示用戶確認是否繼續（僅使用明細規格表數量）
- 上傳多份數量總表時，系統應報錯並要求用戶選擇唯一一份
- Item No. 格式差異（如 "DLX-100" vs "DLX 100" vs "DLX100"）時，系統應嘗試標準化匹配
- 數量總表的 Item No. 包含子項目編號（如 "DLX-100.1"）時，應獨立匹配不合併至父項目
- 明細規格表的同一 Item No. 在不同頁面重複出現時，應合併為單一項目

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統MUST支援PDF檔案上傳，接受標準PDF格式（PDF 1.4及以上）
- **FR-002**: 系統MUST能解析PDF中的BOQ（Bill of Quantities）表格資料
- **FR-003**: 系統MUST識別並提取「活動家具及物料」相關資料
- **FR-004**: 系統MUST產出惠而蒙格式的xls/xlsx Excel檔案
- **FR-005**: 系統MUST支援多檔案同時上傳（至少支援5個檔案）
- **FR-006**: 系統MUST合併多檔案的BOQ資料成單一輸出
- **FR-007**: 系統MUST顯示材料表，包含以下10個欄位：NO.（序號）、Item No.（項目編號）、Description（描述）、Photo（照片）、Dimension（尺寸 WxDxH mm）、Qty（數量）、UOM（單位）、Note（備註）、Location（位置）、Materials Used/Specs（材料/規格）。注意：排除價格/金額相關欄位（Unit Rate, Amount, CBM），這些由用戶手動填寫
- **FR-008**: 系統MUST在Description欄位顯示品名描述，在Materials Used/Specs欄位顯示詳細材料規格
- **FR-009**: 系統MUST標示每筆資料對照至原始PDF的來源位置
- **FR-010**: 系統MUST在BOQ數量欄位為空時，嘗試從平面圖核對數量
- **FR-011**: 系統MUST明確區分資料來源（BOQ原始資料 vs 平面圖補充）
- **FR-012**: 系統MUST提供資料預覽功能，讓用戶在下載前確認內容
- **FR-013**: 系統MUST採用前後端分離架構
- **FR-014**: 前端MUST提供可視化操作介面供用戶互動
- **FR-015**: 後端MUST處理PDF檔案上傳與自動化資料處理
- **FR-016**: 系統MUST允許匿名使用，無需用戶登入或認證
- **FR-017**: 系統MUST從PDF中提取家具/物料相關圖片，並嵌入至Excel報價單的Photo欄位儲存格中

#### 跨表合併功能需求（User Story 2）

- **FR-018**: 系統MUST根據檔名自動識別PDF角色：
  - 檔名含 "Qty"、"Overall"、"Summary"、"數量"、"總量" → `quantity_summary`（數量總表）
  - 其他 → `detail_spec`（明細規格表）
- **FR-019**: 系統MUST支援手動覆寫自動識別的PDF角色
- **FR-020**: 系統MUST以 Item No.（標準化後）為主鍵匹配跨PDF項目
- **FR-021**: 系統MUST執行 Item No. 標準化處理（移除空格、統一大小寫、統一標點符號如 "-" 和 "."）
- **FR-022**: 數量總表的 Qty 值MUST覆蓋明細規格表的數量（優先級最高）
- **FR-023**: 多份明細規格表有相同 Item No. 時，系統MUST合併非空欄位：
  - 非空欄位以上傳順序優先（先上傳的 PDF 優先）
  - 若某欄位在 A 表為空、B 表有值，則取 B 表值
- **FR-024**: 系統MUST產出匹配報告，包含：
  - 成功匹配項目數
  - 僅在數量總表的項目（無明細）
  - 僅在明細規格表的項目（數量未驗證）
  - Item No. 格式差異警告
- **FR-025**: 系統SHOULD在無數量總表時仍可處理（僅合併明細規格表）
- **FR-026**: 多份明細規格表包含相同 Item No. 的圖片時，系統MUST選擇解析度較高的圖片（以像素總數 width × height 判定）

### Key Entities

- **BOQ項目 (BOQ Item)**: 代表一筆家具或物料資料，包含以下屬性：NO.（序號）、Item No.（項目編號）、Description（描述）、Photo（照片）、Dimension（尺寸 WxDxH mm）、Qty（數量）、UOM（單位）、Note（備註）、Location（位置）、Materials Used/Specs（材料/規格）
- **報價單 (Quotation)**: 由多個BOQ項目組成的輸出文件，遵循惠而蒙格式規範，必須包含10個標準欄位（排除價格/金額欄位）
- **來源文件 (Source Document)**: 用戶上傳的PDF檔案，新增 `document_role` 屬性：
  - `quantity_summary`: 數量總表，僅包含 Item No. 與 Qty
  - `detail_spec`: 明細規格表，包含完整欄位資訊
  - `floor_plan`: 平面圖（用於數量核對）
  - `unknown`: 無法自動識別，需用戶確認
- **數量總表 (Quantity Summary)**: 包含所有項目的總數量對照表（如 `Bay Tower Furniture - Overall Qty.pdf`），主要欄位：CODE（對應 Item No.）、TOTAL QTY（對應 Qty）
- **明細規格表 (Detail Specification)**: 包含項目完整規格資訊（如 `Casegoods & Seatings.pdf`、`Fabric & Leather.pdf`），欄位：Item No.、Description、Photo、Dimension、UOM、Note、Location、Materials/Specs、Brand 等
- **匹配報告 (Merge Report)**: 跨PDF合併的結果摘要，包含：成功匹配項目數、僅在數量總表的項目、僅在明細規格表的項目、格式差異警告
- **材料驗證記錄 (Material Verification)**: 包含項目對照資訊，記錄每筆資料的來源與驗證狀態

## Assumptions

- 「惠而蒙格式」依據實際範例檔案 `docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx` 定義，系統將依據此格式規範產出文件
- BOQ PDF檔案中的表格結構為標準格式，可透過表格識別技術解析
- 平面圖中的家具數量標示遵循建築製圖慣例
- 用戶具備基本電腦操作能力，能夠上傳檔案並下載Excel
- 系統不需處理加密或密碼保護的PDF檔案
- 數量總表的 Item No. 編碼規則與明細規格表一致，可透過標準化後進行匹配
- 每次上傳最多包含一份數量總表，多份明細規格表
- 單次處理的 PDF 總頁數上限為 200 頁（超過時系統應提示用戶分批處理）

## Out of Scope

本階段明確不實作的功能：

- **Google Sheets 匯出功能**: 暫不支援匯出至 Google Sheets，僅提供 Excel 下載
- **用戶編輯 BOQ 項目**: 用戶無法在系統內修改解析結果，需透過 Excel 編輯
- **歷史記錄與版本管理**: 不保留用戶上傳與處理歷史
- **多語系支援**: 介面與錯誤訊息僅支援繁體中文

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用戶從上傳PDF到下載Excel報價單的完整流程可在5分鐘內完成（單一檔案）
- **SC-002**: 系統BOQ資料解析準確率達到90%以上（與人工識別對照）
- **SC-003**: 產出的Excel檔案100%符合惠而蒙格式規範
- **SC-004**: 用戶可同時上傳至少5個PDF檔案進行合併處理
- **SC-005**: 系統支援處理單一PDF檔案最大50MB
- **SC-006**: 90%的用戶能在首次使用時成功完成報價單生成流程
- **SC-007**: 平面圖數量核對功能準確率達到80%以上
- **SC-008**: Item No. 跨PDF匹配成功率達95%以上（標準化後）
- **SC-009**: 數量總表 Qty 正確覆蓋率達100%（匹配成功的項目）
- **SC-010**: 多明細規格表欄位合併正確率達90%以上
- **SC-011**: 多 PDF 跨表合併的完整流程（上傳至下載）可在 10 分鐘內完成（最大 200 頁）
