"""Preview page for quotation and Excel export."""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.material_table import display_material_table
from components.source_reference import display_document_info
from components.progress_display import display_task_status


def init_session_state():
    """Initialize session state."""
    if "selected_quotation_id" not in st.session_state:
        st.session_state.selected_quotation_id = None


def fetch_documents():
    """Fetch documents from API."""
    client = st.session_state.api_client
    try:
        response = client.list_documents()
        if response.get("success"):
            return response.get("data", {}).get("documents", [])
        return []
    except Exception as e:
        st.error(f"無法取得文件列表：{e}")
        return []


def fetch_parse_result(document_id: str):
    """Fetch parse result for a document."""
    client = st.session_state.api_client
    try:
        response = client.get_parse_result(document_id)
        return response
    except Exception as e:
        return {"success": False, "message": str(e)}


def create_and_export_quotation(document_ids: list):
    """Create quotation and export to Excel."""
    client = st.session_state.api_client
    try:
        # Create quotation
        quotation_response = client.create_quotation(document_ids)
        if not quotation_response.get("success"):
            return {"error": quotation_response.get("message", "建立報價單失敗")}

        quotation_id = quotation_response.get("data", {}).get("id")
        if not quotation_id:
            return {"error": "未取得報價單 ID"}

        # Export to Excel
        export_response = client.export_excel(quotation_id)
        if not export_response.get("success"):
            return {"error": export_response.get("message", "匯出 Excel 失敗")}

        # Download Excel
        excel_content = client.download_excel(quotation_id)
        return {"quotation_id": quotation_id, "excel_content": excel_content}

    except Exception as e:
        return {"error": str(e)}


def main():
    """Main preview page."""
    init_session_state()

    st.title("📊 預覽報價單")
    st.markdown("---")

    st.write("""
    在此頁面查看已解析的 BOQ 項目、建立報價單，以及產出 Excel 格式的報價單。
    """)

    # Fetch documents
    if st.button("🔄 重新整理", use_container_width=False):
        st.rerun()

    documents = fetch_documents()

    # Tab selection
    tab1, tab2, tab3 = st.tabs(["📋 已上傳文件", "📈 解析結果", "📥 匯出 Excel"])

    with tab1:
        st.subheader("📋 已上傳的文件")

        if not documents:
            st.info("暫無已上傳的文件，請先在「上傳 PDF」頁面上傳檔案")
        else:
            for doc in documents:
                status = doc.get("parse_status", "pending")
                status_icons = {
                    "pending": "⏳ 等待中",
                    "processing": "🔄 解析中",
                    "completed": "✅ 已完成",
                    "failed": "❌ 失敗",
                }
                status_text = status_icons.get(status, "❓ 未知")

                with st.expander(f"📄 {doc.get('filename', '')} - {status_text}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**文件 ID:** {doc.get('id', '')}")
                        st.write(f"**檔案大小:** {doc.get('file_size', 0) / (1024 * 1024):.1f} MB")
                    with col2:
                        st.write(f"**解析狀態:** {status_text}")
                        if doc.get("extracted_items_count"):
                            st.write(f"**提取項目數:** {doc.get('extracted_items_count', 0)}")

                    if status == "failed" and doc.get("parse_error"):
                        st.error(f"錯誤訊息：{doc.get('parse_error')}")

    with tab2:
        st.subheader("📈 解析結果")

        completed_docs = [d for d in documents if d.get("parse_status") == "completed"]

        if not completed_docs:
            st.info("暫無已完成解析的文件")
        else:
            for doc in completed_docs:
                st.write(f"### 📄 {doc.get('filename', '')}")

                # Fetch parse result
                result = fetch_parse_result(doc.get("id"))

                if result.get("success"):
                    items = result.get("data", {}).get("items", [])
                    stats = result.get("data", {}).get("statistics", {})

                    st.write(f"共 {stats.get('total_items', 0)} 個項目")

                    if items:
                        # Display as table
                        display_material_table(items)
                else:
                    st.warning(result.get("message", "無法取得解析結果"))

                st.markdown("---")

    with tab3:
        st.subheader("📥 匯出 Excel")

        completed_docs = [d for d in documents if d.get("parse_status") == "completed"]

        if not completed_docs:
            st.info("請先等待文件解析完成")
        else:
            st.write("選擇要匯出的文件：")

            selected_doc_ids = []
            for doc in completed_docs:
                if st.checkbox(f"📄 {doc.get('filename', '')}", value=True, key=f"doc_{doc.get('id')}"):
                    selected_doc_ids.append(doc.get("id"))

            st.markdown("---")

            if selected_doc_ids:
                if st.button("🚀 產出 Excel 報價單", use_container_width=True, type="primary"):
                    with st.spinner("正在產出 Excel..."):
                        result = create_and_export_quotation(selected_doc_ids)

                    if "error" in result:
                        st.error(f"❌ {result['error']}")
                    else:
                        st.success("✅ Excel 報價單產出成功！")

                        # Download button
                        st.download_button(
                            label="💾 下載 Excel 檔案",
                            data=result["excel_content"],
                            file_name="quotation.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
            else:
                st.warning("請至少選擇一個文件")

        st.markdown("---")

        st.info("""
        ✨ **下一步：**
        - 在 Excel 中手動填寫 Unit Rate、Amount、CBM 等欄位
        - 儲存並分享報價單
        """)


if __name__ == "__main__":
    main()
