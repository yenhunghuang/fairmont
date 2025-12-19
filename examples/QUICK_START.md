# Streamlit-FastAPI 整合範例 - 快速開始

## 一分鐘快速啟動

### 步驟 1：安裝依賴套件

```bash
pip install -r requirements.txt
```

### 步驟 2：啟動後端（開啟第一個終端機）

```bash
# Windows
run_backend.bat

# 或手動啟動
cd backend
python -m uvicorn main:app --reload
```

後端服務會在 http://localhost:8000 啟動

### 步驟 3：啟動前端（開啟第二個終端機）

```bash
# Windows
run_frontend.bat

# 或手動啟動
cd frontend
streamlit run app.py
```

前端應用程式會在 http://localhost:8501 自動開啟

### 步驟 4：開始使用

1. 點擊側邊欄的「檢查連線」確認後端正常運行
2. 選擇功能頁面開始測試：
   - **檔案上傳**：測試檔案上傳與進度顯示
   - **長時間任務**：測試背景任務處理
   - **任務管理**：查看所有任務狀態

---

## 功能展示

### 1. 檔案上傳與進度追蹤

導航至「檔案上傳」頁面：
- 選擇一個檔案（支援 CSV, XLSX, TXT, JSON）
- 點擊「上傳檔案」
- 觀察即時進度更新
- 查看處理結果

### 2. 長時間任務處理

導航至「長時間任務」頁面：
- 輸入測試資料
- 設定處理時間（1-30 秒）
- 點擊「建立任務」
- 觀察進度條和狀態訊息即時更新

### 3. 任務管理

導航至「任務管理」頁面：
- 查看所有任務列表
- 使用篩選和排序功能
- 查看任務詳細資訊
- 刪除不需要的任務

### 4. 多頁面導航

使用左側邊欄在不同功能頁面間切換：
- Session State 會自動保存資料
- 已上傳的檔案記錄會跨頁面保留
- 任務結果可在不同頁面查看

---

## 技術亮點

### 後端（FastAPI）
- RESTful API 設計
- 背景任務處理（BackgroundTasks）
- 檔案上傳與儲存
- 任務狀態即時追蹤
- 統一的錯誤處理與繁體中文訊息

### 前端（Streamlit）
- 多頁面應用程式架構
- API 客戶端封裝（含重試機制）
- 即時進度顯示（輪詢更新）
- Session State 統一管理
- 繁體中文錯誤訊息與驗證

### 整合特性
- 檔案上傳與進度追蹤
- 長時間任務非同步處理
- 即時狀態更新（輪詢機制）
- 跨頁面資料共享
- 完整的錯誤處理

---

## 目錄結構

```
examples/
├── backend/                      # FastAPI 後端
│   ├── main.py                  # 主應用程式
│   └── .env.example             # 環境變數範例
│
├── frontend/                     # Streamlit 前端
│   ├── app.py                   # 主應用程式
│   ├── pages/                   # 頁面模組
│   │   ├── home.py              # 首頁
│   │   ├── file_upload.py       # 檔案上傳
│   │   ├── long_task.py         # 長時間任務
│   │   ├── task_management.py   # 任務管理
│   │   └── settings.py          # 設定
│   │
│   ├── utils/                   # 工具模組
│   │   ├── api_client.py        # API 客戶端
│   │   ├── session_state.py     # Session State 管理
│   │   └── error_handler.py     # 錯誤處理
│   │
│   └── .streamlit/config.toml   # Streamlit 設定
│
├── requirements.txt              # 依賴套件
├── run_backend.bat              # 啟動後端腳本
├── run_frontend.bat             # 啟動前端腳本
├── QUICK_START.md               # 本檔案
└── STREAMLIT_FASTAPI_GUIDE.md   # 完整指南
```

---

## 下一步

### 學習更多
查看 `STREAMLIT_FASTAPI_GUIDE.md` 了解：
- 核心功能詳細說明
- 最佳實踐建議
- 常見問題解決方案
- 進階應用範例

### 自訂開發
參考各個模組的程式碼：
- `backend/main.py` - FastAPI 後端 API 實作
- `frontend/utils/api_client.py` - API 呼叫封裝
- `frontend/utils/session_state.py` - 狀態管理
- `frontend/utils/error_handler.py` - 錯誤處理

### 整合到您的專案
1. 複製所需的模組到您的專案
2. 根據需求修改 API 端點
3. 自訂 UI 樣式和頁面內容
4. 添加您的業務邏輯

---

## 常見問題

**Q: 後端啟動失敗？**
- 確認 8000 埠號沒有被佔用
- 檢查是否已安裝 `fastapi` 和 `uvicorn`
- 查看終端機的錯誤訊息

**Q: 前端無法連接後端？**
- 確認後端服務正在運行
- 檢查 API URL 是否正確（預設：http://localhost:8000）
- 點擊側邊欄的「檢查連線」按鈕

**Q: 檔案上傳失敗？**
- 確認檔案大小未超過 10MB
- 檢查檔案格式是否支援（CSV, XLSX, TXT, JSON）
- 查看錯誤訊息

---

**需要協助？** 請查看完整指南 `STREAMLIT_FASTAPI_GUIDE.md`
