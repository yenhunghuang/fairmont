"""Simple CSS styles for POC - minimal branding."""

import streamlit as st


def apply_poc_styles():
    """應用 POC 級別的簡單樣式。"""
    st.markdown(
        """
        <style>
        /* Main container padding and width */
        .main {
            max-width: 1200px;
            margin: 0 auto;
        }

        /* Reduce default Streamlit block spacing */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }

        /* Reduce spacing between elements */
        .stMarkdown {
            margin-bottom: 0 !important;
        }

        div[data-testid="stVerticalBlock"] > div {
            gap: 0.5rem !important;
        }

        /* Step indicator colors */
        .step-active {
            color: #2C5F7F;
            font-weight: bold;
        }

        .step-completed {
            color: #28A745;
        }

        .step-pending {
            color: #6C757D;
        }

        /* Headers */
        h1 {
            color: #2C5F7F;
            border-bottom: 3px solid #2C5F7F;
            padding-bottom: 10px;
        }

        h2 {
            color: #2C5F7F;
            margin-top: 20px;
        }

        /* Success box */
        .success-box {
            background-color: #D4EDDA;
            border-left: 4px solid #28A745;
            padding: 1em;
            border-radius: 0.5em;
            margin: 1em 0;
        }

        /* Error box */
        .error-box {
            background-color: #F8D7DA;
            border-left: 4px solid #DC3545;
            padding: 1em;
            border-radius: 0.5em;
            margin: 1em 0;
        }

        /* Info box */
        .info-box {
            background-color: #D1ECF1;
            border-left: 4px solid #17A2B8;
            padding: 1em;
            border-radius: 0.5em;
            margin: 1em 0;
        }

        /* File uploader area - Unified dropzone with header */
        [data-testid="stFileUploader"] {
            margin-top: 0.5rem !important;
        }

        [data-testid="stFileUploader"] > section {
            flex-direction: column !important;
            display: flex !important;
            border: 3px dashed #2C5F7F !important;
            border-radius: 16px !important;
            background: linear-gradient(135deg, #f0f7fa 0%, #e8f4f8 100%) !important;
            overflow: visible !important;
            height: auto !important;
            min-height: auto !important;
            max-height: none !important;
        }

        [data-testid="stFileUploader"] > section::before {
            content: "📁 上傳 PDF 檔案";
            display: block !important;
            width: 100% !important;
            order: -2 !important;
            text-align: center;
            color: #2C5F7F;
            font-size: 1.2rem;
            font-weight: bold;
            padding: 0.8rem 1rem 0.2rem 1rem;
            background: transparent;
            box-sizing: border-box;
        }

        [data-testid="stFileUploader"] > section::after {
            content: "拖放上傳 | 最多 5 個檔案，每個 50MB";
            display: block !important;
            width: 100% !important;
            order: -1 !important;
            text-align: center;
            color: #666;
            font-size: 0.8rem;
            padding: 0.1rem 1rem 0.4rem 1rem;
            background: transparent;
            box-sizing: border-box;
        }

        /* Dropzone instructions area - more compact */
        [data-testid="stFileUploaderDropzoneInstructions"] {
            padding: 0.5rem 1.5rem !important;
            justify-content: center !important;
            align-items: center !important;
            gap: 0.8rem !important;
        }

        /* Smaller upload icon */
        [data-testid="stFileUploaderDropzoneInstructions"] svg {
            width: 32px !important;
            height: 32px !important;
        }

        [data-testid="stFileUploader"] > section:hover {
            background: linear-gradient(135deg, #e8f4f8 0%, #d0e8f0 100%) !important;
            box-shadow: 0 8px 25px rgba(44, 95, 127, 0.15) !important;
        }

        /* Dropzone text - compact */
        [data-testid="stFileUploaderDropzoneInstructions"] span {
            font-size: 0.9rem !important;
            color: #2C5F7F !important;
        }

        [data-testid="stFileUploaderDropzoneInstructions"] small {
            font-size: 0.75rem !important;
            color: #888 !important;
        }

        /* Browse button inside dropzone - compact */
        [data-testid="stFileUploader"] > section > span > button {
            background-color: #2C5F7F !important;
            color: white !important;
            border: none !important;
            padding: 0.4rem 1.2rem !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            transition: all 0.2s ease !important;
            margin: 0.3rem 0 0.6rem 0 !important;
        }

        [data-testid="stFileUploader"] > section > span > button:hover {
            background-color: #1E3F52 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(44, 95, 127, 0.3) !important;
        }

        /* Hide native Streamlit file list (we use our own expander) */
        [data-testid="stFileUploaderFile"] {
            display: none !important;
        }

        /* Primary buttons */
        .stButton > button[kind="primary"] {
            background-color: #2C5F7F;
            color: white;
            font-weight: bold;
            border-radius: 6px;
            padding: 10px 20px;
            transition: all 0.3s ease;
        }

        .stButton > button[kind="primary"]:hover {
            background-color: #1E3F52;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(44, 95, 127, 0.3);
        }

        /* Secondary buttons */
        .stButton > button {
            border-radius: 6px;
            padding: 8px 16px;
        }

        /* Progress bar styling */
        .stProgress > div > div > div > div {
            background-color: #2C5F7F;
        }

        /* Divider */
        hr {
            border: none;
            border-top: 2px solid #E0E0E0;
            margin: 1.5em 0;
        }

        /* Text styling */
        .subtitle {
            color: #666;
            font-size: 1.1em;
            margin-bottom: 1em;
        }

        /* Metric cards */
        [data-testid="metric-container"] {
            background-color: #F8F9FA;
            border-radius: 8px;
            padding: 1em;
            border-left: 4px solid #2C5F7F;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_header_style(title: str, subtitle: str = ""):
    """應用 POC 級別的頁面頭部樣式。

    Args:
        title: 頁面標題
        subtitle: 副標題（可選）
    """
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f'<p class="subtitle">{subtitle}</p>', unsafe_allow_html=True)
    st.markdown("---")
