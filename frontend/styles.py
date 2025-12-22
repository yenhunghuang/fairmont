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

        /* File uploader area */
        [data-testid="stFileUploadDropzone"] {
            border: 2px dashed #2C5F7F;
            border-radius: 8px;
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
