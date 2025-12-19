"""
設定頁面

展示：
1. 應用程式設定
2. Session State 管理
3. 設定的持久化
"""

import streamlit as st
from utils.error_handler import display_success, display_info


def show(api_client, session_state):
    """顯示設定頁面"""

    st.title("⚙️ 設定")

    st.markdown("""
    管理應用程式設定和 Session State。
    """)

    # ==================== API 設定 ====================

    st.subheader("🔌 API 設定")

    with st.form("api_settings"):
        current_url = session_state.get('api_base_url', 'http://localhost:8000')

        api_url = st.text_input(
            "後端 API URL",
            value=current_url,
            help="FastAPI 後端的基礎 URL"
        )

        timeout = st.number_input(
            "請求超時（秒）",
            min_value=5,
            max_value=300,
            value=30,
            help="API 請求的超時時間"
        )

        if st.form_submit_button("儲存 API 設定", type="primary"):
            session_state.set('api_base_url', api_url)
            session_state.set('api_timeout', timeout)
            display_success("API 設定已儲存（需要重新載入頁面才會生效）")

    st.divider()

    # ==================== 顯示設定 ====================

    st.subheader("🎨 顯示設定")

    with st.form("display_settings"):
        # 主題
        theme = st.selectbox(
            "主題",
            options=['light', 'dark', 'auto'],
            index=['light', 'dark', 'auto'].index(session_state.get('theme', 'light')),
            help="選擇應用程式主題"
        )

        # 語言
        language = st.selectbox(
            "語言",
            options=['zh-TW', 'zh-CN', 'en'],
            index=['zh-TW', 'zh-CN', 'en'].index(session_state.get('language', 'zh-TW')),
            help="選擇介面語言"
        )

        # 其他選項
        show_debug_info = st.checkbox(
            "顯示除錯資訊",
            value=session_state.get('show_debug_info', False)
        )

        if st.form_submit_button("儲存顯示設定", type="primary"):
            session_state.update(
                theme=theme,
                language=language,
                show_debug_info=show_debug_info
            )
            display_success("顯示設定已儲存")

    st.divider()

    # ==================== Session State 管理 ====================

    st.subheader("💾 Session State 管理")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📊 查看 Session State", use_container_width=True):
            st.session_state._show_state = True

        if st.button("🗑️ 清除上傳歷史", use_container_width=True):
            session_state.clear_uploaded_files()
            display_success("上傳歷史已清除")

    with col2:
        if st.button("🗑️ 清除任務結果", use_container_width=True):
            session_state.set('task_results', {})
            display_success("任務結果已清除")

        if st.button("🔄 重設所有設定", use_container_width=True, type="secondary"):
            session_state.reset_to_defaults()
            display_success("所有設定已重設為預設值")
            st.rerun()

    # 顯示 Session State
    if st.session_state.get('_show_state', False):
        st.subheader("目前的 Session State")

        # 取得所有 Session State（排除內部變數）
        state_data = session_state.get_all()

        # 格式化顯示
        for key, value in state_data.items():
            with st.expander(f"🔑 {key}"):
                st.json(value)

        if st.button("關閉 Session State 檢視"):
            st.session_state._show_state = False
            st.rerun()

    st.divider()

    # ==================== 訊息管理 ====================

    st.subheader("💬 訊息管理")

    messages = session_state.get_messages()

    col1, col2 = st.columns([3, 1])

    with col1:
        st.metric("訊息數量", len(messages))

    with col2:
        if st.button("清除訊息", use_container_width=True):
            session_state.clear_messages()
            display_success("訊息已清除")
            st.rerun()

    # 顯示訊息
    if messages:
        st.subheader("最近的訊息")

        # 訊息類型篩選
        msg_types = st.multiselect(
            "篩選訊息類型",
            options=['info', 'success', 'warning', 'error'],
            default=['info', 'success', 'warning', 'error']
        )

        filtered_messages = [m for m in messages if m.get('type') in msg_types]

        for msg in reversed(filtered_messages[-20:]):  # 最多顯示 20 條
            msg_type = msg.get('type', 'info')
            msg_text = msg.get('text', '')
            timestamp = msg.get('timestamp', '')

            # 根據類型顯示不同樣式
            if msg_type == 'error':
                st.error(f"[{timestamp[:19]}] {msg_text}")
            elif msg_type == 'warning':
                st.warning(f"[{timestamp[:19]}] {msg_text}")
            elif msg_type == 'success':
                st.success(f"[{timestamp[:19]}] {msg_text}")
            else:
                st.info(f"[{timestamp[:19]}] {msg_text}")

    st.divider()

    # ==================== 系統資訊 ====================

    st.subheader("ℹ️ 系統資訊")

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.markdown(f"""
        **Session 啟動時間**
        {session_state.get('session_start_time', 'N/A')[:19]}

        **最後活動時間**
        {session_state.get('last_activity_time', 'N/A')[:19]}

        **已上傳檔案數**
        {len(session_state.get('uploaded_files', []))}
        """)

    with info_col2:
        st.markdown(f"""
        **任務結果數**
        {len(session_state.get('task_results', {}))}

        **訊息數量**
        {len(messages)}

        **後端 URL**
        `{session_state.get('api_base_url', 'N/A')}`
        """)

    # 後端健康檢查
    st.divider()
    st.subheader("🏥 後端健康檢查")

    if st.button("執行健康檢查", type="primary", use_container_width=True):
        with st.spinner("檢查中..."):
            is_healthy = api_client.health_check()

        if is_healthy:
            display_success("後端服務正常運行")

            # 取得後端資訊
            try:
                response = api_client.session.get(f"{api_client.base_url}/")
                data = response.json()

                st.subheader("後端資訊")
                st.json(data)

            except Exception as e:
                st.warning(f"無法取得詳細資訊: {str(e)}")
        else:
            st.error("後端服務無法連線")
            display_info("請確認 FastAPI 伺服器是否正在運行")

    # ==================== 除錯資訊 ====================

    if session_state.get('show_debug_info', False):
        st.divider()
        st.subheader("🐛 除錯資訊")

        with st.expander("完整 Session State（包含內部變數）"):
            st.json(dict(st.session_state))

        with st.expander("Streamlit 版本資訊"):
            st.code(f"Streamlit version: {st.__version__}")

    # ==================== 使用說明 ====================

    with st.expander("📖 使用說明"):
        st.markdown("""
        ### 設定管理功能

        #### API 設定
        - **後端 API URL**：設定 FastAPI 後端的連線位址
        - **請求超時**：設定 API 請求的超時時間

        #### 顯示設定
        - **主題**：選擇淺色、深色或自動主題
        - **語言**：選擇介面語言（目前僅繁體中文完整支援）
        - **除錯資訊**：開啟後會顯示額外的除錯資訊

        #### Session State 管理
        - **查看 Session State**：檢視所有儲存的狀態資料
        - **清除上傳歷史**：刪除所有上傳檔案記錄
        - **清除任務結果**：刪除所有任務結果
        - **重設所有設定**：將所有設定恢復為預設值

        #### 訊息管理
        - 查看應用程式產生的所有訊息
        - 可依類型篩選訊息
        - 支援清除舊訊息

        #### 健康檢查
        - 測試與後端服務的連線
        - 查看後端服務資訊

        ### 注意事項
        - 某些設定變更需要重新載入頁面才會生效
        - 清除 Session State 會導致所有資料遺失
        - 重設設定會清除所有自訂配置
        """)
