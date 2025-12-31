# 家具報價單系統 - 前端 API 文件

> **Base URL**: `http://localhost:8000/api/v1`
> **Swagger UI**: `http://localhost:8000/docs`

---

## 單一 API 端點

```http
POST /api/v1/process
Content-Type: multipart/form-data
```

### Request

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| files | File[] | 是 | PDF 檔案（最多 5 個，單檔 ≤ 50MB）|
| title | string | 否 | 報價單標題 |
| extract_images | boolean | 否 | 是否提取圖片（預設 true）|

### Response (200)

直接返回 Fairmont 15 欄 JSON 陣列（無外層包裝）：

```json
[
  {
    "no": 1,
    "item_no": "DLX-101",
    "description": "Custom Bed Bench",
    "photo": "iVBORw0KGgo...",
    "dimension": "1930 x 2130 x 290 H",
    "qty": 248.0,
    "uom": "ea",
    "unit_rate": null,
    "amount": null,
    "unit_cbm": 1.74,
    "total_cbm": null,
    "note": "Bed bases only",
    "location": "King DLX (A/B)",
    "materials_specs": "Vinyl: DLX-500 Taupe",
    "brand": "Fairmont"
  },
  {
    "no": 2,
    "item_no": "DLX-102",
    "description": "King Bed",
    "photo": "...",
    "dimension": "2130 x 1930 x 450 H",
    "qty": 120.0,
    "uom": "ea",
    "unit_rate": null,
    "amount": null,
    "unit_cbm": 2.15,
    "total_cbm": null,
    "note": null,
    "location": "King Suite",
    "materials_specs": "Fabric: COM Grade A",
    "brand": null
  }
]
```

### Response - 失敗 (4xx/5xx)

```json
{
  "success": false,
  "message": "錯誤訊息（繁體中文）",
  "error_code": "ERROR_CODE"
}
```

---

## 15 欄 JSON 欄位說明

| # | JSON 欄位 | Excel 欄位 | 類型 | 說明 |
|---|-----------|------------|------|------|
| 1 | no | A: NO. | int | 序號（系統自動產生）|
| 2 | item_no | B: Item no. | string | 項目編號 |
| 3 | description | C: Description | string | 品名描述 |
| 4 | photo | D: Photo | string \| null | 圖片 Base64 |
| 5 | dimension | E: Dimension | string \| null | 尺寸 WxDxH mm |
| 6 | qty | F: Qty | float \| null | 數量 |
| 7 | uom | G: UOM | string \| null | 單位 (ea/m/set) |
| 8 | unit_rate | H: Unit Rate | null | 單價（留空，使用者填寫）|
| 9 | amount | I: Amount | null | 金額（留空，使用者填寫）|
| 10 | unit_cbm | J: Unit CBM | float \| null | 單位材積 |
| 11 | total_cbm | K: Total CBM | null | 總材積（留空，前端公式 =qty×unit_cbm）|
| 12 | note | L: Note | string \| null | 備註 |
| 13 | location | M: Location | string \| null | 位置/區域 |
| 14 | materials_specs | N: Materials | string \| null | 材料規格 |
| 15 | brand | O: Brand | string \| null | 品牌 |

**固定留空欄位**（使用者或公式填寫）：
- `unit_rate` (H): 單價
- `amount` (I): 金額
- `total_cbm` (K): 總材積（公式 =qty × unit_cbm）

---

## 前端使用範例

```javascript
async function processPDFs(files) {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));

  const res = await fetch('/api/v1/process', {
    method: 'POST',
    body: formData
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.message);
  }

  // 直接返回 15 欄 JSON 陣列
  return await res.json();
}

// 使用
const items = await processPDFs([pdf1, pdf2]);
console.log(items);
// [
//   { no: 1, item_no: "DLX-101", description: "...", photo: "...", ... },
//   { no: 2, item_no: "DLX-102", ... }
// ]
```

---

## 跨表合併功能

系統會自動識別上傳的 PDF 類型並執行合併：

| PDF 類型 | 檔名關鍵字 | 處理方式 |
|----------|------------|----------|
| 明細規格表 | Casegoods, Seating, Lighting, Fabric, Leather, Vinyl | Gemini AI 解析 BOQ |
| 數量總表 | Qty, Overall, Summary, Quantity | 專用解析器提取數量 |

**合併邏輯**：
1. 解析所有明細規格表（提取品項資訊）
2. 解析數量總表（提取數量）
3. 跨表配對（Item No. 正規化比對）
4. 面料排序（面料項目跟隨對應家具）

---

## 注意事項

| 項目 | 說明 |
|------|------|
| **請求時間** | 約 1-6 分鐘（視 PDF 頁數） |
| **Timeout 建議** | 前端設定 **360 秒（6 分鐘）以上** |
| **Loading 提示** | 建議顯示「處理中」狀態 |

---

## 錯誤碼

| error_code | HTTP | 說明 |
|------------|------|------|
| FILE_SIZE_EXCEEDED | 400 | 檔案過大（>50MB） |
| FILE_TYPE_NOT_ALLOWED | 400 | 非 PDF 檔案 |
| FILE_COUNT_EXCEEDED | 400 | 檔案數量超過限制（>5） |
| PROCESSING_FAILED | 500 | 處理失敗 |

---

## 限制條件

| 項目 | 限制 |
|------|------|
| 單檔大小 | ≤ 50MB |
| 單次上傳數量 | ≤ 5 個檔案 |
| 單次 PDF 頁數 | ≤ 200 頁 |
| 處理時間 | 約 10-60 秒（視頁數） |
