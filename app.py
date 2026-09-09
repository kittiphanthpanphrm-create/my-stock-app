import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import os
import altair as alt
from datetime import datetime
from pypdf import PdfReader

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="TKK ERP - ระบบจัดการสต็อกและคลังสินค้า",
    page_icon="📦",
    layout="wide"
)

# สไตล์ CSS ตัวอักษรใหญ่ หนา ช่องไฟสวยงาม
st.markdown("""
<style>
button[aria-label="Delete"] { display: none !important; }
div[data-testid="stFileUploaderDeleteBtn"] { display: none !important; }

[data-testid="stSidebar"] { padding-top: 1.5rem; padding-bottom: 2rem; }

.main-sidebar-title {
    font-size: 1.65rem !important;
    font-weight: 800 !important;
    color: #1E293B;
    margin-bottom: 1.25rem !important;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #E2E8F0;
}

.section-label {
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    color: #334155;
    margin-top: 1rem !important;
    margin-bottom: 0.6rem !important;
}

div[data-testid="stRadio"] div[role="radiogroup"] > label {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    padding: 0.45rem 0.6rem !important;
    margin-bottom: 0.35rem !important;
    border-radius: 6px;
}

h1 { font-size: 2rem !important; font-weight: 800 !important; }
h2, h3 { font-weight: 700 !important; }
div[data-testid="stMetricValue"] { font-size: 1.85rem !important; font-weight: 800 !important; }
div[data-testid="stMetricLabel"] { font-size: 1rem !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

DB_FILE = "database_inventory.csv"
SNAPSHOT_FILE = "inventory_snapshots.csv"

ALL_ZONES = [
    "AA", "AB", "BB", "CC", "DD", "EE", "FF", "GG", "HH",
    "IA", "IB", "IC", "II", "JJ", "KK", "LL", "MA", "MB", 
    "MC", "MM", "NN", "OO", "PP", "QQ", "RR", "ST", "TT", 
    "UU", "XX", "YY"
]

def load_database():
    if os.path.exists(DB_FILE):
        try:
            return pd.read_csv(DB_FILE, dtype=str)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_database(df):
    df.to_csv(DB_FILE, index=False)

def parse_numeric_stock(val):
    try:
        s = str(val).strip().replace(":", "")
        return float(s)
    except Exception:
        return 0.0

def load_snapshots():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            df = pd.read_csv(SNAPSHOT_FILE)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def record_inventory_snapshot(df_to_record, source_file, target_zone):
    if df_to_record.empty:
        return
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    month_str = datetime.now().strftime("%Y-%m")
    
    records = []
    for _, row in df_to_record.iterrows():
        records.append({
            "timestamp": now_str,
            "month_year": month_str,
            "filename": source_file,
            "zone": target_zone,
            "barcode": str(row.get("รหัสสินค้า", "")).strip(),
            "sub_code": str(row.get("รหัสรอง", "")).strip(),
            "product_name": str(row.get("ชื่อรายการสินค้า", "")).strip(),
            "tag": str(row.get("แท็ก {Tag}", "{ทั่วไป}")).strip(),
            "stock": parse_numeric_stock(row.get("คงเหลือ", 0))
        })
    new_snap_df = pd.DataFrame(records)
    if os.path.exists(SNAPSHOT_FILE):
        try:
            old_snap = pd.read_csv(SNAPSHOT_FILE)
            combined = pd.concat([old_snap, new_snap_df], ignore_index=True)
        except Exception:
            combined = new_snap_df
    else:
        combined = new_snap_df
    combined.to_csv(SNAPSHOT_FILE, index=False)

def format_tag_value(val):
    s = str(val).strip()
    if not s or s.lower() in ["nan", "none", "-", ""]:
        return "{ทั่วไป}"
    if s.startswith("{") and s.endswith("}"):
        return s
    m = re.search(r'[\{\[\(](.*?)[\}\]\)]', s)
    if m:
        return f"{{{m.group(1).strip()}}}"
    return f"{{{s}}}"

def parse_tag_and_clean_name(raw_text):
    text = str(raw_text).replace("•", "").strip()
    m_curly = re.search(r'\{([^}]+)\}', text)
    if m_curly:
        return f"{{{m_curly.group(1).strip()}}}", re.sub(r'\{[^}]+\}', '', text).strip()
    m_square = re.search(r'\[([^\]]+)\]', text)
    if m_square:
        return f"{{{m_square.group(1).strip()}}}", re.sub(r'\[[^\]]+\]', '', text).strip()
    m_paren = re.search(r'\(([^)]+)\)', text)
    if m_paren and len(m_paren.group(1).strip()) <= 15:
        return f"{{{m_paren.group(1).strip()}}}", re.sub(r'\([^)]+\)', '', text).strip()
    return "{ทั่วไป}", text

def clean_and_prepare_df(raw_df, source_name, target_zone):
    df = raw_df.copy()
    
    if "Unnamed: 0" in df.columns:
        df = df.iloc[1:].copy()
        
    df.columns = [f"{c}_{i}" if list(df.columns).count(c) > 1 else c for i, c in enumerate(df.columns)]
    df["โซน"] = str(target_zone).upper().strip()

    # ตรวจหาตำแหน่งคอลัมน์ A (รหัสรอง), B (บาร์โค้ด+ชื่อสินค้า), D (แท็ก), E (คงเหลือ)
    name_col = df.columns[1] if len(df.columns) >= 2 else df.columns[0]
    sub_col = df.columns[0] if len(df.columns) >= 1 and df.columns[0] != name_col else None
    
    tag_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["แท็ก", "tag"]) or (df[c].astype(str).str.contains(r'\{.*\}').sum() > len(df) * 0.2)), None)
    if not tag_col and len(df.columns) >= 4:
        tag_col = df.columns[3]

    stock_col = next((c for c in df.columns if "คงเหลือ" in str(c)), None)
    if not stock_col and len(df.columns) >= 5:
        stock_col = df.columns[4]

    barcodes = []
    sub_codes = []
    cleaned_names = []
    tags = []

    for idx, row in df.iterrows():
        raw_text = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
        raw_sub = str(row[sub_col]).strip() if sub_col and pd.notna(row[sub_col]) else ""
        raw_sub = re.sub(r'\.0$', '', raw_sub)
        if raw_sub.lower() in ["nan", "none", "-"]:
            raw_sub = ""
        
        # ค้นหาเลขบาร์โค้ด 8-14 หลักจากคอลัมน์ B
        bc_match = re.search(r'(\d{8,14})', raw_text)
        if bc_match:
            bc_val = bc_match.group(1)
            name_val = re.sub(r'^\s*' + bc_val + r'[_\s\-\•]*', '', raw_text).strip()
        else:
            bc_val = ""
            name_val = raw_text

        # ตรวจสอบแท็กจากคอลัมน์ D
        if tag_col and pd.notna(row[tag_col]) and str(row[tag_col]).strip() and str(row[tag_col]).lower() != "nan":
            tag_val = format_tag_value(row[tag_col])
            _, clean_n = parse_tag_and_clean_name(name_val)
        else:
            tag_val, clean_n = parse_tag_and_clean_name(name_val)

        # หากไม่มีบาร์โค้ด 13 หลัก ให้ตรวจสอบว่าในคอลัมน์ A เป็นบาร์โค้ดหรือไม่
        if not bc_val and len(raw_sub) >= 8:
            bc_val = raw_sub
            raw_sub = ""

        barcodes.append(bc_val)
        sub_codes.append(raw_sub)
        cleaned_names.append(clean_n if clean_n else raw_text)
        tags.append(tag_val)

    df["รหัสสินค้า"] = barcodes
    df["รหัสรอง"] = sub_codes
    df["ชื่อรายการสินค้า"] = cleaned_names
    df["แท็ก {Tag}"] = tags

    if stock_col:
        df["คงเหลือ"] = df[stock_col].astype(str).str.replace(":", "", regex=False).str.strip()
    else:
        df["คงเหลือ"] = "0"
    df["คงเหลือ"] = df["คงเหลือ"].replace("nan", "0")

    status_col = next((c for c in df.columns if "สถานะ" in str(c)), None)
    df["สถานะ"] = df[status_col].astype(str).str.strip() if status_col else "พร้อมขาย"
    df["สถานะ"] = df["สถานะ"].replace("nan", "พร้อมขาย")

    df["จำนวนสั่งล่าสุด"] = "0"
    df["หน่วยนับ"] = "-"
    df["ชื่อไฟล์ที่มา"] = str(source_name)

    cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}", "หน่วยนับ", "จำนวนสั่งล่าสุด", "โซน", "คงเหลือ", "สถานะ", "ชื่อไฟล์ที่มา"]
    return df[[c for c in cols if c in df.columns]]

def extract_fields_from_text(text, source_name, target_zone):
    pattern = re.compile(
        r'(\d{4,5})\s+รหัส\s*:\s*(\d+)\s*รหัสรอง\s*:\s*(\d+)[•\s\-]*(.*?)(?:\{([^}]+)\})?\s*หน่วยนับ\s*:\s*([^คง]+)คงเหลือ\s*:\s*([\-\d\.]+)\s*(เลิกขาย|ขาย)?\s*(\d+)\s*โซน\s*:\s*([A-Za-z0-9]+)',
        re.DOTALL
    )
    matches = pattern.findall(text)
    data = []
    for m in matches:
        raw_name = m[3].strip()
        tag, clean_name = parse_tag_and_clean_name(raw_name)
        if m[4]:
            tag = f"{{{m[4].strip()}}}"
        data.append({
            "#": m[0],
            "รหัสสินค้า": str(m[1]).strip(),
            "รหัสรอง": str(m[2]).strip(),
            "ชื่อรายการสินค้า": clean_name,
            "แท็ก {Tag}": tag,
            "หน่วยนับ": m[5].strip(),
            "จำนวนสั่งล่าสุด": str(int(m[8])) if m[8].isdigit() else "0",
            "โซน": str(target_zone).upper().strip(),
            "คงเหลือ": str(m[6]).strip() if m[6] else "0",
            "สถานะ": m[7] if m[7] else "พร้อมขาย",
            "ชื่อไฟล์ที่มา": source_name
        })
    return pd.DataFrame(data)

def render_product_cards(items_df, current_zone, is_problem=False):
    cols = st.columns(3)
    for idx, row in items_df.iterrows():
        raw_b = str(row.get("รหัสสินค้า", "")).replace(".0", "").strip()
        barcode = re.sub(r'[^0-9A-Za-z_-]', '', raw_b)
        if barcode.lower() in ["nan", "none"]: barcode = ""
        
        raw_s = str(row.get("รหัสรอง", "")).replace(".0", "").strip()
        sub_code = re.sub(r'[^0-9A-Za-z_-]', '', raw_s)
        if sub_code.lower() in ["nan", "none"]: sub_code = ""
        
        name = str(row.get("ชื่อรายการสินค้า", "")).strip()
        qty = row.get("จำนวนสั่งล่าสุด", 0)
        if str(qty).lower() == "nan": qty = "0"
        stock = row.get("คงเหลือ", 0)
        if str(stock).lower() == "nan": stock = "0"
        
        code_for_img = barcode if barcode else sub_code
        img_url = f"https://tkkonlineshop.com/images/products/{code_for_img}.jpg"
        web_link = f"https://tkkonlineshop.com/products/{code_for_img}" if code_for_img else "https://tkkonlineshop.com"
        
        with cols[idx % 3]:
            with st.container(border=True):
                if code_for_img and len(code_for_img) >= 3:
                    try:
                        st.image(img_url, use_container_width=True)
                    except Exception:
                        st.markdown(
                            f"""
                            <div style="background-color:#F1F5F9; border:1px dashed #CBD5E1; border-radius:8px; height:180px; display:flex; align-items:center; justify-content:center; flex-direction:column; color:#64748B; margin-bottom:10px;">
                                <span style="font-size:36px;">📦</span>
                                <span style="font-size:13px; font-weight:600; margin-top:6px;">ไม่มีรูปภาพในระบบ TKK</span>
                                <span style="font-size:11px; color:#94A3B8;">(รหัส: {code_for_img})</span>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                else:
                    st.markdown(
                        f"""
                        <div style="background-color:#F8FAFC; border:1px dashed #CBD5E1; border-radius:8px; height:180px; display:flex; align-items:center; justify-content:center; flex-direction:column; color:#64748B; margin-bottom: 10px;">
                            <span style="font-size:36px;">📦</span>
                            <span style="font-size:12px; margin-top:4px;">ไม่พบเลขรหัสสินค้า</span>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                st.markdown(f"### **{name}**")
                st.caption(f"**รหัสสินค้า:** `{barcode or '-'}` | **โซน:** `{current_zone}`")
                st.markdown("📋 **รหัสรอง (คลิกเพื่อ Copy):**")
                st.code(sub_code if sub_code else (barcode if barcode else "-"), language="text")
                
                if is_problem or parse_numeric_stock(stock) < 0:
                    st.markdown(f"🚨 **คงเหลือ:** :red[{stock}] | 🛒 **สั่งล่าสุด:** **{qty}**")
                else:
                    st.markdown(f"📦 **คงเหลือ:** **{stock}** | 🛒 **สั่งล่าสุด:** **{qty}**")
                    
                if code_for_img:
                    st.link_button("🌐 เปิดดูบนเว็บ TKK Online", web_link, use_container_width=True)

# โหลดฐานข้อมูล
if "current_df" not in st.session_state:
    st.session_state.current_df = load_database()
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# แถบด้านซ้าย
with st.sidebar:
    st.markdown('<div class="main-sidebar-title">📦 จัดการสต็อก</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-label">🎯 ฟังก์ชันการทำงาน</div>', unsafe_allow_html=True)
    menu = st.radio(
        "",
        [
            "📊 ภาพรวมคลังสินค้า", 
            "📑 จัดการสินค้า (รายโซน)", 
            "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)", 
            "📈 สรุปรายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง)",
            "🔍 ค้นหาสินค้า & Tag"
        ]
    )
    
    st.divider()
    st.markdown('<div class="section-label">📍 โซนสินค้า (30 โซน)</div>', unsafe_allow_html=True)
    selected_zone = st.selectbox("เลือกโซนที่ต้องการเข้าดู:", options=ALL_ZONES, index=0)
    
    st.divider()
    st.markdown(f'<div class="section-label">⚙️ จัดการข้อมูล [โซน {selected_zone}]</div>', unsafe_allow_html=True)
    
    with st.expander(f"📥 เพิ่มไฟล์ข้อมูลเข้าโซน {selected_zone}", expanded=False):
        uploaded_files = st.file_uploader(
            f"เลือกไฟล์สำหรับโซน {selected_zone} (PDF, CSV, XLSX)", 
            type=["pdf", "csv", "xlsx", "xls"], 
            accept_multiple_files=True,
            key=f"uploader_{selected_zone}_{st.session_state.uploader_key}"
        )
        
        if uploaded_files:
            preview_dfs = []
            for u_file in uploaded_files:
                try:
                    if u_file.name.endswith(".pdf"):
                        reader = PdfReader(u_file)
                        full_text = "".join([page.extract_text() + "\n" for page in reader.pages])
                        t_df = extract_fields_from_text(full_text, u_file.name, selected_zone)
                    elif u_file.name.endswith(".csv"):
                        t_df = clean_and_prepare_df(pd.read_csv(u_file), u_file.name, selected_zone)
                    elif u_file.name.endswith(".xlsx") or u_file.name.endswith(".xls"):
                        t_df = clean_and_prepare_df(pd.read_excel(u_file), u_file.name, selected_zone)
                    
                    if not t_df.empty:
                        t_df["โซน"] = str(selected_zone).upper().strip()
                        preview_dfs.append(t_df)
                        record_inventory_snapshot(t_df, u_file.name, selected_zone)
                except Exception as e:
                    st.error(f"ไฟล์ {u_file.name} ผิดพลาด: {e}")
            
            if preview_dfs:
                combined_new_df = pd.concat(preview_dfs, ignore_index=True)
                st.info(f"**เตรียมพร้อมบันทึก:** {len(combined_new_df)} รายการ เข้าโซน {selected_zone}")
                
                if st.button(f"💾 ยืนยันบันทึกเข้าโซน {selected_zone}", type="primary"):
                    if st.session_state.current_df.empty:
                        st.session_state.current_df = combined_new_df
                    else:
                        st.session_state.current_df = pd.concat([st.session_state.current_df, combined_new_df], ignore_index=True)
                        st.session_state.current_df["_dedup_key"] = st.session_state.current_df["โซน"].astype(str) + "_" + st.session_state.current_df["รหัสรอง"].astype(str) + "_" + st.session_state.current_df["ชื่อรายการสินค้า"].astype(str).str.strip()
                        st.session_state.current_df.drop_duplicates(subset=["_dedup_key"], keep="last", inplace=True)
                        st.session_state.current_df.drop(columns=["_dedup_key"], inplace=True)
                    
                    save_database(st.session_state.current_df)
                    st.session_state.uploader_key += 1
                    st.success(f"✅ บันทึกข้อมูลเข้าโซน {selected_zone} เรียบร้อย!")
                    st.rerun()

    with st.expander(f"📁 ลบข้อมูลไฟล์ในโซน {selected_zone}", expanded=False):
        df_all = st.session_state.current_df
        if not df_all.empty and "โซน" in df_all.columns and "ชื่อไฟล์ที่มา" in df_all.columns:
            zone_files = df_all[df_all["โซน"].astype(str).str.upper().str.strip() == str(selected_zone).upper().strip()]["ชื่อไฟล์ที่มา"].dropna().unique().tolist()
            if zone_files:
                selected_remove_file = st.selectbox("เลือกไฟล์ที่ต้องการลบ:", options=zone_files)
                if st.button("🗑️ ยืนยันลบไฟล์นี้"):
                    condition = (st.session_state.current_df["ชื่อไฟล์ที่มา"] == selected_remove_file) & (st.session_state.current_df["โซน"].astype(str).str.upper().str.strip() == str(selected_zone).upper().strip())
                    st.session_state.current_df = st.session_state.current_df[~condition]
                    save_database(st.session_state.current_df)
                    st.success(f"ลบข้อมูลสำเร็จ")
                    st.rerun()
            else:
                st.caption(f"ยังไม่มีไฟล์ข้อมูลในโซน {selected_zone}")
        else:
            st.caption("ยังไม่มีข้อมูลในระบบ")

    st.divider()
    # ปุ่มรีเซ็ตล้างฐานข้อมูลทั้งหมด
    with st.expander("⚠️ ล้างฐานข้อมูลระบบทั้งหมด (Reset)", expanded=False):
        st.caption("กดปุ่มนี้เพื่อล้างข้อมูลสินค้าทุกโซนทิ้งทั้งหมด และเริ่มอัปโหลดใหม่ตั้งแต่ต้น")
        if st.button("🔥 ยืนยันล้างข้อมูลทั้งหมด", type="secondary"):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            if os.path.exists(SNAPSHOT_FILE):
                os.remove(SNAPSHOT_FILE)
            st.session_state.current_df = pd.DataFrame()
            st.success("ล้างฐานข้อมูลระบบเรียบร้อยแล้ว!")
            st.rerun()

df_all = st.session_state.current_df
if not df_all.empty and "โซน" in df_all.columns:
    df_zone = df_all[df_all["โซน"].astype(str).str.upper().str.strip() == str(selected_zone).upper().strip()].reset_index(drop=True)
else:
    df_zone = pd.DataFrame()

# ------------------------------------------
# 1. ภาพรวมคลังสินค้า + แผนภูมิ
# ------------------------------------------
if menu == "📊 ภาพรวมคลังสินค้า":
    st.title("📊 ภาพรวมคลังสินค้า (30 โซน)")
    
    if not df_all.empty:
        stock_nums = df_all["คงเหลือ"].apply(parse_numeric_stock) if "คงเหลือ" in df_all.columns else pd.Series([0]*len(df_all))
        status_series = df_all["สถานะ"].astype(str).str.strip() if "สถานะ" in df_all.columns else pd.Series(["พร้อมขาย"]*len(df_all))
        is_discontinued = status_series.str.contains("เลิก|ยกเลิก|หยุดขาย", na=False)
        is_available = ~is_discontinued
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 รายการสินค้าทั้งหมด", f"{len(df_all):,} รายการ")
        c2.metric("✅ สินค้าพร้อมขาย", f"{is_available.sum():,} รายการ")
        c3.metric("⛔ สินค้าเลิกขาย", f"{is_discontinued.sum():,} รายการ")
        c4.metric("⚠️ สต็อกติดลบ", f"{(stock_nums < 0).sum():,} รายการ")

        st.markdown("---")
        st.subheader("📊 แผนภูมิสัดส่วนจำนวนสินค้าในแต่ละโซน (ทั้ง 30 โซน)")
        
        zone_template = pd.DataFrame({"โซน": ALL_ZONES})
        zone_actual_counts = df_all.groupby("โซน")["ชื่อรายการสินค้า"].count().reset_index().rename(columns={"ชื่อรายการสินค้า": "จำนวนสินค้า"})
        zone_summary_30 = pd.merge(zone_template, zone_actual_counts, on="โซน", how="left").fillna(0)
        zone_summary_30["จำนวนสินค้า"] = zone_summary_30["จำนวนสินค้า"].astype(int)
        
        total_items_count = zone_summary_30["จำนวนสินค้า"].sum()
        zone_summary_30["สัดส่วน (%)"] = ((zone_summary_30["จำนวนสินค้า"] / total_items_count * 100).round(2)) if total_items_count > 0 else 0.0

        col_chart1, col_chart2 = st.columns([1.8, 1.2])
        with col_chart1:
            st.markdown("##### 📈 จำนวนสินค้าแยกรายโซน (ครบทั้ง 30 โซน)")
            st.bar_chart(zone_summary_30.set_index("โซน")[["จำนวนสินค้า"]], color="#2563EB", use_container_width=True)
            
        with col_chart2:
            st.markdown("##### 🍩 สัดส่วนเปอร์เซ็นต์ของโซนที่มีสินค้า")
            active_zones = zone_summary_30[zone_summary_30["จำนวนสินค้า"] > 0].copy()
            if not active_zones.empty:
                donut_chart = alt.Chart(active_zones).mark_arc(innerRadius=50).encode(
                    theta=alt.Theta(field="จำนวนสินค้า", type="quantitative"),
                    color=alt.Color(field="โซน", type="nominal", legend=alt.Legend(title="โซนสินค้า")),
                    tooltip=["โซน", "จำนวนสินค้า", alt.Tooltip("สัดส่วน (%):Q", format=".2f")]
                ).properties(height=320)
                st.altair_chart(donut_chart, use_container_width=True)

        st.markdown("---")
        st.subheader("📋 ตารางข้อมูลสินค้าทั้งหมดในระบบ")
        display_all_df = df_all.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
        st.dataframe(display_all_df, use_container_width=True)

        csv_data = display_all_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(label="📥 ดาวน์โหลดข้อมูลทั้งหมด (Cleaned CSV)", data=csv_data, file_name="TKKERP_Cleaned_All.csv", mime="text/csv")
    else:
        st.info("💡 ยังไม่มีข้อมูลสินค้าในระบบ กรุณาเลือกโซนและอัปโหลดไฟล์ที่แถบเมนูด้านซ้าย")

# ------------------------------------------
# 2. จัดการสินค้า (รายโซน)
# ------------------------------------------
elif menu == "📑 จัดการสินค้า (รายโซน)":
    st.title(f"📑 ระบบจัดการสินค้าประจำโซน : {selected_zone}")

    if not df_zone.empty:
        col_t, col_s, col_v = st.columns([1.5, 2, 1.2])
        with col_t:
            tag_list = sorted(list(df_zone["แท็ก {Tag}"].dropna().unique())) if "แท็ก {Tag}" in df_zone.columns else []
            tag_options = ["📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)"] + tag_list
            selected_tag = st.selectbox("🏷️ เลือกแท็กสินค้า:", options=tag_options)

        with col_s:
            stock_ranges = ["ทั้งหมด", "-1000 ถึง 0", "1-10", "10-20", "20-30", "30-40", "40-50", "50-100", "100-200"]
            selected_range = st.select_slider("🔢 เลือกช่วงจำนวนสต็อกคงเหลือ:", options=stock_ranges, value="ทั้งหมด")
        
        with col_v:
            display_type = st.radio("รูปแบบการแสดงผล:", ["🖼️ รูปภาพสินค้า (Cards)", "📋 ตารางข้อมูล (Table)"], horizontal=True)

        base_df = df_zone.copy() if selected_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)" else df_zone[df_zone["แท็ก {Tag}"] == selected_tag].copy()
        numeric_stocks = base_df["คงเหลือ"].apply(parse_numeric_stock)

        if selected_range == "-1000 ถึง 0":
            mask = (numeric_stocks >= -1000) & (numeric_stocks <= 0)
            filtered_df = base_df[mask].copy()
            filtered_df["_sort_num"] = filtered_df["คงเหลือ"].apply(parse_numeric_stock)
            filtered_df = filtered_df.sort_values(by="_sort_num", ascending=True).drop(columns=["_sort_num"])
        elif selected_range == "1-10":
            filtered_df = base_df[(numeric_stocks >= 1) & (numeric_stocks <= 10)]
        elif selected_range == "10-20":
            filtered_df = base_df[(numeric_stocks > 10) & (numeric_stocks <= 20)]
        elif selected_range == "20-30":
            filtered_df = base_df[(numeric_stocks > 20) & (numeric_stocks <= 30)]
        elif selected_range == "30-40":
            filtered_df = base_df[(numeric_stocks > 30) & (numeric_stocks <= 40)]
        elif selected_range == "40-50":
            filtered_df = base_df[(numeric_stocks > 40) & (numeric_stocks <= 50)]
        elif selected_range == "50-100":
            filtered_df = base_df[(numeric_stocks > 50) & (numeric_stocks <= 100)]
        elif selected_range == "100-200":
            filtered_df = base_df[(numeric_stocks > 100) & (numeric_stocks <= 200)]
        else:
            filtered_df = base_df.copy()

        filtered_df = filtered_df.reset_index(drop=True)

        st.markdown("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📍 โซนที่เลือก", f"โซน {selected_zone}")
        m2.metric("🏷️ แท็กที่เลือก", "รวมทุกแท็ก" if selected_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)" else selected_tag)
        m3.metric("🎯 เงื่อนไขสต็อก", selected_range)
        m4.metric("📦 พบสินค้า", f"{len(filtered_df):,} รายการ")

        if not filtered_df.empty:
            if display_type == "🖼️ รูปภาพสินค้า (Cards)":
                if selected_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)":
                    present_tags = sorted(list(filtered_df["แท็ก {Tag}"].dropna().unique()))
                    for tag in present_tags:
                        group_df = filtered_df[filtered_df["แท็ก {Tag}"] == tag].reset_index(drop=True)
                        with st.expander(f"📦 แท็ก: **{tag}** (พบ **{len(group_df)}** รายการ)", expanded=True):
                            render_product_cards(group_df, selected_zone)
                else:
                    render_product_cards(filtered_df, selected_zone)
            else:
                def highlight_neg(val):
                    try:
                        num = float(str(val).replace(":", ""))
                        if num < 0: return "background-color: #ffebee; color: #c62828; font-weight: bold;"
                        elif num == 0: return "background-color: #fffde7; color: #f57f17; font-weight: bold;"
                        return ""
                    except Exception: return ""

                try:
                    styled_df = filtered_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore").style.map(highlight_neg, subset=["คงเหลือ"])
                except AttributeError:
                    styled_df = filtered_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore").style.applymap(highlight_neg, subset=["คงเหลือ"])
                st.dataframe(styled_df, use_container_width=True)

            st.divider()
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                filtered_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore").to_excel(writer, sheet_name=f"โซน_{selected_zone}", index=False)
            st.download_button(label=f"📥 ดาวน์โหลดไฟล์ Excel โซน {selected_zone} (.xlsx)", data=output.getvalue(), file_name=f"ข้อมูลสินค้า_โซน_{selected_zone}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning(f"ℹ️ ไม่พบรายการสินค้าในโซน {selected_zone} ที่ตรงกับเงื่อนไขสต็อก")
    else:
        st.info(f"👈 โซน **{selected_zone}** ยังไม่มีข้อมูลสินค้า คลิกที่เมนูด้านซ้ายเพื่ออัปโหลด")

# ------------------------------------------
# 3. สินค้าที่มีปัญหา (คงเหลือติดลบ)
# ------------------------------------------
elif menu == "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)":
    st.title(f"⚠️ สินค้าที่มีปัญหา [คงเหลือติดลบ -] : โซน {selected_zone}")
    
    if not df_zone.empty and "คงเหลือ" in df_zone.columns:
        numeric_stocks = df_zone["คงเหลือ"].apply(parse_numeric_stock)
        problem_df = df_zone[numeric_stocks < 0].copy()
        problem_df["_sort_num"] = problem_df["คงเหลือ"].apply(parse_numeric_stock)
        problem_df = problem_df.sort_values(by="_sort_num", ascending=True).drop(columns=["_sort_num"]).reset_index(drop=True)
        
        if not problem_df.empty:
            st.error(f"🚨 พบสินค้าคงเหลือติดลบทั้งหมด **{len(problem_df)} รายการ** ในโซน {selected_zone}")
            prob_tags = sorted(list(problem_df["แท็ก {Tag}"].dropna().unique()))
            selected_prob_tag = st.selectbox("🏷️ เลือกกลุ่มแท็กสินค้าที่มีปัญหา:", options=["📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)"] + prob_tags)
            
            if selected_prob_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)":
                for tag in prob_tags:
                    group_prob_df = problem_df[problem_df["แท็ก {Tag}"] == tag].reset_index(drop=True)
                    with st.expander(f"🚨 แท็ก: **{tag}** (รวม **{len(group_prob_df)}** รายการ)", expanded=True):
                        render_product_cards(group_prob_df, selected_zone, is_problem=True)
            else:
                filtered_prob_df = problem_df[problem_df["แท็ก {Tag}"] == selected_prob_tag].reset_index(drop=True)
                st.write(f"พบ **{len(filtered_prob_df)} รายการ** ที่ติดลบ ในแท็ก `{selected_prob_tag}`")
                render_product_cards(filtered_prob_df, selected_zone, is_problem=True)

            st.divider()
            st.subheader(f"📋 ตารางรายการสินค้าที่มีปัญหา [โซน {selected_zone}]")
            st.dataframe(problem_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore"), use_container_width=True)
        else:
            st.success(f"🎉 ยอดเยี่ยม! ไม่พบสินค้าคงเหลือติดลบในโซน {selected_zone}")
    else:
        st.info(f"👈 โซน {selected_zone} ยังไม่มีข้อมูลสินค้า")

# ------------------------------------------
# 4. สรุปรายงานรายเดือน
# ------------------------------------------
elif menu == "📈 สรุปรายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง)":
    st.title("📈 สรุปรายงานรายเดือน: วิเคราะห์การเปลี่ยนแปลงสต็อกแยกตามแท็กและโซน")
    df_snaps = load_snapshots()
    
    if not df_snaps.empty:
        months_available = sorted(list(df_snaps["month_year"].dropna().unique()), reverse=True)
        c_m, c_z = st.columns([1.5, 1.5])
        with c_m: selected_month = st.selectbox("📅 เลือกเดือนที่ต้องการวิเคราะห์:", options=months_available)
        with c_z: selected_rep_zone = st.selectbox("📍 เลือกโซนที่ต้องการดูการเปลี่ยนแปลง:", options=["📌 รวมทุกโซน (30 โซน)"] + ALL_ZONES)
            
        cur_month_df = df_snaps[df_snaps["month_year"] == selected_month].copy()
        if selected_rep_zone != "📌 รวมทุกโซน (30 โซน)":
            cur_month_df = cur_month_df[cur_month_df["zone"] == selected_rep_zone]

        if not cur_month_df.empty:
            grouped_items = []
            for (z_val, name_key), g in cur_month_df.groupby(["zone", "product_name"]):
                g_sorted = g.sort_values(by="timestamp")
                first_row = g_sorted.iloc[0]
                last_row = g_sorted.iloc[-1]
                delta_stock = last_row["stock"] - first_row["stock"]
                status_change = "คงที่"
                if len(g_sorted) == 1: status_change = "🆕 นำเข้าใหม่"
                elif delta_stock > 0: status_change = f"🟢 เพิ่มขึ้น (+{delta_stock:g})"
                elif delta_stock < 0: status_change = f"🔴 ลดลง ({delta_stock:g})"
                if last_row["stock"] < 0: status_change += " [🚨 ติดลบ]"
                
                grouped_items.append({
                    "โซน": z_val, "รหัสสินค้า": last_row["barcode"], "รหัสรอง": last_row["sub_code"],
                    "ชื่อรายการสินค้า": name_key, "แท็ก {Tag}": last_row["tag"],
                    "สต็อกเริ่มต้นเดือน": first_row["stock"], "สต็อกล่าสุด": last_row["stock"],
                    "ผลต่างการเปลี่ยนแปลง": delta_stock, "สถานะการเคลื่อนไหว": status_change
                })
            items_change_df = pd.DataFrame(grouped_items)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📦 สินค้าที่มีการบันทึก", f"{len(items_change_df):,} รายการ")
            c2.metric("🟢 สินค้าที่สต็อกเพิ่ม", f"{len(items_change_df[items_change_df['ผลต่างการเปลี่ยนแปลง'] > 0]):,} รายการ")
            c3.metric("🔴 สินค้าที่สต็อกลดลง", f"{len(items_change_df[items_change_df['ผลต่างการเปลี่ยนแปลง'] < 0]):,} รายการ")
            c4.metric("📊 สต็อกสุทธิเคลื่อนไหว", f"{items_change_df['ผลต่างการเปลี่ยนแปลง'].sum():+,.0f} ชิ้น")

            st.markdown("---")
            st.dataframe(items_change_df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"ℹ️ ไม่พบข้อมูลการอัปโหลดในเดือน {selected_month}")
    else:
        st.info("💡 ยังไม่มีประวัติการอัปโหลดไฟล์ในระบบ")

# ------------------------------------------
# 5. ค้นหาสินค้า & Tag
# ------------------------------------------
elif menu == "🔍 ค้นหาสินค้า & Tag":
    st.title("🔍 ค้นหาและจัดกลุ่มสินค้าตาม Tag / รหัส")
    search_kw = st.text_input("🔎 ค้นหาด้วย ชื่อสินค้า / บาร์โค้ด / รหัสรอง / Tag / โซน:", "")

    if search_kw and not df_all.empty:
        mask = (
            df_all["ชื่อรายการสินค้า"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["รหัสสินค้า"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["รหัสรอง"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["แท็ก {Tag}"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["โซน"].astype(str).str.contains(search_kw, case=False, na=False)
        )
        res_df = df_all[mask].reset_index(drop=True)
        st.write(f"ผลการค้นหา: พบ **{len(res_df)}** รายการ")
        
        view_res_type = st.radio("เลือกมุมมองผลการค้นหา:", ["🖼️ แสดงรูปภาพ (Cards)", "📋 ตารางข้อมูล (Table)"], horizontal=True)
        if view_res_type == "🖼️ แสดงรูปภาพ (Cards)":
            render_product_cards(res_df, "หลายโซน")
        else:
            st.dataframe(res_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore"), use_container_width=True)# --- ระบบล็อกอินป้องกันคนนอกเข้าดู ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "1234":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 ระบบจัดการคลังสินค้า")
        st.text_input("กรุณาใส่รหัสผ่านเพื่อเข้าใช้งาน:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 ระบบจัดการคลังสินค้า")
        st.text_input("กรุณาใส่รหัสผ่านเพื่อเข้าใช้งาน:", type="password", on_change=password_entered, key="password")
        st.error("❌ รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง")
        return False
    else:
        return True

if not check_password():
    st.stop()
# ------------------------------------
