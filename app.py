# --- 2. หน้าสินค้าที่มีปัญหา (คงเหลือติดลบ) ---
elif selected_menu == "สินค้าที่มีปัญหา (คงเหลือติดลบ)":
    st.title("⚠️ สินค้าที่มีปัญหา (ยอดคงเหลือติดลบ)")
    
    if not df_all.empty and "คงเหลือ" in df_all.columns:
        # กรองเฉพาะรายการที่คงเหลือติดลบ
        neg_mask = df_all["คงเหลือ"].astype(str).str.contains("-", na=False)
        df_negative = df_all[neg_mask].reset_index(drop=True)
        
        if not df_negative.empty:
            st.error(f"ตรวจพบสินค้าติดลบทั้งหมด {len(df_negative):,} รายการทั่วทั้งระบบ")
            
            # 1. กล่องเลือกกรองตาม Tag
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

            # 2. ปุ่มดาวน์โหลดไฟล์ Excel และแสดงตารางข้อมูลทันที
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
            
            # ตาราง Excel แสดงผลบนหน้าเว็บ
            st.dataframe(display_neg_df, use_container_width=True)

            st.divider()

            # 3. แสดงการ์ดรูปภาพสินค้าพร้อมตัวแบ่งหน้า (Pagination)
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
