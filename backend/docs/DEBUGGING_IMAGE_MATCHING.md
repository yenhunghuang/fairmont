# 圖片匹配故障排查指南

如果看到 `Matched 0/5 items with images`，請按以下步驟診斷。

---

## 📋 檢查清單

### 1️⃣ 是否找到候選圖片？

**查看日誌：**
```
Processing item 1/5: FUR-001 (page 1)
Searching pages [0, 1, 2] for FUR-001
  Page 0: 0 total, 0 unused
  Page 1: 8 total, 8 unused
  Page 2: 5 total, 5 unused
Found 13 candidate images for FUR-001
```

**分析：**
- ✅ `Found X candidate images` → 候選圖片已找到，繼續下一步
- ❌ `No candidate images found` → 搜尋範圍問題或無大圖片

**解決方案（如無候選）：**
```python
# 增大搜尋範圍（在 image_matcher.py）
IMAGE_SEARCH_RADIUS = 3  # 原: 2
```

---

### 2️⃣ Vision API 是否工作？

**查看日誌：**
```
Calling Vision API for item: FUR-001
Vision response for FUR-001: {"is_matching_product": true, "confidence": 0.92, ...}
Parsed result: {'is_matching_product': True, 'confidence': 0.92, 'reason': '...'}
```

**分析：**
- ✅ `Vision response` 包含 JSON → API 工作正常
- ❌ `Could not find JSON in Vision response` → 格式問題
- ❌ `Vision validation error` → API 錯誤

**常見錯誤信息及解決方案：**

| 錯誤信息 | 原因 | 解決 |
|---------|------|------|
| `Gemini Vision not available` | 未初始化 | 檢查 `GEMINI_API_KEY` |
| `Could not find JSON` | 返回格式錯誤 | 見下面的 JSON 問題 |
| `Failed to parse Vision JSON` | JSON 無效 | 檢查 Prompt 格式 |
| `Vision validation error` | API 超時/額度 | 檢查 Gemini 配額 |

---

### 3️⃣ JSON 響應格式

**期望格式：**
```json
{
  "is_matching_product": true,
  "confidence": 0.95,
  "reason": "圖片顯示會議桌"
}
```

**常見問題及修復：**

#### 問題 A：Gemini 返回額外文本
```
Gemini 說：
"分析了這張圖片... 以下是結果：
{
  "is_matching_product": true,
  ...
}
這個結果基於..."
```

**修復：** 已在 Prompt 中加入 `只返回這個格式，不要其他文本`

#### 問題 B：欄位名稱不對
```
錯誤返回：
{
  "is_product_sample": true,  ← 應該是 is_matching_product
  "confidence": 0.95,
  "reason": "..."
}
```

**修復：** 檢查 Prompt 中的欄位名稱是否一致

---

### 4️⃣ 置信度/匹配問題

**查看日誌：**
```
Image 5 (page 1): match=false, confidence=0.45, reason="不是家具"
Image 12 (page 1): match=true, confidence=0.92, reason="是會議桌"
Best match (verified) for FUR-001: image 12 (confidence=0.92)
```

**分析：**

- ✅ 有 `match=true` 且 `confidence >= 0.6` → 會被選中
- ⚠️ 所有圖片 `match=false` → 使用最高置信度的（fallback）
- ❌ 所有圖片 `confidence < 0.6` → 可能需要調整閾值

**調整置信度閾值：**

在 `parse.py` 中修改：
```python
image_to_item_map = await matcher.match_images_to_items(
    images_with_bytes,
    boq_items,
    validate_product_images=True,
    min_confidence=0.5  # 降低閾值（原: 0.6）
)
```

---

## 🔍 完整診斷流程

### 情況 1：找不到候選圖片

```
日誌：
No candidate images found for FUR-001 (search pages: [-1, 0, 1])
```

**檢查：**
1. BOQ 項目的 `source_page` 是否正確設定？
   ```python
   print(item.source_page)  # 應該是正數 (1, 2, 3...)
   ```

2. 圖片是否都被過濾掉了？
   ```python
   # 檢查是否有足夠的大圖片
   print(f"Large images: {len(large_images)}")  # 應該 > 0
   ```

