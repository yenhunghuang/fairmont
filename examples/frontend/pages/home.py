"""
首頁
"""

import streamlit as st


def show(api_client, session_state):
    """顯示首頁"""

    st.title("🚀 Streamlit-FastAPI 整合範例")

    st.markdown("""
    ### 歡迎使用本範例應用程式！

    這個應用程式展示了 Streamlit 與 FastAPI 整合的最佳實踐，包含以下功能：

    #### 📚 功能概覽

    1. **檔案上傳**
       - 支援多種檔案格式
       - 即時上傳進度顯示
       - 背景任務處理

    2. **長時間任務處理**
       - 非同步任務執行
       - 即時進度追蹤
       - 結果自動更新

    3. **任務管理**
       - 查看所有任務狀態
       - 任務歷史記錄
       - 任務結果下載

    4. **Session State 管理**
       - 統一的狀態管理
       - 跨頁面資料共享
       - 持久化使用者設定

    5. **錯誤處理**
       - 繁體中文錯誤訊息
       - 友善的錯誤提示
       - 詳細的錯誤記錄

    #### 🎯 快速開始

    1. 確認後端服務正在運行（點擊側邊欄的「檢查連線」）
    2. 從左側選單選擇要使用的功能
    3. 按照頁面指示操作

    #### 🔧 技術架構

    - **前端**: Streamlit
    - **後端**: FastAPI
    - **通訊**: REST API (requests)
    - **狀態管理**: Session State
    - **錯誤處理**: 統一的例外處理機制
    """)

    st.divider()

    # 快速狀態檢查
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="已上傳檔案",
            value=len(session_state.get('uploaded_files', []))
        )

    with col2:
        st.metric(
            label="任務結果",
            value=len(session_state.get('task_results', {}))
        )

    with col3:
        # 檢查後端連線
        is_connected = api_client.health_check()
        st.metric(
            label="後端狀態",
            value="正常" if is_connected else "離線",
            delta="已連線" if is_connected else "未連線",
            delta_color="normal" if is_connected else "inverse"
        )

    st.divider()

    # 最近的訊息
    messages = session_state.get_messages()
    if messages:
        st.subheader("📋 最近的訊息")
        for msg in messages[-5:]:  # 只顯示最近 5 條
            msg_type = msg.get('type', 'info')
            msg_text = msg.get('text', '')

            if msg_type == 'error':
                st.error(msg_text)
            elif msg_type == 'warning':
                st.warning(msg_text)
            elif msg_type == 'success':
                st.success(msg_text)
            else:
                st.info(msg_text)
