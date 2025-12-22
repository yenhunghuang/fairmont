# 家具報價單系統 (Fairmont Furniture Quotation System)

這是一個專為家具報價流程設計的自動化系統，旨在簡化從 PDF 報價單提取資訊、匹配圖片並匯出至 Excel 的流程。

## 📌 專案概述

本專案是一個 POC (Proof of Concept) 實施，主要解決家具報價單處理中的手動操作痛點。系統能夠自動解析 PDF 文件，提取家具品項資訊，並透過確定性影像匹配技術 (Deterministic Image Matching) 準確關聯產品圖片。

## ✨ 核心功能

- **自動化流程**：從上傳、處理到下載的一站式自動化體驗。
- **PDF 解析**：高效提取 PDF 中的文字與結構化數據。
- **影像匹配**：採用確定性影像匹配技術，確保家具品項與圖片的準確對應。
- **Excel 匯出**：生成包含嵌入圖片的專業 Excel 報價單。
- **實時進度**：前端提供實時處理進度顯示與步驟指示。
- **響應式介面**：基於 Streamlit 構建的現代化、簡潔用戶介面。

## 🛠️ 技術棧

- **後端 (Backend)**: FastAPI (Python 3.10+)
- **前端 (Frontend)**: Streamlit
- **影像處理**: PyMuPDF (fitz), Pillow
- **Excel 處理**: openpyxl
- **AI 整合**: Google Gemini API (用於輔助解析)
- **容器化**: Docker & Docker Compose

## 📂 專案結構

```
Fairmont/
├── backend/            # FastAPI 後端服務
│   ├── app/            # 核心邏輯與 API
│   ├── tests/          # 後端測試
│   └── requirements.txt
├── frontend/           # Streamlit 前端應用
│   ├── app.py          # 單一入口點
│   └── requirements.txt
├── docs/               # 技術文件與研究報告
├── specs/              # 系統規格說明
├── docker-compose.yml  # 容器編排配置
└── Dockerfile.*        # Docker 構建文件
```

## 🚀 快速開始

### 使用 Docker (推薦)

1. 複製專案並進入目錄。
2. 建立 `.env` 檔案並設定 `GEMINI_API_KEY`。
3. 執行以下命令啟動系統：

```bash
docker-compose up --build
```

4. 訪問前端介面：`http://localhost:8501`
5. 訪問 API 文件：`http://localhost:8000/docs`

### 本地開發環境

#### 後端啟動：
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### 前端啟動：
```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## 📝 POC 實施進度

目前已完成第一階段 (Week 1) 的核心功能優化，包括：
- [x] 簡化前端導航與自動導向。
- [x] 實現實時進度顯示。
- [x] 強化錯誤處理機制。
- [x] 品牌視覺設計與樣式統一。

詳細資訊請參閱 [POC_IMPLEMENTATION_SUMMARY.md](POC_IMPLEMENTATION_SUMMARY.md)。

---
Developed by yenhunghuang
