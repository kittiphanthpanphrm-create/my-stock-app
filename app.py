import io
import math
import os
import re
import pandas as pd
from pypdf import PdfReader
import streamlit as st

st.set_page_config(page_title="TKK ERP - จัดการคลังและโซนสินค้า", layout="wide")

# ซ่อนปุ่มกากบาทของ uploader
st.markdown("""
<style>
button[aria-label="Delete"] { display: none !important; }
div[data-testid="stFileUploaderDeleteBtn"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

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

def clean_and_prepare_df(raw_df, source_name, target_zone):
    df = raw_df.copy()
    for col in df.columns:
        c_str = str(col).strip()
        if "รหัสสินค้า" in c_str or c_str == "รหัส":
            df["รหัสสินค้า"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if "รหัสรอง" in c_str:
            df["รหัสรอง"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    name_col = next(
        (c for c in df.columns if "ชื่อรายการสินค้า" in str(c) or "ชื่อ" in str(c) or "รายละ" in str(c)),
        df.columns[2] if len(df.columns) > 2 else df.columns[0]
    )
    df["ชื่อรายการสินค้า"] = df[name_col].astype(str).apply(lambda x: re.sub(r'\{[^}]+\}', '', x).replace("•", "").strip())

    tag_col = next((c for c in df.columns if "แท็ก" in str(c) and "ชื่อ" not in str(c)), None)
    if tag_col:
        df["แท็ก {Tag}"] = df[tag_col].fillna("{ทั่วไป}").astype(str).str.strip()
    else:
        def get_tag(x):
            m = re.search(r'\{([^}]+)\}', str(x))
            return f"{{{m.group(1).strip()}}}" if m else "{ทั่วไป}"
        df["แท็ก {Tag}"] = df[name_col].astype(str).apply(get_tag)

    for c in df.columns:
        c_str = str(c).strip()
        if "สั่ง" in c_str:
            df["จำนวนสั่งล่าสุด"] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int).astype(str)
        if "คงเหลือ" in c_str:
            df["คงเหลือ"] = df[c].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    if "โซน" not in df.columns:
        df["โซน"] = target_zone
    else:
        df["โซน"] = df["โซน"].fillna(target_zone).astype(str).str.strip()

    df["ชื่อไฟล์ที่มา"] = source_name
    standard_cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}", "หน่วยนับ", "จำนวนสั่งล่าสุด", "โซน", "คงเหลือ", "สถานะ", "ชื่อไฟล์ที่มา"]
    existing_cols = [c for c in standard_cols if c in df.columns]
    return df[existing_cols]

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
            
        qty = row.get("จำนวนสั่งล่าสุด", 0)
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
                         style="width: 100%; aspect-ratio: 1/1; object-fit: contain; border-radius: 12px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.08);" />
                </div>
                <div style="text-align: center; height: 44px; overflow: hidden; font-size: 13px; font-weight: 600; color: #1e293b; line-height: 1.4; margin-bottom: 6px;">
                    • {name}
                </div>
                <div style="text-align: center; font-size: 11px; color: #64748b; line-height: 1.6; margin-bottom: 6px;">
                    <div>รหัสสินค้า: <span style="color: #334155;">{barcode if barcode else '-'}</span></div>
                    <div>รหัสรอง: <b style="color: #2563eb;">{sub_code if sub_code else '-'}</b></div>
                    <div>จำนวนคงเหลือ : <b style="color: {'#dc2626' if '-' in stock else '#059669'};">{stock}</b></div>
                </div>
                """, unsafe_allow_html=True)

