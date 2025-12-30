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
| extract_images | boolean | 否 | 是否提取圖片（預設 true） |

### Response - 成功 (200)

```json
{
  "success": true,
  "message": "處理完成：50 個項目",
  "data": {
    "items": [
      {
        "id": "item-uuid-1",
        "no": 1,
        "item_no": "DLX-100",
        "description": "King Bed",
        "photo_base64": "data:image/png;base64,...",
        "dimension": "1930 x 2130 x 290 H",
        "qty": 239,
        "uom": "ea",
        "unit_cbm": 1.74,
        "note": "Bed bases only",
        "location": "King DLX",
        "materials_specs": "Vinyl: DLX-500 Taupe",
        "brand": "Fairmont",
        "source_document_id": "doc-uuid-1",
        "source_page": 1
      }
    ],
    "total_items": 50,
    "statistics": {
      "items_with_qty": 48,
      "items_with_photo": 45,
      "total_images": 50,
      "matched_images": 45,
      "match_rate": 0.9
    }
  },
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

### Response - 失敗 (4xx/5xx)

```json
{
  "success": false,
  "message": "處理失敗：PDF 格式不正確",
  "error_code": "PROCESSING_FAILED",
  "timestamp": "2025-01-15T10:30:00.000Z"
}
```

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

  const result = await res.json();

  if (!result.success) {
    throw new Error(result.message);
  }

  return result.data.items; // 15 欄 JSON 陣列
}

// 使用
const items = await processPDFs([pdf1, pdf2]);
console.log(items);
```

---

## 注意事項

| 項目 | 說明 |
|------|------|
| **請求時間** | 約 10-60 秒（視 PDF 頁數） |
| **Timeout 建議** | 前端設定 120 秒以上 |
| **Loading 提示** | 建議顯示「處理中」狀態 |

---

## 15 欄 JSON 欄位說明

| JSON 欄位 | Excel 欄位 | 類型 | 說明 |
|-----------|------------|------|------|
| id | - | string | 項目唯一識別碼 |
| no | A: NO. | int | 序號 |
| item_no | B: Item no. | string | 項目編號 |
| description | C: Description | string | 品名描述 |
| photo_base64 | D: Photo | string | 圖片 Base64 |
| dimension | E: Dimension | string | 尺寸 WxDxH mm |
| qty | F: Qty | float | 數量 |
| uom | G: UOM | string | 單位 (ea/m/set) |
| unit_cbm | J: Unit CBM | float | 單位材積 |
| note | L: Note | string | 備註 |
| location | M: Location | string | 位置/區域 |
| materials_specs | N: Materials | string | 材料規格 |
| brand | O: Brand | string | 品牌 |
| source_document_id | - | string | 來源文件 ID |
| source_page | - | int | 來源頁碼 |

**留空欄位**（用戶手動填寫）：
- H: Unit Rate（單價）
- I: Amount（金額）
- K: Total CBM（公式：qty × unit_cbm）

---

## 錯誤處理

| error_code | HTTP | 說明 |
|------------|------|------|
| FILE_SIZE_EXCEEDED | 400 | 檔案過大（>50MB） |
| FILE_TYPE_NOT_ALLOWED | 400 | 非 PDF 檔案 |
| PDF_PARSING_FAILED | 500 | PDF 解析失敗 |
| PROCESSING_FAILED | 500 | 處理失敗 |

---

## 限制條件

| 項目 | 限制 |
|------|------|
| 單檔大小 | ≤ 50MB |
| 單次上傳數量 | ≤ 5 個檔案 |
| 單次 PDF 頁數 | ≤ 200 頁 |
| 處理時間 | 約 10-60 秒（視頁數） |

---

## 支援的 PDF 類型

| 類型 | 檔名關鍵字 | 說明 |
|------|------------|------|
| 家具明細 | Casegoods, Seating, Lighting | 自動解析 BOQ |
| 面料明細 | Fabric, Leather, Vinyl | 自動解析 BOQ |
| 數量總表 | Qty, Overall, Summary | 合併時配對數量 |
