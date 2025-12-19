"""
檔案上傳頁面

展示：
1. 檔案上傳功能
2. 上傳進度顯示
3. 任務追蹤
"""

import streamlit as st
from utils.error_handler import (
    handle_errors,
    validate_file_size,
    validate_file_extension,
    display_success,
    display_error,
    FileError,
    APIError
)
from utils.api_client import APIError as ClientAPIError
import time


def show(api_client, session_state):
    """顯示檔案上傳頁面"""

    st.title("📤 檔案上傳")

    st.markdown("""
    上傳檔案到後端進行處理。支援的檔案格式：CSV、XLSX、TXT
    """)

    # ==================== 檔案上傳表單 ====================

    with st.form("upload_form", clear_on_submit=True):
        st.subheader("選擇要上傳的檔案")

        # 檔案上傳器
        uploaded_file = st.file_uploader(
            "選擇檔案",
            type=['csv', 'xlsx', 'txt', 'json'],
            help="支援的檔案格式：CSV, XLSX, TXT, JSON"
        )

        # 選項
        col1, col2 = st.columns(2)
        with col1:
            show_progress = st.checkbox("顯示詳細進度", value=True)
        with col2:
            auto_refresh = st.checkbox("自動重新整理結果", value=True)

        # 提交按鈕
        submit_button = st.form_submit_button(
            "上傳檔案",
            use_container_width=True,
            type="primary"
        )

    # ==================== 處理上傳 ====================

    if submit_button and uploaded_file is not None:
        try:
            # 驗證檔案
            validate_file_size(uploaded_file, max_size_mb=10)
            validate_file_extension(
                uploaded_file.name,
                allowed_extensions=['.csv', '.xlsx', '.txt', '.json']
            )

            # 顯示上傳中訊息
            with st.spinner(f"正在上傳 {uploaded_file.name}..."):
                # 上傳檔案
                response = api_client.upload_file(
                    uploaded_file.getvalue(),
                    uploaded_file.name
                )

                task_id = response['task_id']

                # 記錄到 session state
                session_state.add_uploaded_file(uploaded_file.name, task_id)
                session_state.set('current_task_id', task_id)

                display_success(f"檔案 '{uploaded_file.name}' 上傳成功！")
                st.info(f"任務 ID: {task_id}")

            # ==================== 追蹤進度 ====================

            if show_progress:
                st.subheader("處理進度")

                # 進度容器
                progress_bar = st.progress(0)
                status_text = st.empty()
                progress_details = st.empty()

                # 輪詢任務狀態
                max_wait = 60  # 最多等待 60 秒
                poll_interval = 0.5  # 每 0.5 秒檢查一次
                start_time = time.time()

                while True:
                    # 檢查超時
                    if time.time() - start_time > max_wait:
                        display_error("任務處理超時，請稍後在「任務管理」頁面查看結果")
                        break

                    # 取得任務狀態
                    try:
                        task_status = api_client.get_task_status(task_id)
                    except Exception as e:
                        display_error(f"無法取得任務狀態: {str(e)}")
                        break

                    # 更新進度
                    progress = task_status.get('progress', 0)
                    status = task_status.get('status', 'unknown')
                    message = task_status.get('message', '')

                    progress_bar.progress(progress / 100)
                    status_text.text(f"狀態: {message}")

                    # 顯示詳細資訊
                    with progress_details.container():
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("進度", f"{progress}%")
                        with col2:
                            st.metric("狀態", status)
                        with col3:
                            elapsed = int(time.time() - start_time)
                            st.metric("已用時間", f"{elapsed}秒")

                    # 檢查是否完成
                    if status == 'completed':
                        progress_bar.progress(100)
                        display_success("處理完成！")

                        # 顯示結果
                        result = task_status.get('result', {})
                        if result:
                            st.subheader("處理結果")
                            st.json(result)

                        # 儲存結果
                        session_state.set_task_result(task_id, result)
                        break

                    elif status == 'failed':
                        error_msg = task_status.get('error', '未知錯誤')
                        display_error(f"處理失敗: {error_msg}")
                        break

                    # 等待後再次檢查
                    time.sleep(poll_interval)

        except FileError as e:
            display_error(e.message)
            if e.details:
                with st.expander("錯誤詳情"):
                    st.json(e.details)

        except (ClientAPIError, APIError) as e:
            display_error(f"上傳失敗: {str(e)}")

        except Exception as e:
            display_error(f"發生未預期的錯誤: {str(e)}")

    elif submit_button:
        st.warning("請先選擇要上傳的檔案")

    # ==================== 已上傳檔案歷史 ====================

    st.divider()
    st.subheader("📋 上傳歷史")

    uploaded_files = session_state.get_uploaded_files()

    if uploaded_files:
        # 顯示檔案列表
        for idx, file_info in enumerate(reversed(uploaded_files[-10:])):  # 最多顯示 10 筆
            with st.expander(f"📄 {file_info['filename']} - {file_info['uploaded_at'][:19]}"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.text(f"任務 ID: {file_info['task_id']}")
                    st.text(f"上傳時間: {file_info['uploaded_at']}")

                with col2:
                    # 查看結果按鈕
                    if st.button("查看結果", key=f"view_{idx}"):
                        try:
                            task_status = api_client.get_task_status(file_info['task_id'])
                            st.json(task_status)
                        except Exception as e:
                            st.error(f"無法取得任務狀態: {str(e)}")

        # 清除歷史按鈕
        if st.button("清除歷史記錄", type="secondary"):
            session_state.clear_uploaded_files()
            st.rerun()

    else:
        st.info("尚未上傳任何檔案")

    # ==================== 使用說明 ====================

    with st.expander("📖 使用說明"):
        st.markdown("""
        ### 如何使用檔案上傳功能

        1. **選擇檔案**：點擊「Browse files」選擇要上傳的檔案
        2. **設定選項**：
           - 顯示詳細進度：勾選後會即時顯示處理進度
           - 自動重新整理結果：勾選後會自動更新處理結果
        3. **上傳檔案**：點擊「上傳檔案」按鈕
        4. **等待處理**：系統會自動處理檔案並顯示進度
        5. **查看結果**：處理完成後會顯示結果

        ### 注意事項

        - 檔案大小限制：10MB
        - 支援格式：CSV, XLSX, TXT, JSON
        - 處理時間取決於檔案大小和內容
        - 可在「任務管理」頁面查看所有任務狀態
        """)