if "current_df" not in st.session_state:
    st.session_state.current_df = load_database()
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# --- เมนูด้านข้าง (Sidebar) ---
with st.sidebar:
    st.title("📦 การจัดการสต็อก")
    
    st.markdown("##### 🧭 ฟังก์ชันการทำงาน")
    selected_menu = st.radio(
        "เลือกฟังก์ชัน:",
        options=[
            "จัดการสินค้า (รายโซน)",
            "สินค้าที่มีปัญหา (คงเหลือติดลบ)",
            "สรุปสายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง)",
            "ค้นหาสินค้า & Tag"
        ],
        index=0,
        label_visibility="collapsed"
    )
    
    st.divider()
    st.markdown("##### 📍 โซนสินค้า (30 โซน)")
    selected_zone = st.selectbox("เลือกโซนที่ต้องการเข้าดู:", options=ALL_ZONES, index=0)
    
    st.divider()
    st.markdown(f"##### ⚙️ จัดการข้อมูล [โซน {selected_zone}]")
    
    with st.expander(f"📥 แนบไฟล์ข้อมูลเข้าโซน {selected_zone}", expanded=False):
        uploaded_files = st.file_uploader(
            f"เลือกไฟล์สำหรับโซน {selected_zone} (PDF, CSV, XLSX)", 
            type=["pdf", "csv", "xlsx"], 
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
                    elif u_file.name.endswith(".xlsx"):
                        t_df = clean_and_prepare_df(pd.read_excel(u_file), u_file.name, selected_zone)
                    
                    if not t_df.empty:
                        t_df["โซน"] = t_df["โซน"].replace({"": selected_zone, "-": selected_zone}).fillna(selected_zone)
                        preview_dfs.append(t_df)
                except Exception as e:
                    st.error(f"ไฟล์ {u_file.name} มีปัญหา: {e}")
            
            if preview_dfs:
                combined_new_df = pd.concat(preview_dfs, ignore_index=True)
                st.info(f"พร้อมบันทึก: {len(combined_new_df)} รายการ")
                
                if st.button("💾 อัปโหลดบันทึกเข้าสู่ระบบ", type="primary", use_container_width=True):
                    if st.session_state.current_df.empty:
                        st.session_state.current_df = combined_new_df
                    else:
                        st.session_state.current_df = pd.concat([st.session_state.current_df, combined_new_df], ignore_index=True)
                        if "รหัสสินค้า" in st.session_state.current_df.columns:
                            st.session_state.current_df.drop_duplicates(subset=["รหัสสินค้า"], keep="last", inplace=True)
                    
                    save_database(st.session_state.current_df)
                    st.session_state.uploader_key += 1
                    st.success("บันทึกข้อมูลเรียบร้อย!")
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

df_all = st.session_state.current_df

# --- 1. หน้าจัดการสินค้า (รายโซน) ---
if selected_menu == "จัดการสินค้า (รายโซน)":
    if not df_all.empty and "โซน" in df_all.columns:
        df_zone = df_all[df_all["โซน"] == selected_zone].reset_index(drop=True)
    else:
        df_zone = pd.DataFrame()

    top_c1, top_c2, top_c3, top_c4 = st.columns(4)
    with top_c1:
        st.subheader(f"โซน {selected_zone}")
    with top_c2:
        st.subheader("รวมทุกแท็ก")
    with top_c3:
        st.subheader("ทั้งหมด")
    with top_c4:
        total_items = len(df_zone)
        st.subheader(f"{total_items:,} รายการ")

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
elif selected_menu == "สินค้าที่มีปัญหา (คงเหลือติดลบ)":
    st.title("⚠️ สินค้าที่มีปัญหา (ยอดคงเหลือติดลบ)")
    
    if not df_all.empty and "คงเหลือ" in df_all.columns:
        neg_mask = df_all["คงเหลือ"].astype(str).str.contains("-", na=False)
        df_negative = df_all[neg_mask].reset_index(drop=True)
        
        if not df_negative.empty:
            st.error(f"ตรวจพบสินค้าติดลบทั้งหมด {len(df_negative):,} รายการทั่วทั้งระบบ")
            
            # 1. เลือกกรองตาม Tag
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

            # 2. ปุ่มดาวน์โหลดและตารางแสดงข้อมูล
            st.subheader(f"📋 ตารางข้อมูล: {report_title} ({len(active_neg_df):,} รายการ)")
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

            # 3. แสดงรูปภาพสินค้าติดลบ (ไม่มีปุ่มใส่ตะกร้า)
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
            st.success("🎉 ไม่พบสินค้าที่มียอดคงเหลือติดลบในระบบ")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

# --- 3. สรุปสายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง) ---
elif selected_menu == "สรุปสายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง)":
    st.title("📊 ข้อมูลสายงานรายเดือน (วิเคราะห์การเปลี่ยนแปลง)")
    if not df_all.empty and "โซน" in df_all.columns:
        zone_summary = df_all.groupby("โซน").size().reset_index(name="จำนวนสินค้าทั้งหมด")
        st.dataframe(zone_summary, use_container_width=True)
        st.bar_chart(zone_summary.set_index("โซน"))
    else:
        st.info("ยังไม่มีข้อมูลสต็อกสินค้า")

# --- 4. ค้นหาสินค้า & Tag ---
elif selected_menu == "ค้นหาสินค้า & Tag":
    st.title("🔍 ค้นหาสินค้า & แท็กข้ามทุกโซน")
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
