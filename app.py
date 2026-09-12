import io
import math
import os
import re
import pandas as pd
from pypdf import PdfReader
import streamlit as st

st.set_page_config(
    page_title="TKK ERP - จัดการคลังและโซนสินค้า", 
    page_icon="📦",
    layout="wide"
)

# ==========================================
# 🔑 กำหนดรหัสผ่าน
# ==========================================
APP_PASSWORD = "1234"         # รหัสผ่านเข้าใช้งานทั่วไป
ADMIN_PASSWORD = "admin8888"   # รหัสผ่านปลดล็อกโหมด Admin

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

def check_password():
    if not st.session_state.authenticated:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1.2, 1])
        with col2:
            with st.container(border=True):
                st.markdown("<h2 style='text-align: center;'>🔒 เข้าสู่ระบบ</h2>", unsafe_allow_html=True)
                st.caption("<div style='text-align: center; margin-bottom: 12px;'>ระบบจัดการคลังและโซนสินค้า TKK ERP</div>", unsafe_allow_html=True)
                pwd = st.text_input("กรุณากรอกรหัสผ่าน (Password):", type="password")
                if st.button("เข้าสู่ระบบ 🚀", type="primary", use_container_width=True):
                    if pwd == APP_PASSWORD:
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("❌ รหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง")
        return False
    return True

if not check_password():
    st.stop()

