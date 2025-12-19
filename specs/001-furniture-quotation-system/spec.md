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

### User Story 2 - 多檔案上傳與合併處理 (Priority: P2)

客戶需要統整多份標案資料，上傳多個PDF檔案，系統合併處理後產出單一惠而蒙格式的Excel報價單。

**Why this priority**: 實際業務場景中，客戶常需處理多份文件。此功能建立在P1的單檔處理能力之上，擴展系統實用性。

**Independent Test**: 可透過上傳2-3份不同的PDF檔案，驗證系統能正確合併資料並產出單一整合報價單。

**Acceptance Scenarios**:

1. **Given** 用戶已進入上傳介面, **When** 用戶選擇多個PDF檔案上傳, **Then** 系統接受所有檔案並顯示檔案清單
2. **Given** 多個PDF檔案已上傳, **When** 系統完成所有檔案解析, **Then** 系統合併所有BOQ資料並顯示統整後的材料表
3. **Given** 統整資料已完成, **When** 用戶下載Excel, **Then** 產出的xls檔案包含所有檔案的合併資料

---

### User Story 3 - BOQ數量與平面圖核對 (Priority: P2)

當BOQ中某些項目缺少數量資料時，系統從同時上傳的平面圖PDF中核對並補充數量資訊。

**Why this priority**: 此功能解決實際業務痛點，確保報價單數據完整性，與P2並列因為它增強資料準確度。

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

### Key Entities

- **BOQ項目 (BOQ Item)**: 代表一筆家具或物料資料，包含以下屬性：NO.（序號）、Item No.（項目編號）、Description（描述）、Photo（照片）、Dimension（尺寸 WxDxH mm）、Qty（數量）、UOM（單位）、Note（備註）、Location（位置）、Materials Used/Specs（材料/規格）
- **報價單 (Quotation)**: 由多個BOQ項目組成的輸出文件，遵循惠而蒙格式規範，必須包含10個標準欄位（排除價格/金額欄位）
- **來源文件 (Source Document)**: 用戶上傳的PDF檔案，可能是BOQ文件或平面圖
- **材料驗證記錄 (Material Verification)**: 包含項目對照資訊，記錄每筆資料的來源與驗證狀態

## Assumptions

- 「惠而蒙格式」依據實際範例檔案 `docs/RFQ FORM-FTQ25106_報價Excel Form.xlsx` 定義，系統將依據此格式規範產出文件
- BOQ PDF檔案中的表格結構為標準格式，可透過表格識別技術解析
- 平面圖中的家具數量標示遵循建築製圖慣例
- 用戶具備基本電腦操作能力，能夠上傳檔案並下載Excel
- 系統不需處理加密或密碼保護的PDF檔案

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用戶從上傳PDF到下載Excel報價單的完整流程可在5分鐘內完成（單一檔案）
- **SC-002**: 系統BOQ資料解析準確率達到90%以上（與人工識別對照）
- **SC-003**: 產出的Excel檔案100%符合惠而蒙格式規範
- **SC-004**: 用戶可同時上傳至少5個PDF檔案進行合併處理
- **SC-005**: 系統支援處理單一PDF檔案最大50MB
- **SC-006**: 90%的用戶能在首次使用時成功完成報價單生成流程
- **SC-007**: 平面圖數量核對功能準確率達到80%以上
