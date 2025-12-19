"""
長時間任務處理頁面

展示：
1. 建立長時間執行的任務
2. 即時進度追蹤
3. 結果顯示
"""

import streamlit as st
from utils.error_handler import display_success, display_error, display_info
from utils.api_client import APIError
import time


def show(api_client, session_state):
    """顯示長時間任務頁面"""

    st.title("⏳ 長時間任務處理")

    st.markdown("""
    建立需要較長處理時間的任務，系統會在背景執行並即時更新進度。
    """)

    # ==================== 建立任務表單 ====================

    with st.form("task_form"):
        st.subheader("建立新任務")

        # 輸入欄位
        task_data = st.text_area(
            "任務資料",
            value="測試資料",
            help="輸入要處理的資料",
            height=100
        )

        processing_time = st.slider(
            "處理時間（秒）",
            min_value=1,
            max_value=30,
            value=10,
            help="模擬任務處理需要的時間"
        )

        # 進度顯示選項
        col1, col2 = st.columns(2)
        with col1:
            show_live_progress = st.checkbox("即時顯示進度", value=True)
        with col2:
            show_details = st.checkbox("顯示詳細資訊", value=True)

        # 提交按鈕
        submit_button = st.form_submit_button(
            "建立任務",
            use_container_width=True,
            type="primary"
        )

    # ==================== 處理任務建立 ====================

    if submit_button:
        if not task_data.strip():
            st.warning("請輸入任務資料")
        else:
            try:
                # 建立任務
                with st.spinner("正在建立任務..."):
                    response = api_client.create_process_task(
                        data=task_data,
                        delay=processing_time
                    )

                    task_id = response['task_id']
                    session_state.set('current_task_id', task_id)

                display_success(f"任務已建立！任務 ID: {task_id}")

                # ==================== 追蹤進度 ====================

                if show_live_progress:
                    st.divider()
                    st.subheader("📊 處理進度")

                    # 建立進度顯示容器
                    progress_container = st.container()

                    with progress_container:
                        # 進度條
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        # 詳細資訊容器
                        if show_details:
                            metrics_container = st.container()
                            details_container = st.expander("任務詳情", expanded=False)

                        # 輪詢任務狀態
                        poll_interval = 0.5
                        max_wait = processing_time + 30  # 預期時間 + 緩衝時間
                        start_time = time.time()

                        while True:
                            # 檢查超時
                            elapsed = time.time() - start_time
                            if elapsed > max_wait:
                                display_error("任務處理超時")
                                break

                            # 取得任務狀態
                            try:
                                task_status = api_client.get_task_status(task_id)
                            except Exception as e:
                                display_error(f"無法取得任務狀態: {str(e)}")
                                break

                            # 解析狀態
                            progress = task_status.get('progress', 0)
                            status = task_status.get('status', 'unknown')
                            message = task_status.get('message', '')

                            # 更新進度條
                            progress_bar.progress(progress / 100)
                            status_text.text(f"🔄 {message}")

                            # 顯示詳細指標
                            if show_details:
                                with metrics_container:
                                    col1, col2, col3, col4 = st.columns(4)

                                    with col1:
                                        st.metric("進度", f"{progress}%")

                                    with col2:
                                        status_emoji = {
                                            'pending': '⏸️',
                                            'processing': '▶️',
                                            'completed': '✅',
                                            'failed': '❌'
                                        }.get(status, '❓')
                                        st.metric("狀態", f"{status_emoji} {status}")

                                    with col3:
                                        st.metric("已用時間", f"{int(elapsed)}秒")

                                    with col4:
                                        remaining = max(0, processing_time - int(elapsed))
                                        st.metric("預計剩餘", f"{remaining}秒")

                                # 顯示完整任務資訊
                                with details_container:
                                    st.json(task_status)

                            # 檢查是否完成
                            if status == 'completed':
                                progress_bar.progress(100)
                                status_text.empty()
                                display_success("✅ 任務處理完成！")

                                # 顯示結果
                                result = task_status.get('result', {})
                                if result:
                                    st.subheader("🎉 處理結果")

                                    # 格式化顯示結果
                                    col1, col2 = st.columns(2)

                                    with col1:
                                        st.info(f"**處理的資料**: {result.get('processed_data', 'N/A')}")
                                        st.info(f"**處理項目數**: {result.get('items_processed', 0)}")

                                    with col2:
                                        st.info(f"**完成時間**: {result.get('timestamp', 'N/A')[:19]}")

                                    # 完整結果（JSON 格式）
                                    with st.expander("完整結果（JSON）"):
                                        st.json(result)

                                # 儲存結果
                                session_state.set_task_result(task_id, result)
                                session_state.add_message(
                                    f"任務 {task_id[:8]}... 處理完成",
                                    'success'
                                )
                                break

                            elif status == 'failed':
                                status_text.empty()
                                error_msg = task_status.get('error', '未知錯誤')
                                display_error(f"❌ 任務執行失敗: {error_msg}")

                                # 顯示錯誤詳情
                                with st.expander("錯誤詳情"):
                                    st.json(task_status)

                                session_state.add_message(
                                    f"任務 {task_id[:8]}... 執行失敗: {error_msg}",
                                    'error'
                                )
                                break

                            # 等待後再次檢查
                            time.sleep(poll_interval)

                else:
                    # 不顯示即時進度，只提供任務 ID
                    display_info(f"任務已在背景執行，可至「任務管理」頁面查看進度")

            except APIError as e:
                display_error(f"任務建立失敗: {str(e)}")
            except Exception as e:
                display_error(f"發生未預期的錯誤: {str(e)}")

    # ==================== 最近的任務 ====================

    st.divider()
    st.subheader("📋 最近的任務")

    task_results = session_state.get('task_results', {})

    if task_results:
        # 顯示最近 5 個任務的結果
        recent_tasks = list(task_results.items())[-5:]

        for task_id, task_data in reversed(recent_tasks):
            result = task_data.get('result', {})
            completed_at = task_data.get('completed_at', 'N/A')

            with st.expander(f"✅ {task_id[:8]}... - {completed_at[:19]}"):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.json(result)

                with col2:
                    st.text(f"任務 ID:\n{task_id}")
                    st.text(f"完成時間:\n{completed_at[:19]}")

                    # 重新查詢按鈕
                    if st.button("重新查詢", key=f"refresh_{task_id[:8]}"):
                        try:
                            task_status = api_client.get_task_status(task_id)
                            st.json(task_status)
                        except Exception as e:
                            st.error(f"無法取得任務: {str(e)}")

        # 清除結果按鈕
        if st.button("清除所有結果", type="secondary"):
            session_state.set('task_results', {})
            st.rerun()

    else:
        st.info("尚無已完成的任務")

    # ==================== 使用說明 ====================

    with st.expander("📖 使用說明"):
        st.markdown("""
        ### 如何使用長時間任務功能

        1. **輸入資料**：在「任務資料」欄位輸入要處理的資料
        2. **設定處理時間**：使用滑桿選擇模擬的處理時間（1-30秒）
        3. **選擇顯示選項**：
           - 即時顯示進度：勾選後會即時更新進度
           - 顯示詳細資訊：勾選後會顯示更多任務資訊
        4. **建立任務**：點擊「建立任務」按鈕
        5. **等待處理**：系統會在背景處理並即時更新進度
        6. **查看結果**：處理完成後會顯示結果

        ### 技術說明

        - 任務在後端的背景執行（使用 FastAPI BackgroundTasks）
        - 前端使用輪詢（polling）方式定期檢查任務狀態
        - 進度資訊由後端即時更新
        - 所有任務結果會儲存在 Session State 中

        ### 實際應用場景

        - 大量資料處理
        - 檔案轉換
        - 報表生成
        - AI 模型推論
        - 批次作業
        """)