3. 搜尋範圍是否足夠？
   ```python
   IMAGE_SEARCH_RADIUS = 2  # 改成 3 或 5 試試
   ```

---

### 情況 2：Vision 返回零置信度

```
日誌：
Image 5 (page 1): match=false, confidence=0.0, reason="無法判斷"
Image 12 (page 1): match=false, confidence=0.0, reason="無法判斷"
No matching images found for FUR-001 (threshold=0.6)
```

**可能原因：**
1. **圖片格式問題** - PNG 轉換失敗或損壞
2. **Prompt 語言問題** - Gemini 沒有正確理解繁體中文
3. **圖片質量** - 圖片太小或不清楚

**解決方案：**

```python
# 降低置信度閾值
min_confidence=0.3  # 從 0.6 降到 0.3

# 或者啟用 fallback 模式
# （自動選擇最高置信度，即使 < 0.6）
# 這已經在代碼中實現了
```

---

### 情況 3：JSON 解析失敗

```
日誌：
Could not find JSON in Vision response for FUR-001.
Response: 分析完成。根據評估標準...
```

**修復：**

Prompt 已經改進，但如果還是有問題：

```python
# 在 image_matcher.py 的 create_description_based_prompt 中修改
# 確保最後要求的格式明確

prompt = f"""...評估標準...

請ONLY返回以下JSON，不要任何其他文本：
{{{{
  "is_matching_product": true或false,
  "confidence": 0.0到1.0,
  "reason": "簡短說明"
}}}}"""
```

---

## 📊 效能診斷

### 檢查 Vision API 調用次數

```
日誌：
Matched 0/5 items with images (validated 10 images instead of 39)
```

**解析：**
- 預期驗證 ~10 張圖片（5 項目 × 2-3 候選）
- 如果超過 39 張，表示搜尋範圍或邏輯有問題

### 檢查耗時

```
2025-12-22 12:19:54 - Start
2025-12-22 12:21:08 - End
= ~74 秒
```

**分析：**
- ✅ 10-15 秒 → 正常（Vision 調用 10-15 次）
- ⚠️ 30-50 秒 → 可能驗證了太多圖片
- ❌ > 100 秒 → 可能驗證了所有 39 張

---

## 🛠️ 快速修復

### 快速方案 1：降低置信度

```python
# parse.py 第 140 行
min_confidence=0.5  # 改成 0.5 或 0.4
```

### 快速方案 2：擴大搜尋範圍

```python
# image_matcher.py 第 27 行
IMAGE_SEARCH_RADIUS = 3  # 改成 3 或更大
```

### 快速方案 3：禁用 Vision（暫時測試）

```python
# parse.py 第 139 行
validate_product_images=False  # 禁用以測試候選圖片是否被找到
```

---

## 📝 收集日誌進行除錯

設置日誌級別為 DEBUG：

```python
# main.py 或 config.py
import logging
logging.getLogger("app.services.image_matcher").setLevel(logging.DEBUG)
```

然後運行 PDF 解析，收集完整日誌：

```bash
python -m app.main 2>&1 | tee debug.log
```

分享日誌中的：
1. `Processing item` 行
2. `Vision response` 行
3. `Best match` 或 `No matching images` 行

---

## 🎯 預期輸出（成功情況）

```
INFO - Found 39 large images for 5 items (description-based matching)
INFO - Processing item 1/5: FUR-001 (page 1)
DEBUG - Found 13 candidate images for FUR-001
DEBUG - Validating 13 candidates for FUR-001 (description: 會議桌)
DEBUG - Image 5 (page 1): match=true, confidence=0.95, reason="是會議桌"
INFO - Best match (verified) for FUR-001: image 5 (confidence=0.95)
...
INFO - Matched 5/5 items with images (validated 10 images instead of 39)
```

---

## 📞 仍需幫助？

查看完整日誌中：
1. `Vision response for [ITEM]` - Gemini 的完整響應
2. `Extracted JSON` - 提取出的 JSON 字符串
3. `Parsed result` - 解析后的字典

提供這些日誌片段可以快速診斷問題。
