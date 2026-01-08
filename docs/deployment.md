# Docker 部署指南

## 前置需求

- Docker Engine 20.10+
- Docker Compose 2.0+
- Gemini API Key

## 快速部署

### 1. 複製專案

```bash
git clone <repo-url>
cd Fairmont
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env，填入你的 GEMINI_API_KEY
nano .env
```

必填項目：
- `GEMINI_API_KEY`: Google Gemini API 金鑰
- `API_KEY`: API 認證金鑰（請自行設定）

### 3. 啟動服務

```bash
docker-compose up -d --build
```

### 4. 驗證服務

```bash
curl http://localhost:8000/api/v1/health
```

預期回應：
```json
{"status": "healthy", "message": "服務運行正常"}
```

---

## API 使用

| 項目 | 說明 |
|------|------|
| **Swagger UI** | http://\<server-ip\>:8000/docs |
| **API 端點** | `POST http://<server-ip>:8000/api/v1/process` |
| **認證方式** | Header `Authorization: Bearer <your-api-key>` |
| **Timeout** | 前端應設定 **360 秒（6 分鐘）以上** |

### 呼叫範例

```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Authorization: Bearer <your-api-key>" \
  -F "files=@sample.pdf"
```

---

## 常用指令

### 停止服務
```bash
docker-compose down
```

### 重新建置
```bash
docker-compose up -d --build
```

### 查看日誌
```bash
docker-compose logs -f backend
```

### 查看容器狀態
```bash
docker-compose ps
```

---

## 故障排除

### 容器無法啟動

1. 檢查日誌：
   ```bash
   docker-compose logs backend
   ```

2. 確認 `.env` 檔案中的 `GEMINI_API_KEY` 已正確設定

3. 確認 `skills/` 目錄存在且包含 yaml 配置

### API 回應 401 Unauthorized

確認請求 Header 包含正確的 API Key：
```
Authorization: Bearer <your-api-key>
```

### 處理時間過長

- 正常處理時間：1-6 分鐘（視 PDF 頁數）
- 前端 timeout 應設定 360 秒以上
- 檢查 Gemini API 配額是否足夠

---

## 環境變數說明

| 變數 | 必填 | 預設值 | 說明 |
|------|------|--------|------|
| `GEMINI_API_KEY` | ✅ | - | Google Gemini API 金鑰 |
| `GEMINI_MODEL` | ❌ | `gemini-3-flash-preview` | Gemini 模型 |
| `GEMINI_TIMEOUT_SECONDS` | ❌ | `600` | API 呼叫超時（秒）|
| `API_KEY` | ✅ | - | Bearer Token 認證金鑰 |
| `MAX_FILE_SIZE_MB` | ❌ | `50` | 單檔最大 MB |
| `MAX_FILES` | ❌ | `5` | 單次最多檔案數 |
