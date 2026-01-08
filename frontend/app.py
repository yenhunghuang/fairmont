"""Streamlit main application - 使用 /api/v1/process 單一 API 端點."""

import streamlit as st
import pandas as pd
import os
from styles import apply_poc_styles


# Page configuration
st.set_page_config(
    page_title="家具報價單系統",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Apply POC styles
apply_poc_styles()


def init_session_state():
    """Initialize session state variables."""
    # API Client
    if "api_client" not in st.session_state:
        from services.api_client import APIClient
        backend_host = os.getenv("BACKEND_HOST", "localhost")
        backend_port = os.getenv("BACKEND_PORT", "8000")
        api_key = os.getenv("API_KEY", "")
        base_url = f"http://{backend_host}:{backend_port}"
        st.session_state.api_client = APIClient(base_url=base_url, api_key=api_key)

    # Workflow step: upload or results
    if "step" not in st.session_state:
        st.session_state.step = "upload"

    # Processing results
    if "items" not in st.session_state:
        st.session_state.items = None


def get_api_client():
    """Get API client from session state."""
    if "api_client" not in st.session_state:
        init_session_state()
    return st.session_state.api_client


# Initialize session state at module level
init_session_state()


def show_step_indicator():
    """顯示簡單的步驟指示器"""
    steps = ["📤 上傳處理", "📊 檢視結果"]
    step_indices = {"upload": 0, "results": 1}
    current_step = step_indices.get(st.session_state.step, 0)

    step_html = '<div style="display: flex; justify-content: center; gap: 2rem; padding: 0.5rem 0;">'
    for i, step in enumerate(steps):
        if i == current_step:
            style = "color: #2C5F7F; font-weight: bold; font-size: 1.1rem;"
            label = f"{step} 💫"
        elif i < current_step:
            style = "color: #28A745; font-size: 1.1rem;"
            label = f"{step} ✅"
        else:
            style = "color: #999; font-size: 1.1rem;"
            label = step
        step_html += f'<span style="{style}">{label}</span>'
    step_html += '</div>'

    st.markdown(step_html, unsafe_allow_html=True)


def category_to_label(cat):
    """Convert category number to label."""
    if cat == 1:
        return "家具"
    elif cat == 5:
        return "面料"
    return "-"


def show_upload_page():
    """上傳頁面"""
    st.markdown(
        """
        <h1 style="color: #2C5F7F; border-bottom: 3px solid #2C5F7F; padding-bottom: 8px; margin-bottom: 5px;">
            📋 家具報價單系統
        </h1>
        <p style="color: #666; margin: 0 0 10px 0;">上傳 BOQ PDF 檔案，系統自動解析並產出 17 欄 JSON 結果</p>
        """,
        unsafe_allow_html=True,
    )

    show_step_indicator()

    # File uploader
    uploaded_files = st.file_uploader(
        "選擇 PDF 檔案",
        type=["pdf"],
        accept_multiple_files=True,
        key="file_uploader",
        help="支援 BOQ 數量總表與明細規格表，系統自動偵測並合併",
        label_visibility="collapsed",
    )

    if uploaded_files:
        file_names = ", ".join([f.name for f in uploaded_files])
        total_size = sum(f.size for f in uploaded_files) / (1024 * 1024)

        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(
                f"""
                <div style="background: #e8f5e9; border-radius: 8px; padding: 0.6rem 1rem; margin-top: 0.5rem;">
                    <span style="color: #2e7d32; font-weight: 600;">✅ {len(uploaded_files)} 個檔案</span>
                    <span style="color: #666; font-size: 0.85rem; margin-left: 0.5rem;">({total_size:.1f} MB)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            upload_clicked = st.button("🚀 上傳並開始解析", type="primary", use_container_width=True)

        with st.expander(f"📋 檔案詳情", expanded=False):
            for file in uploaded_files:
                file_size_mb = file.size / (1024 * 1024)
                st.markdown(f"• **{file.name}** ({file_size_mb:.2f} MB)")

        if upload_clicked:
            # Show processing message
            progress_placeholder = st.empty()
            status_placeholder = st.empty()

            with progress_placeholder.container():
                st.info("⏳ 正在處理中，請稍候... (約需 1-5 分鐘)")
                progress_bar = st.progress(0)

            try:
                client = get_api_client()

                # Convert to file format
                files_data = [(f.name, f.read()) for f in uploaded_files]

                # Update progress
                progress_bar.progress(10)
                status_placeholder.text("📤 上傳檔案中...")

                # Call process API
                progress_bar.progress(20)
                status_placeholder.text("🔄 AI 解析中... (這可能需要幾分鐘)")

                response = client.process_files(files_data)

                progress_bar.progress(100)

                if not response.get("success"):
                    progress_placeholder.empty()
                    st.error(f"❌ 處理失敗：{response.get('message', '未知錯誤')}")
                    return

                data = response.get("data", {})
                items = data.get("items", []) if isinstance(data, dict) else data
                project_name = data.get("project_name") if isinstance(data, dict) else None

                if not items:
                    progress_placeholder.empty()
                    st.warning("⚠️ 未解析到任何項目")
                    return

                # Store results and advance to results page
                st.session_state.items = items
                st.session_state.project_name = project_name
                st.session_state.step = "results"

                progress_placeholder.empty()
                status_placeholder.empty()
                success_msg = f"✅ 處理完成！共解析 {len(items)} 個項目"
                if project_name:
                    success_msg += f" (專案: {project_name})"
                st.success(success_msg)
                st.rerun()

            except Exception as e:
                progress_placeholder.empty()
                st.error(f"❌ 錯誤：{str(e)}")


def show_results_page():
    """結果頁面 - 顯示解析結果"""
    st.markdown(
        """
        <h1 style="color: #2C5F7F; border-bottom: 3px solid #2C5F7F; padding-bottom: 8px; margin-bottom: 5px;">
            📋 家具報價單系統
        </h1>
        """,
        unsafe_allow_html=True,
    )

    show_step_indicator()

    items = st.session_state.items
    project_name = st.session_state.get("project_name")

    if not items:
        st.warning("⚠️ 無資料可顯示")
        if st.button("返回上傳"):
            st.session_state.step = "upload"
            st.rerun()
        return

    # Display project name if available
    if project_name:
        st.info(f"📁 專案名稱: **{project_name}**")

    st.subheader(f"📊 解析結果 ({len(items)} 個項目)")

    # Summary statistics
    furniture_count = sum(1 for item in items if item.get("category") == 1)
    fabric_count = sum(1 for item in items if item.get("category") == 5)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總項目數", len(items))
    with col2:
        st.metric("家具", furniture_count)
    with col3:
        st.metric("面料", fabric_count)

    st.markdown("---")

    # Create DataFrame for display
    display_data = []
    for item in items:
        display_data.append({
            "序號": item.get("no"),
            "項目編號": item.get("item_no"),
            "描述": item.get("description", "")[:50] + ("..." if len(item.get("description", "")) > 50 else ""),
            "分類": category_to_label(item.get("category")),
            "附屬": item.get("affiliate") or "-",
            "數量": item.get("qty"),
            "單位": item.get("uom"),
            "尺寸": item.get("dimension", "")[:30] if item.get("dimension") else "-",
            "品牌": item.get("brand") or "-",
            "有圖片": "✅" if item.get("photo") else "❌",
        })

    df = pd.DataFrame(display_data)

    # Display table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    st.markdown("---")

    # Filter options
    with st.expander("🔍 篩選與詳情", expanded=False):
        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            category_filter = st.selectbox(
                "按分類篩選",
                options=["全部", "家具", "面料"],
                index=0,
            )

        with filter_col2:
            search_term = st.text_input("搜尋項目編號或描述", "")

        # Apply filters
        filtered_items = items
        if category_filter == "家具":
            filtered_items = [i for i in filtered_items if i.get("category") == 1]
        elif category_filter == "面料":
            filtered_items = [i for i in filtered_items if i.get("category") == 5]

        if search_term:
            search_lower = search_term.lower()
            filtered_items = [
                i for i in filtered_items
                if search_lower in (i.get("item_no", "").lower())
                or search_lower in (i.get("description", "").lower())
            ]

        if filtered_items != items:
            st.write(f"篩選結果：{len(filtered_items)} 個項目")

            # Show filtered details
            for item in filtered_items[:10]:
                with st.container():
                    st.markdown(f"**{item.get('item_no')}** - {item.get('description', '')[:80]}")
                    detail_col1, detail_col2, detail_col3 = st.columns(3)
                    with detail_col1:
                        st.caption(f"分類: {category_to_label(item.get('category'))}")
                    with detail_col2:
                        st.caption(f"附屬: {item.get('affiliate') or '-'}")
                    with detail_col3:
                        st.caption(f"數量: {item.get('qty') or '-'} {item.get('uom') or ''}")

    st.markdown("---")

    # Export options
    st.subheader("📥 匯出選項")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Export as JSON
        import json
        json_str = json.dumps(items, ensure_ascii=False, indent=2)
        st.download_button(
            label="⬇️ 下載 JSON",
            data=json_str,
            file_name="boq_items.json",
            mime="application/json",
            use_container_width=True,
        )

    with col2:
        # Export as CSV
        csv_data = []
        for item in items:
            csv_data.append({
                "no": item.get("no"),
                "item_no": item.get("item_no"),
                "description": item.get("description"),
                "dimension": item.get("dimension"),
                "qty": item.get("qty"),
                "uom": item.get("uom"),
                "unit_cbm": item.get("unit_cbm"),
                "note": item.get("note"),
                "location": item.get("location"),
                "materials_specs": item.get("materials_specs"),
                "brand": item.get("brand"),
                "category": item.get("category"),
                "affiliate": item.get("affiliate"),
            })
        csv_df = pd.DataFrame(csv_data)
        csv_str = csv_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="⬇️ 下載 CSV",
            data=csv_str,
            file_name="boq_items.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col3:
        if st.button("📤 上傳新檔案", use_container_width=True):
            st.session_state.step = "upload"
            st.session_state.items = None
            st.rerun()


def main():
    """Main application entry point."""
    if st.session_state.step == "upload":
        show_upload_page()
    elif st.session_state.step == "results":
        show_results_page()
    else:
        st.session_state.step = "upload"
        show_upload_page()


if __name__ == "__main__":
    main()
