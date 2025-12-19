"""
任務管理頁面

展示：
1. 查看所有任務
2. 任務狀態監控
3. 任務操作（刪除等）
"""

import streamlit as st
from utils.error_handler import display_success, display_error, display_info
from utils.api_client import APIError
import time


def show(api_client, session_state):
    """顯示任務管理頁面"""

    st.title("📊 任務管理")

    st.markdown("""
    查看和管理所有任務的狀態、進度和結果。
    """)

    # ==================== 控制列 ====================

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        auto_refresh = st.checkbox("自動重新整理", value=False)
        if auto_refresh:
            refresh_interval = st.slider("重新整理間隔（秒）", 1, 10, 3)

    with col2:
        show_limit = st.number_input("顯示筆數", min_value=5, max_value=50, value=10)

    with col3:
        if st.button("🔄 手動重新整理", use_container_width=True):
            st.rerun()

    st.divider()

    # ==================== 取得任務列表 ====================

    try:
        with st.spinner("載入任務列表..."):
            tasks = api_client.list_tasks(limit=show_limit)

        if not tasks:
            st.info("目前沒有任何任務")
        else:
            # ==================== 任務統計 ====================

            st.subheader("📈 任務統計")

            # 計算各狀態的任務數量
            status_counts = {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }

            for task in tasks:
                status = task.get('status', 'unknown')
                if status in status_counts:
                    status_counts[status] += 1

            # 顯示統計指標
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("⏸️ 等待中", status_counts['pending'])

            with col2:
                st.metric("▶️ 處理中", status_counts['processing'])

            with col3:
                st.metric("✅ 已完成", status_counts['completed'])

            with col4:
                st.metric("❌ 失敗", status_counts['failed'])

            st.divider()

            # ==================== 任務列表 ====================

            st.subheader("📋 任務列表")

            # 篩選選項
            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:
                filter_status = st.multiselect(
                    "篩選狀態",
                    options=['pending', 'processing', 'completed', 'failed'],
                    default=['pending', 'processing', 'completed', 'failed']
                )

            with filter_col2:
                sort_by = st.selectbox(
                    "排序方式",
                    options=['最新優先', '最舊優先', '進度（高到低）', '進度（低到高）']
                )

            # 套用篩選
            filtered_tasks = [t for t in tasks if t.get('status') in filter_status]

            # 套用排序
            if sort_by == '最新優先':
                filtered_tasks.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            elif sort_by == '最舊優先':
                filtered_tasks.sort(key=lambda x: x.get('created_at', ''))
            elif sort_by == '進度（高到低）':
                filtered_tasks.sort(key=lambda x: x.get('progress', 0), reverse=True)
            elif sort_by == '進度（低到高）':
                filtered_tasks.sort(key=lambda x: x.get('progress', 0))

            # 顯示任務
            if not filtered_tasks:
                st.info("沒有符合篩選條件的任務")
            else:
                for idx, task in enumerate(filtered_tasks):
                    render_task_card(task, idx, api_client, session_state)

    except APIError as e:
        display_error(f"無法載入任務列表: {str(e)}")
    except Exception as e:
        display_error(f"發生未預期的錯誤: {str(e)}")

    # ==================== 自動重新整理 ====================

    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

    # ==================== 使用說明 ====================

    with st.expander("📖 使用說明"):
        st.markdown("""
        ### 任務管理功能

        #### 自動重新整理
        - 勾選「自動重新整理」可以讓頁面定期更新任務狀態
        - 可調整重新整理的間隔時間（1-10秒）

        #### 篩選與排序
        - **篩選狀態**：選擇要顯示的任務狀態
        - **排序方式**：依據不同條件排序任務列表

        #### 任務操作
        - **查看詳情**：點擊任務卡片展開查看完整資訊
        - **刪除任務**：刪除不需要的任務記錄

        #### 任務狀態說明
        - ⏸️ **等待中**：任務已建立，等待處理
        - ▶️ **處理中**：任務正在執行
        - ✅ **已完成**：任務成功完成
        - ❌ **失敗**：任務執行失敗
        """)


def render_task_card(task: dict, idx: int, api_client, session_state):
    """渲染單個任務卡片"""

    task_id = task.get('task_id', 'unknown')
    status = task.get('status', 'unknown')
    progress = task.get('progress', 0)
    message = task.get('message', '')
    created_at = task.get('created_at', '')
    updated_at = task.get('updated_at', '')

    # 狀態樣式
    status_emoji = {
        'pending': '⏸️',
        'processing': '▶️',
        'completed': '✅',
        'failed': '❌'
    }.get(status, '❓')

    status_color = {
        'pending': 'blue',
        'processing': 'orange',
        'completed': 'green',
        'failed': 'red'
    }.get(status, 'gray')

    # 任務卡片
    with st.expander(
        f"{status_emoji} {task_id[:12]}... - {status} ({progress}%) - {message[:30]}",
        expanded=(status == 'processing')
    ):
        # 進度條（如果未完成）
        if status in ['pending', 'processing']:
            st.progress(progress / 100)

        # 任務資訊
        info_col1, info_col2 = st.columns(2)

        with info_col1:
            st.markdown(f"""
            **任務 ID**: `{task_id}`

            **狀態**: :{status_color}[{status_emoji} {status}]

            **進度**: {progress}%

            **訊息**: {message}
            """)

        with info_col2:
            st.markdown(f"""
            **建立時間**: {created_at[:19] if created_at else 'N/A'}

            **更新時間**: {updated_at[:19] if updated_at else 'N/A'}
            """)

        # 結果（如果已完成）
        if status == 'completed':
            result = task.get('result')
            if result:
                st.subheader("處理結果")
                st.json(result)

        # 錯誤（如果失敗）
        if status == 'failed':
            error = task.get('error')
            if error:
                st.error(f"錯誤: {error}")

        # 完整任務資料
        with st.expander("完整任務資料"):
            st.json(task)

        # 操作按鈕
        btn_col1, btn_col2, btn_col3 = st.columns(3)

        with btn_col1:
            if st.button("🔄 重新整理", key=f"refresh_{task_id}_{idx}"):
                st.rerun()

        with btn_col2:
            # 複製任務 ID
            st.code(task_id, language=None)

        with btn_col3:
            if st.button("🗑️ 刪除", key=f"delete_{task_id}_{idx}", type="secondary"):
                try:
                    api_client.delete_task(task_id)
                    display_success(f"任務 {task_id[:8]}... 已刪除")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    display_error(f"刪除失敗: {str(e)}")
