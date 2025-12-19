"""Preview page for quotation and Excel export."""

import streamlit as st
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.api_client import APIClient
from components.material_table import display_material_table
from components.source_reference import display_document_info
from components.progress_display import display_task_status


def init_session_state():
    """Initialize session state."""
    if "preview_client" not in st.session_state:
        backend_host = os.getenv("BACKEND_HOST", "localhost")
        backend_port = os.getenv("BACKEND_PORT", "8000")
        base_url = f"http://{backend_host}:{backend_port}"
        st.session_state.preview_client = APIClient(base_url=base_url)

    if "selected_quotation_id" not in st.session_state:
        st.session_state.selected_quotation_id = None


def main():
    """Main preview page."""
    st.set_page_config(
        page_title="預覽報價單 - 家具報價單系統",
        page_icon="📊",
        layout="wide",
    )

    init_session_state()

    st.title("📊 預覽報價單")
    st.markdown("---")

    st.write("""
    在此頁面查看已解析的 BOQ 項目、建立報價單，以及產出 Excel 格式的報價單。
    """)

    # Tab selection
    tab1, tab2, tab3 = st.tabs(["📋 已上傳文件", "📈 報價單", "📥 匯出 Excel"])

    with tab1:
        st.subheader("📋 已上傳的文件")

        # List documents
        try:
            # In a real implementation, this would call the API
            documents = []  # await client.list_documents()

            if not documents:
                st.info("暫無已上傳的文件")
            else:
                for doc in documents:
                    with st.expander(f"📄 {doc.get('filename', '')}"):
                        display_document_info(doc)

                        # Show items from this document
                        if doc.get("parse_status") == "completed":
                            st.subheader("📋 提取的項目")
                            # Display items here
                            st.write(f"找到 {doc.get('extracted_items_count', 0)} 個項目")

        except Exception as e:
            st.error(f"❌ 無法取得文件列表：{e}")

    with tab2:
        st.subheader("📈 建立報價單")

        st.write("從已解析的文件建立報價單")

        # Document selection (would be from API in real implementation)
        st.info("💡 請先在「上傳 PDF」頁面上傳並解析檔案")

        # Create quotation button
        if st.button("➕ 建立新報價單", use_container_width=True):
            st.info("報價單建立成功（此為示例）")

    with tab3:
        st.subheader("📥 匯出 Excel")

        st.write("將報價單匯出為 Excel 格式")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("⚙️ 匯出選項")

            include_photos = st.checkbox("嵌入圖片", value=True)

            if include_photos:
                photo_height = st.slider(
                    "圖片高度（公分）",
                    min_value=1.0,
                    max_value=10.0,
                    value=3.0,
                    step=0.5,
                )
            else:
                photo_height = 0.0

        with col2:
            st.subheader("📊 報價單資訊")
            st.info("""
            匯出前，請確認：
            - ✅ 所有項目信息完整
            - ✅ 數量已驗證
            - ✅ 報價單標題正確
            """)

        # Export button
        if st.button("🚀 產出 Excel", use_container_width=True, type="primary"):
            st.success("✅ Excel 匯出成功（此為示例）")

            # Download button
            st.download_button(
                label="💾 下載 Excel 檔案",
                data=b"sample",  # In real implementation, this would be the actual file
                file_name="quotation_sample.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        st.markdown("---")

        st.info("""
        ✨ **下一步：**
        - 在 Excel 中手動填寫 Unit Rate、Amount、CBM 等欄位
        - 儲存並分享報價單
        """)


if __name__ == "__main__":
    main()
