# ADR-0001: Skills 架構與 agentskills.io 標準對齊

## 狀態

已決定 (2025-01-15)

## 背景

專案使用 `skills/` 目錄存放配置化的供應商規則、輸出格式與合併邏輯。研究 [agentskills.io](https://agentskills.io) 開放標準後，評估是否需要對齊該標準。

### agentskills.io 核心要求

| 項目 | 要求 |
|------|------|
| SKILL.md | **必要**，作為 Agent 發現入口 |
| name | 小寫+連字號，≤64 字元 |
| description | **必要**，說明功能與使用時機 |
| version | 選用，放在 metadata 區塊 |
| license | 選用 |

### 專案現況

- `SkillLoaderService` 直接硬編碼載入 `habitus`
- 沒有動態發現機制（不是 Agent 架構）
- 已有 `_vendor.yaml` 作為元資料載入入口

## 決策

### 不新增 SKILL.md

**原因**：專案目前不是 Agent 架構，沒有任何機制會讀取 SKILL.md 做技能發現。新增只會增加維護成本而無實際效益。

### 保留 description 與 license 欄位

**原因**：
1. 作為人類可讀的文件說明
2. 未來如果轉為 Agent 架構，已備妥必要元資料

**已完成的改動**：

```yaml
# skills/vendors/habitus/_vendor.yaml
vendor:
  description: |
    解析 HABITUS Design Group 的 FF&E 規格書 PDF，提取家具、面料、數量資訊。
    用於處理 HABITUS 格式的 Casegoods/Seating/Lighting/Fabric 規格文件。
  license: "Proprietary"

# skills/output-formats/fairmont.yaml
format:
  description: |
    惠而蒙報價單 Excel 格式定義，15 欄標準輸出。
    用於產出惠而蒙格式的家具報價單 Excel 檔案。
  license: "Proprietary"
```

## 現有架構優勢（保留）

以下設計已優於 agentskills.io 標準：

1. **版本依賴聲明** — `requires: { merge_rules: ">=1.1.0" }`
2. **JSON Schema 驗證** — `skills/schemas/*.schema.json`
3. **四層揭露層級** — `_disclosure_level: 1-4`
4. **Prompt 安全防護** — 防禦 Prompt Injection

## 後果

- POC 階段維持現有架構，不做大幅調整
- 未來如需支援多供應商動態選擇，可參考 agentskills.io 標準新增發現機制
- description 欄位可作為未來 Agent 整合的準備

## 參考

- [agentskills.io 規格](https://agentskills.io/specification)
- [GitHub: agentskills/agentskills](https://github.com/agentskills/agentskills)
