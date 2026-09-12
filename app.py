# --- 3. หน้าสินค้าสต็อก 0 ถึง 3000 ---
elif selected_menu == "สต็อกสินค้า 0 ถึง 3000":
    st.title("📊 แดชบอร์ดวิเคราะห์และรายงานสินค้าสต็อก (0 ถึง 3,000)")
    
    if not df_all.empty and "คงเหลือ" in df_all.columns:
        # แปลงข้อมูลสต็อกเป็นตัวเลขเพื่อใช้คำนวณและกรอง
        df_work = df_all.copy()
        df_work["คงเหลือ_ตัวเลข"] = pd.to_numeric(df_work["คงเหลือ"], errors="coerce")
        
        # 1. ลูกเล่นแถบเลื่อน (Slider) เลือกช่วงสต็อกที่ต้องการดู
        st.markdown("##### 🎚️ เลือกช่วงจำนวนคงเหลือที่ต้องการตรวจสอบ")
        stock_range = st.slider(
            "กำหนดช่วงยอดคงเหลือ:",
            min_value=0,
            max_value=3000,
            value=(0, 3000),
            step=10,
            help="เลื่อนแถบซ้าย-ขวาเพื่อดูเฉพาะช่วงสต็อกที่สนใจได้ทันที"
        )
        min_stock, max_stock = stock_range
        
        # กรองข้อมูลตามช่วงสต็อกที่เลือก
        range_mask = (df_work["คงเหลือ_ตัวเลข"] >= min_stock) & (df_work["คงเหลือ_ตัวเลข"] <= max_stock)
        df_range = df_work[range_mask].reset_index(drop=True)
        
        if not df_range.empty:
            # 2. แถบสรุปสถิติ (KPI Cards)
            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.metric("📦 จำนวนรายการสินค้า", f"{len(df_range):,} รายการ")
            with kpi2:
                total_qty = int(df_range["คงเหลือ_ตัวเลข"].sum())
                st.metric("🔢 ยอดรวมสินค้าทั้งหมด", f"{total_qty:,} ชิ้น")
            with kpi3:
                avg_stock = df_range["คงเหลือ_ตัวเลข"].mean()
                st.metric("📈 สต็อกเฉลี่ยต่อรายการ", f"{avg_stock:.1f} ชิ้น")

            # 3. แผนภูมิแท่งวิเคราะห์ (Charts)
            chart_col1, chart_col2 = st.columns(2)
            with chart_col1:
                st.markdown("###### 📊 การกระจายตัวตามระดับสต็อก")
                # แบ่งกลุ่มตัวเลขสต็อก
                bins = [-1, 0, 50, 200, 500, 1000, 3000]
                labels = ["0 (หมดสต็อก)", "1-50 (สต็อกต่ำ)", "51-200", "201-500", "501-1,000", "1,001-3,000"]
                df_range["กลุ่มสต็อก"] = pd.cut(df_range["คงเหลือ_ตัวเลข"], bins=bins, labels=labels)
                dist_chart = df_range["กลุ่มสต็อก"].value_counts().sort_index()
                st.bar_chart(dist_chart, color="#3b82f6")

            with chart_col2:
                st.markdown("###### 🏷️ 10 อันดับแท็กที่มีสินค้ามากที่สุด")
                top_tags = df_range["แท็ก {Tag}"].value_counts().head(10)
                st.bar_chart(top_tags, color="#10b981")

            st.divider()

            # 4. กรองดูตามแท็ก
            unique_range_tags = sorted(list(df_range["แท็ก {Tag}"].dropna().unique()))
            selected_range_tag = st.selectbox(
                "🏷️ กรองดูรายละเอียดตามกลุ่มแท็ก:", 
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

            # 5. ตารางข้อมูลและปุ่มดาวน์โหลดรายงาน Excel
            st.subheader(f"📋 {range_report_title.replace('_', ' ')} ({len(active_range_df):,} รายการ)")
            display_range_df = active_range_df.drop(columns=["ชื่อไฟล์ที่มา", "คงเหลือ_ตัวเลข", "กลุ่มสต็อก"], errors="ignore")
            
            output_range = io.BytesIO()
            with pd.ExcelWriter(output_range, engine="openpyxl") as writer:
                clean_sheet = re.sub(r'[\/\\\?\*\[\]\:]', '_', range_file_suffix)[:31]
                display_range_df.to_excel(writer, sheet_name=clean_sheet, index=False)
            
            st.download_button(
                label=f"📥 ดาวน์โหลด Excel ({range_report_title.replace('_', ' ')})",
                data=output_range.getvalue(),
                file_name=f"{range_report_title}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                key="btn_download_range_excel"
            )
            
            st.dataframe(display_range_df, use_container_width=True)

            st.divider()

            # 6. แสดงการ์ดรูปภาพสินค้าพร้อมระบบแบ่งหน้า
            st.markdown(f"##### 🖼️ การ์ดรายการสินค้า (สต็อกช่วง {min_stock} ถึง {max_stock})")
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