# ==========================================
# 🎨 ตกแต่ง CSS
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Sarabun', sans-serif;
    }
    
    button[aria-label="Delete"] { display: none !important; }
    div[data-testid="stFileUploaderDeleteBtn"] { display: none !important; }

    div[data-testid="stRadio"] > div {
        gap: 10px !important;
    }
    div[data-testid="stRadio"] label {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        margin-bottom: 2px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03) !important;
        transition: all 0.25s ease-in-out !important;
        cursor: pointer !important;
    }
    div[data-testid="stRadio"] label:hover {
        background: #f1f5f9 !important;
        border-color: #94a3b8 !important;
        transform: translateX(4px) !important;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%) !important;
        border: 1.5px solid #2563eb !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15) !important;
    }
    div[data-testid="stRadio"] label:has(input:checked) p {
        color: #1d4ed8 !important;
        font-weight: 700 !important;
    }
    
    .kpi-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border-radius: 14px;
        padding: 18px 22px;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
        border: 1px solid #e2e8f0;
        text-align: left;
        margin-bottom: 12px;
    }
    .kpi-title {
        font-size: 14px;
        font-weight: 600;
        color: #64748b;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .kpi-value {
        font-size: 30px;
        font-weight: 700;
        line-height: 1.2;
    }
    .kpi-sub {
        font-size: 12px;
        color: #94a3b8;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🚀 ตัวแปรและฟังก์ชันระบบคลังสินค้า
# ==========================================
DB_FILE = "database_inventory.csv"
NO_IMAGE_PLACEHOLDER = "https://placehold.co/400x400/f8fafc/94a3b8?text=No+Image"
ITEMS_PER_PAGE = 48

ALL_ZONES = [
    "AA", "AB", "BB", "CC", "DD", "EE", "FF", "GG", 
    "IA", "IB", "IC", "JJ", "KK", "LL", "MA", "MB", 
    "MC", "MM", "NN", "PP", "QQ", "RR", "ST", "TT", 
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
    df.to_csv(DB_FILE, index=False, encoding="utf-8-sig")

def extract_fields_from_text(text, source_name, target_zone):
    pattern = re.compile(
        r'(\d{4,5})\s+รหัส\s*:\s*(\d+)\s*รหัสรอง\s*:\s*(\d+)[•\s\-]*(.*?)(?:\{([^}]+)\})?\s*หน่วยนับ\s*:\s*([^คง]+)คงเหลือ\s*:\s*([\-\d\.]+)\s*(เลิกขาย|ขาย)?\s*(\d+)\s*โซน\s*:\s*([A-Za-z0-9]+)',
        re.DOTALL
    )
    matches = pattern.findall(text)
    data = []
    for m in matches:
        raw_tag = m[4].strip() if m[4] else ""
        extracted_zone = m[9].strip() if m[9] else target_zone
        barcode = str(m[1]).strip()
        data.append({
            "#": m[0],
            "รหัสสินค้า": barcode,
            "รหัสรอง": str(m[2]).strip(),
            "ชื่อรายการสินค้า": m[3].strip(),
            "แท็ก {Tag}": f"{{{raw_tag}}}" if raw_tag else "{ทั่วไป}",
            "หน่วยนับ": m[5].strip(),
            "จำนวนสั่งล่าสุด": str(int(m[8])) if m[8].isdigit() else "0",
            "โซน": extracted_zone,
            "คงเหลือ": str(m[6]).strip() if m[6] else "0",
            "สถานะ": m[7] if m[7] else "ปกติ",
            "ชื่อไฟล์ที่มา": source_name
        })
    return pd.DataFrame(data)

def clean_and_prepare_df(raw_df, source_name, default_zone):
    df = raw_df.copy()
    
    # ดึงรหัสสินค้า
    for col in df.columns:
        c_str = str(col).strip()
        if "รหัสสินค้า" in c_str or c_str == "รหัส" or "barcode" in c_str.lower():
            df["รหัสสินค้า"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if "รหัสรอง" in c_str or "sub" in c_str.lower():
            df["รหัสรอง"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    # ดึงชื่อสินค้า
    name_col = next(
        (c for c in df.columns if "ชื่อรายการสินค้า" in str(c) or "ชื่อ" in str(c) or "รายละ" in str(c)),
        None
    )
    if name_col:
        df["ชื่อรายการสินค้า"] = df[name_col].astype(str).apply(lambda x: re.sub(r'\{[^}]+\}', '', str(x)).replace("•", "").strip())
    elif "ชื่อรายการสินค้า" not in df.columns:
        df["ชื่อรายการสินค้า"] = "-"

    # ดึงแท็ก Tag
    tag_col = next((c for c in df.columns if "แท็ก" in str(c) and "ชื่อ" not in str(c)), None)
    if tag_col:
        df["แท็ก {Tag}"] = df[tag_col].fillna("{ทั่วไป}").astype(str).str.strip()
    elif name_col:
        def get_tag(x):
            m = re.search(r'\{([^}]+)\}', str(x))
            return f"{{{m.group(1).strip()}}}" if m else "{ทั่วไป}"
        df["แท็ก {Tag}"] = df[name_col].astype(str).apply(get_tag)
    else:
        df["แท็ก {Tag}"] = "{ทั่วไป}"

    # ดึงจำนวน / คงเหลือ
    qty_col = next((c for c in df.columns if any(k in str(c) for k in ["คงเหลือ", "จำนวน", "ยอด", "qty", "quantity"])), None)
    if qty_col:
        df["คงเหลือ"] = df[qty_col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    elif "คงเหลือ" not in df.columns:
        df["คงเหลือ"] = "0"

    # ดึงโซน (หากในไฟล์มีคอลัมน์โซน ให้ใช้โซนจากไฟล์ ถ้าไม่มีให้ใช้ default_zone)
    zone_col = next((c for c in df.columns if "โซน" in str(c) or "zone" in str(c).lower()), None)
    if zone_col:
        df["โซน"] = df[zone_col].fillna(default_zone).astype(str).str.upper().str.strip()
    else:
        df["โซน"] = default_zone

    df["ชื่อไฟล์ที่มา"] = source_name
    standard_cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}", "หน่วยนับ", "จำนวนสั่งล่าสุด", "โซน", "คงเหลือ", "สถานะ", "ชื่อไฟล์ที่มา"]
    for sc in standard_cols:
        if sc not in df.columns:
            df[sc] = "-"
            
    return df[standard_cols]

def process_inventory_transactions(master_df, incoming_df, action_type):
    """
    ประมวลผลการคำนวณสต็อก:
    - action_type == 'ADD': รับเข้าสินค้า (+ สต็อก)
    - action_type == 'SUB': ขายสินค้าออก (- สต็อก)
    - action_type == 'SET': อัปเดตทับ / ตั้งต้นสต็อก
    """
    if master_df.empty:
        return incoming_df

    master = master_df.copy()
    
    # ทำ mapping ดัชนีด้วยรหัสสินค้า
    master["รหัสสินค้า"] = master["รหัสสินค้า"].astype(str).str.strip()
    incoming = incoming_df.copy()
    incoming["รหัสสินค้า"] = incoming["รหัสสินค้า"].astype(str).str.strip()
    
    master_indexed = master.set_index("รหัสสินค้า")
    
    for idx, row in incoming.iterrows():
        bcode = row["รหัสสินค้า"]
        if not bcode or bcode == "-" or bcode == "nan":
            continue
            
        qty_in = pd.to_numeric(row.get("คงเหลือ", 0), errors="coerce")
        qty_in = 0 if pd.isna(qty_in) else qty_in
        
        if bcode in master_indexed.index:
            # มีสินค้าเดิมในระบบ
            curr_stock = pd.to_numeric(master_indexed.at[bcode, "คงเหลือ"], errors="coerce")
            curr_stock = 0 if pd.isna(curr_stock) else curr_stock
            
            if action_type == "ADD":
                new_stock = curr_stock + qty_in
            elif action_type == "SUB":
                new_stock = curr_stock - qty_in
            else:  # SET
                new_stock = qty_in
                
            master_indexed.at[bcode, "คงเหลือ"] = str(int(new_stock) if new_stock == int(new_stock) else round(new_stock, 2))
            
            # อัปเดตโซนและข้อมูลรายการหากมีระบุมาใหม่
            if row["โซน"] and row["โซน"] != "-":
                master_indexed.at[bcode, "โซน"] = row["โซน"]
            if row["ชื่อรายการสินค้า"] and row["ชื่อรายการสินค้า"] != "-":
                master_indexed.at[bcode, "ชื่อรายการสินค้า"] = row["ชื่อรายการสินค้า"]
            if row["แท็ก {Tag}"] and row["แท็ก {Tag}"] != "{ทั่วไป}":
                master_indexed.at[bcode, "แท็ก {Tag}"] = row["แท็ก {Tag}"]
        else:
            # สินค้าใหม่
            new_row = row.copy()
            if action_type == "SUB":
                new_row["คงเหลือ"] = str(-qty_in)
            master_indexed.loc[bcode] = new_row
            
    updated_master = master_indexed.reset_index()
    return updated_master

def render_product_cards(items_df, current_zone):
    cols = st.columns(4)
    for idx, row in items_df.iterrows():
        raw_barcode = str(row.get("รหัสสินค้า", "")).replace(".0", "").strip()
        barcode = re.sub(r'[^0-9A-Za-z\-_]', '', raw_barcode)
        
        raw_sub = str(row.get("รหัสรอง", "")).replace(".0", "").strip()
        sub_code = re.sub(r'[^0-9A-Za-z\-_]', '', raw_sub)
        
        name = str(row.get("ชื่อรายการสินค้า", "")).strip()
        if not name or name.lower() == "nan":
            name = str(row.get("แท็ก • ชื่อรายการสินค้า", "-")).strip()
            
        stock = str(row.get("คงเหลือ", "0")).replace(".0", "")
        
        code_for_img = barcode if (barcode and len(barcode) >= 5) else sub_code
        img_url = f"https://tkkonlineshop.com/images/products/{code_for_img}.jpg"
        
        with cols[idx % 4]:
            with st.container(border=True):
                st.markdown(f"""
                <div style="text-align: center; margin-bottom: 10px;">
                    <img src="{img_url}" 
                         onerror="this.onerror=null; this.src='{NO_IMAGE_PLACEHOLDER}';" 
                         loading="lazy"
                         style="width: 100%; aspect-ratio: 1/1; object-fit: contain; border-radius: 12px; background: #fff; box-shadow: 0 2px 6px rgba(0,0,0,0.06);" />
                </div>
                <div style="text-align: center; height: 44px; overflow: hidden; font-size: 13px; font-weight: 600; color: #1e293b; line-height: 1.4; margin-bottom: 6px;">
                    • {name}
                </div>
                <div style="text-align: center; font-size: 12px; color: #64748b; line-height: 1.6; margin-bottom: 6px;">
                    <div>รหัสสินค้า: <span style="color: #334155; font-weight: 600;">{barcode if barcode else '-'}</span></div>
                    <div>รหัสรอง: <b style="color: #2563eb;">{sub_code if sub_code else '-'}</b></div>
                    <div>คงเหลือ : <b style="font-size: 14px; color: {'#dc2626' if ('-' in stock or stock == '0') else '#059669'};">{stock}</b></div>
                </div>
                """, unsafe_allow_html=True)

if "current_df" not in st.session_state:
    st.session_state.current_df = load_database()
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- เมนูด้านข้าง (Sidebar) ---
with st.sidebar:
    st.markdown("""
        <div style="font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 8px;">
            📦 การจัดการสต็อก
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚪 ออกจากระบบ (Logout)", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.admin_authenticated = False
        st.rerun()
        
    st.divider()
    
    # 1. ฟังก์ชันการทำงาน
    st.markdown("""
        <div style="font-size: 18px; font-weight: 800; color: #1e293b; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; border-left: 4px solid #2563eb; padding-left: 8px;">
            🧭 ฟังก์ชันการทำงาน
        </div>
    """, unsafe_allow_html=True)
    
    selected_menu = st.radio(
        "เลือกฟังก์ชัน:",
        options=[
            "📦 จัดการสินค้า (รายโซน)",
            "⚠️ สินค้ามีปัญหา (สต็อกติดลบ)",
            "📊 สต็อกสินค้า 0 ถึง 3000",
            "📈 สรุปสายงานรายเดือน",
            "🔍 ค้นหาสินค้า & Tag"
        ],
        index=0,
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # 2. โซนสินค้า (30 โซน)
    st.markdown("""
        <div style="font-size: 18px; font-weight: 800; color: #1e293b; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; border-left: 4px solid #10b981; padding-left: 8px;">
            📍 โซนสินค้า (30 โซน)
        </div>
    """, unsafe_allow_html=True)
    selected_zone = st.selectbox("เลือกโซนที่ต้องการเข้าดู:", options=ALL_ZONES, index=0)
    
    st.divider()
    
    # 3. โหมดจัดการข้อมูล (Admin)
    st.markdown("""
        <div style="font-size: 18px; font-weight: 800; color: #1e293b; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; border-left: 4px solid #f59e0b; padding-left: 8px;">
            ⚙️ โหมดจัดการข้อมูล (Admin)
        </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.admin_authenticated:
        with st.expander("🔒 ปลดล็อกระบบจัดการ (Admin Only)", expanded=False):
            admin_pwd = st.text_input("กรอกรหัสผ่าน Admin:", type="password", key="admin_pwd_input")
            if st.button("ยืนยันปลดล็อก 🔓", use_container_width=True):
                if admin_pwd == ADMIN_PASSWORD:
                    st.session_state.admin_authenticated = True
                    st.success("ปลดล็อกโหมด Admin สำเร็จ!")
                    st.rerun()
                else:
                    st.error("❌ รหัสผ่าน Admin ไม่ถูกต้อง")
    else:
        st.success("🟢 โหมด Admin เปิดใช้งานอยู่")
        if st.button("🔒 ปิดโหมด Admin", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()
            
        with st.expander("📥 อัปโหลดเอกสาร / จัดการธุรกรรมสต็อก", expanded=True):
            # เลือกประเภทของเอกสารที่นำเข้า
            trans_type = st.selectbox(
                "ประเภทเอกสารที่นำเข้า:",
                options=[
                    "📥 รับเข้าสินค้า (+ บวกสต็อกเพิ่ม)",
                    "📤 รายการขายสินค้า (- หักลบสต็อกออก)",
                    "📋 อัปเดตข้อมูล Master (ตั้งต้นสต็อก)"
                ]
            )
            
            st.caption("💡 ไฟล์ Excel/CSV สามารถรวมรายการสินค้าหลายโซนได้ ระบบจะคัดแยกเข้าโซนให้อัตโนมัติ")
            
            uploaded_files = st.file_uploader(
                "เลือกไฟล์เอกสาร (PDF, CSV, XLSX)", 
                type=["pdf", "csv", "xlsx"], 
                accept_multiple_files=True,
                key=f"uploader_{st.session_state.uploader_key}"
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
                        elif u_file.name.endswith(".xlsx"):
                            t_df = clean_and_prepare_df(pd.read_excel(u_file), u_file.name, selected_zone)
                        
                        if not t_df.empty:
                            preview_dfs.append(t_df)
                    except Exception as e:
                        st.error(f"ไฟล์ {u_file.name} มีปัญหา: {e}")
                
                if preview_dfs:
                    combined_incoming = pd.concat(preview_dfs, ignore_index=True)
                    st.info(f"📄 พบข้อมูลที่พร้อมประมวลผล: {len(combined_incoming):,} รายการ")
                    
                    if st.button("⚡ บันทึกและคำนวณสต็อกอัตโนมัติ", type="primary", use_container_width=True):
                        action_code = "ADD" if "รับเข้า" in trans_type else ("SUB" if "ขาย" in trans_type else "SET")
                        
                        st.session_state.current_df = process_inventory_transactions(
                            st.session_state.current_df, 
                            combined_incoming, 
                            action_code
                        )
                        
                        save_database(st.session_state.current_df)
                        st.session_state.uploader_key += 1
                        st.success("ประมวลผลและอัปเดตสต็อก 30 โซนสำเร็จเรียบร้อย!")
                        st.rerun()

        with st.expander(f"📁 ลบข้อมูลไฟล์ในโซน {selected_zone}", expanded=False):
            df_all = st.session_state.current_df
            if not df_all.empty and "โซน" in df_all.columns:
                filter_cond = (df_all["โซน"] == selected_zone)
                zone_files = df_all[filter_cond]["ชื่อไฟล์ที่มา"].dropna().unique().tolist()
                if zone_files:
                    selected_remove_file = st.selectbox("เลือกไฟล์ที่ต้องการลบ:", options=zone_files)
                    if st.button("🗑️ ยืนยันลบไฟล์", use_container_width=True):
                        del_cond = (st.session_state.current_df["ชื่อไฟล์ที่มา"] == selected_remove_file) & (st.session_state.current_df["โซน"] == selected_zone)
                        st.session_state.current_df = st.session_state.current_df[~del_cond]
                        save_database(st.session_state.current_df)
                        st.success("ลบข้อมูลสำเร็จ")
                        st.rerun()

        if not st.session_state.current_df.empty:
            st.divider()
            output_backup = io.BytesIO()
            st.session_state.current_df.to_csv(output_backup, index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 สำรองฐานข้อมูลรวม 30 โซน (Backup CSV)",
                data=output_backup.getvalue(),
                file_name="database_master_30zones.csv",
                mime="text/csv",
                use_container_width=True
            )

df_all = st.session_state.current_df

# --- 1. หน้าจัดการสินค้า (รายโซน) ---
if "จัดการสินค้า" in selected_menu:
    if not df_all.empty and "โซน" in df_all.columns:
        df_zone = df_all[df_all["โซน"] == selected_zone].reset_index(drop=True)
    else:
        df_zone = pd.DataFrame()

    st.markdown(f"## 📍 รายการสต็อกสินค้า [โซน {selected_zone}]")

    top_c1, top_c2, top_c3, top_c4 = st.columns(4)
    with top_c1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">📌 รหัสโซน</div><div class="kpi-value" style="color:#2563eb;">{selected_zone}</div></div>""", unsafe_allow_html=True)
    with top_c2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">🏷️ กลุ่มแท็ก</div><div class="kpi-value" style="color:#0f172a;">รวมทุกแท็ก</div></div>""", unsafe_allow_html=True)
    with top_c3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">📊 สถานะ</div><div class="kpi-value" style="color:#059669;">ทั้งหมด</div></div>""", unsafe_allow_html=True)
    with top_c4:
        total_items = len(df_zone)
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">📦 จำนวนรวม</div><div class="kpi-value" style="color:#ea580c;">{total_items:,} <span style="font-size:16px;">รายการ</span></div></div>""", unsafe_allow_html=True)

    st.divider()

    if not df_zone.empty:
        unique_tags = sorted(list(df_zone["แท็ก {Tag}"].dropna().unique()))
        selected_tag = st.selectbox("🔍 เลือกกลุ่มแท็กเพื่อดูสินค้า:", options=["แสดงทุกกลุ่มแท็ก"] + unique_tags)
        
        if selected_tag == "แสดงทุกกลุ่มแท็ก":
            active_items_df = df_zone.copy()
        else:
            active_items_df = df_zone[df_zone["แท็ก {Tag}"] == selected_tag].reset_index(drop=True)
        
        total_count = len(active_items_df)
        total_pages = max(1, math.ceil(total_count / ITEMS_PER_PAGE))
        
        p_col1, p_col2 = st.columns([3, 1])
        with p_col1:
            st.markdown(f"📦 จำนวนสินค้าที่แสดง: **{total_count:,}** รายการ")
        with p_col2:
            current_page = st.number_input(f"หน้าแสดงผล (จาก {total_pages} หน้า):", min_value=1, max_value=total_pages, value=1, step=1)
        
        start_idx = (current_page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_df = active_items_df.iloc[start_idx:end_idx].reset_index(drop=True)
        
        with st.container():
            render_product_cards(page_df, selected_zone)

        st.divider()

        if selected_tag == "แสดงทุกกลุ่มแท็ก":
            table_title = f"📋 ตารางข้อมูลทั้งหมด [โซน {selected_zone}]"
            file_suffix = f"โซน_{selected_zone}_ทั้งหมด"
        else:
            clean_tag_name = re.sub(r'[\{\}]', '', selected_tag)
            table_title = f"📋 ตารางข้อมูลแท็ก {selected_tag} [โซน {selected_zone}]"
            file_suffix = f"โซน_{selected_zone}_แท็ก_{clean_tag_name}"

        st.subheader(table_title)
        display_df = active_items_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
        st.dataframe(display_df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            display_df.to_excel(writer, sheet_name=f"Zone_{selected_zone}"[:31], index=False)
        
        st.download_button(
            label=f"📥 ดาวน์โหลด Excel โซน {selected_zone}",
            data=output.getvalue(),
            file_name=f"ข้อมูล_{file_suffix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info(f"👈 โซน {selected_zone} ยังไม่มีข้อมูล สามารถอัปโหลดไฟล์ที่แถบซ้ายมือได้เลยครับ")

# --- 2. หน้าสินค้าที่มีปัญหา (คงเหลือติดลบ) ---
elif "ติดลบ" in selected_menu:
    st.markdown("## ⚠️ สินค้าที่มีปัญหา (ยอดคงเหลือติดลบ)")
    
    if not df_all.empty and "คงเหลือ" in df_all.columns:
        stock_series = pd.to_numeric(df_all["คงเหลือ"], errors="coerce")
        df_negative = df_all[stock_series < 0].reset_index(drop=True)
        
        if not df_negative.empty:
            st.error(f"🚨 ตรวจพบสินค้าติดลบทั้งหมด {len(df_negative):,} รายการทั่วทั้งระบบ")
            
            unique_neg_tags = sorted(list(df_negative["แท็ก {Tag}"].dropna().unique()))
            selected_neg_tag = st.selectbox(
                "🏷️ กรองดูตามกลุ่มแท็กสินค้าติดลบ:", 
                options=["แสดงทุกกลุ่มแท็ก"] + unique_neg_tags
            )
            
            if selected_neg_tag == "แสดงทุกกลุ่มแท็ก":
                active_neg_df = df_negative.copy()
                report_title = "รายงานสินค้าติดลบทั้งหมด"
                file_name_suffix = "ทั้งหมด"
            else:
                active_neg_df = df_negative[df_negative["แท็ก {Tag}"] == selected_neg_tag].reset_index(drop=True)
                clean_tag = re.sub(r'[\{\}]', '', selected_neg_tag)
                report_title = f"รายงานสินค้าติดลบ แท็ก {selected_neg_tag}"
                file_name_suffix = f"แท็ก_{clean_tag}"

            st.markdown(f"#### 📋 ตารางข้อมูล: {report_title} ({len(active_neg_df):,} รายการ)")
            display_neg_df = active_neg_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
            
            output_neg = io.BytesIO()
            with pd.ExcelWriter(output_neg, engine="openpyxl") as writer:
                clean_sheet_name = re.sub(r'[\/\\\?\*\[\]\:]', '_', file_name_suffix)[:31]
                display_neg_df.to_excel(writer, sheet_name=clean_sheet_name, index=False)
            
            st.download_button(
                label=f"📥 ดาวน์โหลดไฟล์ Excel ({report_title})",
                data=output_neg.getvalue(),
                file_name=f"รายงานสินค้าติดลบ_{file_name_suffix}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="btn_download_neg_excel"
            )
            
            st.dataframe(display_neg_df, use_container_width=True)

            st.divider()

            st.markdown("##### 🖼️ รายการการ์ดรูปภาพสินค้าติดลบ")
            total_neg_count = len(active_neg_df)
            total_neg_pages = max(1, math.ceil(total_neg_count / ITEMS_PER_PAGE))
            
            p_col1, p_col2 = st.columns([3, 1])
            with p_col1:
                st.caption(f"แสดงตัวอย่างหน้าละ {ITEMS_PER_PAGE} รายการ")
            with p_col2:
                current_neg_page = st.number_input(
                    f"หน้าแสดงผล (จาก {total_neg_pages} หน้า):", 
                    min_value=1, 
                    max_value=total_neg_pages, 
                    value=1, 
                    step=1,
                    key="neg_page_input"
                )
            
            start_neg_idx = (current_neg_page - 1) * ITEMS_PER_PAGE
            end_neg_idx = start_neg_idx + ITEMS_PER_PAGE
            page_neg_df = active_neg_df.iloc[start_neg_idx:end_neg_idx].reset_index(drop=True)

            with st.container():
                render_product_cards(page_neg_df, "สินค้าติดลบ")
        else:
            st.success("🎉 ยอดเยี่ยมมาก! ไม่พบสินค้าที่มียอดคงเหลือติดลบในระบบ")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

# --- 3. หน้าสินค้าสต็อก 0 ถึง 3000 ---
elif "0 ถึง 3000" in selected_menu:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
            <h1 style="font-size: 28px; font-weight: 700; margin: 0; color: #0f172a;">📊 แดชบอร์ดวิเคราะห์และรายงานสต็อก (0 ถึง 3,000)</h1>
        </div>
        <p style="color: #64748b; font-size: 14px; margin-bottom: 20px;">ระบบวิเคราะห์การกระจายตัวของระดับสต็อก กรองกลุ่มแท็ก และดาวน์โหลดตารางข้อมูลรายงานอัตโนมัติ</p>
    """, unsafe_allow_html=True)
    
    if not df_all.empty and "คงเหลือ" in df_all.columns:
        df_work = df_all.copy()
        df_work["คงเหลือ_ตัวเลข"] = pd.to_numeric(df_work["คงเหลือ"], errors="coerce")
        
        with st.container(border=True):
            st.markdown("##### 🎚️ ปรับแถบเลื่อนเพื่อระบุช่วงจำนวนสต็อกที่ต้องการ")
            stock_range = st.slider(
                "กำหนดช่วงยอดคงเหลือ:",
                min_value=0,
                max_value=3000,
                value=(0, 3000),
                step=10,
                help="เลื่อนแถบเพื่อวิเคราะห์เฉพาะกลุ่มสต็อกที่ต้องการ"
            )
        min_stock, max_stock = stock_range
        
        range_mask = (df_work["คงเหลือ_ตัวเลข"] >= min_stock) & (df_work["คงเหลือ_ตัวเลข"] <= max_stock)
        df_range = df_work[range_mask].reset_index(drop=True)
        
        if not df_range.empty:
            total_qty = int(df_range["คงเหลือ_ตัวเลข"].sum())
            avg_stock = df_range["คงเหลือ_ตัวเลข"].mean()

            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">📋 จำนวนรายการสินค้า</div>
                    <div class="kpi-value" style="color: #2563eb;">{len(df_range):,}</div>
                    <div class="kpi-sub">รายการที่อยู่ในเกณฑ์ที่เลือก</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi2:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">🔢 ยอดรวมชิ้นสินค้าคงคลัง</div>
                    <div class="kpi-value" style="color: #059669;">{total_qty:,}</div>
                    <div class="kpi-sub">ชิ้นทั้งหมดในระบบ</div>
                </div>
                """, unsafe_allow_html=True)
            with kpi3:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">📈 สต็อกเฉลี่ยต่อรายการ</div>
                    <div class="kpi-value" style="color: #d97706;">{avg_stock:.1f}</div>
                    <div class="kpi-sub">ชิ้น / รายการสินค้า</div>
                </div>
                """, unsafe_allow_html=True)

            st.write("")

            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                with st.container(border=True):
                    st.markdown("##### 📊 การกระจายตัวตามระดับสต็อก")
                    bins = [-1, 0, 50, 200, 500, 1000, 3000]
                    labels = ["0 (หมดสต็อก)", "1-50 (สต็อกต่ำ)", "51-200", "201-500", "501-1,000", "1,001-3,000"]
                    df_range["กลุ่มสต็อก"] = pd.cut(df_range["คงเหลือ_ตัวเลข"], bins=bins, labels=labels)
                    dist_chart = df_range["กลุ่มสต็อก"].value_counts().sort_index()
                    st.bar_chart(dist_chart, color="#3b82f6")

            with chart_col2:
                with st.container(border=True):
                    st.markdown("##### 🏷️ 10 อันดับแท็กที่มีสินค้ามากที่สุด")
                    top_tags = df_range["แท็ก {Tag}"].value_counts().head(10)
                    st.bar_chart(top_tags, color="#10b981")

            st.divider()

            unique_range_tags = sorted(list(df_range["แท็ก {Tag}"].dropna().unique()))
            selected_range_tag = st.selectbox(
                "🏷️ กรองดูรายละเอียดตามกลุ่มแท็กสินค้า:", 
                options=["แสดงทุกกลุ่มแท็ก"] + unique_range_tags,
                key="select_range_tag"
            )
            
            if selected_range_tag == "แสดงทุกกลุ่มแท็ก":
                active_range_df = df_range.copy()
                range_report_title = f"รายงานสต็อก_{min_stock}_ถึง_{max_stock}_ทั้งหมด"
                range_file_suffix = f"{min_stock}_{max_stock}_ทั้งหมด"
            else:
                active_range_df = df_range[df_range["แท็ก {Tag}"] == selected_range_tag].reset_index(drop=True)
                clean_tag = re.sub(r'[\{\}]', '', selected_range_tag)
                range_report_title = f"รายงานสต็อก_{min_stock}_ถึง_{max_stock}_แท็ก_{selected_range_tag}"
                range_file_suffix = f"{min_stock}_{max_stock}_แท็ก_{clean_tag}"

            st.markdown(f"#### 📋 {range_report_title.replace('_', ' ')} ({len(active_range_df):,} รายการ)")
            display_range_df = active_range_df.drop(columns=["ชื่อไฟล์ที่มา", "คงเหลือ_ตัวเลข", "กลุ่มสต็อก"], errors="ignore")
            
            output_range = io.BytesIO()
            with pd.ExcelWriter(output_range, engine="openpyxl") as writer:
                clean_sheet = re.sub(r'[\/\\\?\*\[\]\:]', '_', range_file_suffix)[:31]
                display_range_df.to_excel(writer, sheet_name=clean_sheet, index=False)
            
            st.download_button(
                label=f"📥 ดาวน์โหลดไฟล์ Excel ({range_report_title.replace('_', ' ')})",
                data=output_range.getvalue(),
                file_name=f"{range_report_title}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="btn_download_range_excel"
            )
            
            st.dataframe(display_range_df, use_container_width=True)

            st.divider()

            st.markdown(f"##### 🖼️ รายการการ์ดสินค้า (สต็อกช่วง {min_stock} ถึง {max_stock})")
            total_range_count = len(active_range_df)
            total_range_pages = max(1, math.ceil(total_range_count / ITEMS_PER_PAGE))
            
            r_col1, r_col2 = st.columns([3, 1])
            with r_col1:
                st.caption(f"แสดงตัวอย่างหน้าละ {ITEMS_PER_PAGE} รายการ")
            with r_col2:
                current_range_page = st.number_input(
                    f"หน้าแสดงผล (จาก {total_range_pages} หน้า):", 
                    min_value=1, 
                    max_value=total_range_pages, 
                    value=1, 
                    step=1,
                    key="range_page_input"
                )
            
            start_range_idx = (current_range_page - 1) * ITEMS_PER_PAGE
            end_range_idx = start_range_idx + ITEMS_PER_PAGE
            page_range_df = active_range_df.iloc[start_range_idx:end_range_idx].reset_index(drop=True)

            with st.container():
                render_product_cards(page_range_df, f"{min_stock}-{max_stock}")
        else:
            st.info(f"ไม่พบสินค้าที่มียอดคงเหลืออยู่ในช่วง {min_stock} ถึง {max_stock} ชิ้น")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

# --- 4. สรุปสายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง) ---
elif "สรุปสายงาน" in selected_menu:
    st.markdown("## 📊 ข้อมูลสายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง)")
    if not df_all.empty and "โซน" in df_all.columns:
        zone_summary = df_all.groupby("โซน").size().reset_index(name="จำนวนสินค้าทั้งหมด")
        with st.container(border=True):
            st.dataframe(zone_summary, use_container_width=True)
        with st.container(border=True):
            st.bar_chart(zone_summary.set_index("โซน"), color="#6366f1")
    else:
        st.info("ยังไม่มีข้อมูลสต็อกสินค้า")

# --- 5. ค้นหาสินค้า & Tag ---
elif "ค้นหาสินค้า" in selected_menu:
    st.markdown("## 🔍 ค้นหาสินค้า & แท็กข้ามทุกโซน")
    with st.container(border=True):
        keyword = st.text_input("พิมพ์รหัสสินค้า, รหัสรอง, หรือชื่อสินค้าที่ต้องการค้นหา:")
    if keyword and not df_all.empty:
        kw = keyword.strip().lower()
        search_cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}"]
        cond = False
        for c in search_cols:
            if c in df_all.columns:
                cond = cond | df_all[c].astype(str).str.lower().str.contains(kw, na=False)
        res_df = df_all[cond].reset_index(drop=True)
        st.info(f"ผลการค้นหา: พบ {len(res_df):,} รายการ")
        render_product_cards(res_df.head(ITEMS_PER_PAGE), "ค้นหา")
        st.dataframe(res_df, use_container_width=True)
