"""Material table component."""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any


def display_material_table(items: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Display material table with Fairmont format columns.

    Args:
        items: List of BOQ items

    Returns:
        DataFrame of displayed items
    """
    st.subheader("📊 材料清單")

    if not items:
        st.info("暫無材料資料")
        return pd.DataFrame()

    # Prepare data for display
    display_data = []
    for item in items:
        display_data.append({
            "序號": item.get("no", ""),
            "項目編號": item.get("item_no", ""),
            "描述": item.get("description", ""),
            "尺寸 (mm)": item.get("dimension", ""),
            "數量": item.get("qty", ""),
            "單位": item.get("uom", ""),
            "備註": item.get("note", ""),
            "位置": item.get("location", ""),
            "材料/規格": item.get("materials_specs", ""),
        })

    df = pd.DataFrame(display_data)

    # Display table
    st.dataframe(
        df,
        use_container_width=True,
        height=400,
        hide_index=True,
    )

    # Display statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📈 總項目數", len(items))
    with col2:
        items_with_qty = sum(1 for item in items if item.get("qty"))
        st.metric("📋 有數量的項目", items_with_qty)
    with col3:
        items_with_photo = sum(1 for item in items if item.get("photo_path"))
        st.metric("🖼️ 有圖片的項目", items_with_photo)
    with col4:
        items_verified = sum(1 for item in items if item.get("qty_verified"))
        st.metric("✅ 已驗證數量", items_verified)

    return df


def display_item_details(item: Dict[str, Any]) -> None:
    """
    Display detailed view of a single item.

    Args:
        item: BOQ item dictionary
    """
    st.subheader(f"📋 項目詳情：{item.get('item_no', '未知')}")

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**序號**: {item.get('no', '')}")
        st.write(f"**項目編號**: {item.get('item_no', '')}")
        st.write(f"**描述**: {item.get('description', '')}")
        st.write(f"**尺寸**: {item.get('dimension', '')}")
        st.write(f"**數量**: {item.get('qty', '')}")
        st.write(f"**單位**: {item.get('uom', '')}")

    with col2:
        st.write(f"**備註**: {item.get('note', '')}")
        st.write(f"**位置**: {item.get('location', '')}")
        st.write(f"**材料/規格**: {item.get('materials_specs', '')}")

        # Verification status
        qty_verified = item.get('qty_verified', False)
        qty_source = item.get('qty_source', '')

        if qty_verified:
            st.success(f"✅ 已驗證（來源：{qty_source}）")
        else:
            st.warning("⚠️ 數量未驗證")

    # Display photo if available
    if item.get('photo_path'):
        st.subheader("🖼️ 圖片")
        try:
            st.image(item['photo_path'], use_column_width=True)
        except Exception as e:
            st.warning(f"無法載入圖片：{e}")


def editable_material_table(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Display editable material table.

    Args:
        items: List of BOQ items

    Returns:
        Updated items list
    """
    st.subheader("✏️ 編輯材料清單")

    if not items:
        st.info("暫無材料資料")
        return []

    updated_items = []

    for idx, item in enumerate(items):
        with st.expander(f"編輯 - {item.get('item_no', '')} ({item.get('description', '')})"):
            col1, col2 = st.columns(2)

            with col1:
                updated_item = {"id": item.get("id")}
                updated_item["qty"] = st.number_input(
                    "數量",
                    value=float(item.get("qty", 0)),
                    min_value=0.0,
                    key=f"qty_{idx}",
                )
                updated_item["description"] = st.text_input(
                    "描述",
                    value=item.get("description", ""),
                    key=f"desc_{idx}",
                )
                updated_item["dimension"] = st.text_input(
                    "尺寸",
                    value=item.get("dimension", ""),
                    key=f"dim_{idx}",
                )

            with col2:
                updated_item["materials_specs"] = st.text_area(
                    "材料/規格",
                    value=item.get("materials_specs", ""),
                    key=f"mat_{idx}",
                )
                updated_item["location"] = st.text_input(
                    "位置",
                    value=item.get("location", ""),
                    key=f"loc_{idx}",
                )
                updated_item["note"] = st.text_input(
                    "備註",
                    value=item.get("note", ""),
                    key=f"note_{idx}",
                )

            updated_items.append(updated_item)

    return updated_items
