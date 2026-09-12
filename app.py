def render_product_cards(items_df, current_zone):
    cols = st.columns(4)  # จัดแถวละ 4 กล่องตามหน้าเว็บ TKK Online
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
        
        # ถอดรหัสรูปภาพและลิงก์
        code_for_img = barcode if (barcode and len(barcode) >= 5) else sub_code
        img_url = f"https://tkkonlineshop.com/images/products/{code_for_img}.jpg"
        web_link = f"https://tkkonlineshop.com/products/{code_for_img}" if code_for_img else "https://tkkonlineshop.com"
        
        with cols[idx % 4]:
            with st.container(border=True):
                # 1. รูปภาพสินค้าพร้อมกรอบโค้งมน
                st.markdown(f"""
                <div style="text-align: center; margin-bottom: 10px;">
                    <a href="{web_link}" target="_blank">
                        <img src="{img_url}" 
                             onerror="this.onerror=null; this.src='{NO_IMAGE_PLACEHOLDER}';" 
                             loading="lazy"
                             style="width: 100%; aspect-ratio: 1/1; object-fit: contain; border-radius: 12px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.08);" />
                    </a>
                </div>
                """, unsafe_allow_html=True)
                
                # 2. ชื่อสินค้าตรงกลาง (ตัดบรรทัดให้พอดี)
                st.markdown(f"""
                <div style="text-align: center; height: 42px; overflow: hidden; font-size: 13px; font-weight: 600; color: #1e293b; line-height: 1.4; margin-bottom: 6px;">
                    • {name}
                </div>
                """, unsafe_allow_html=True)
                
                # 3. รหัสสินค้า, รหัสรอง, ยอดคงเหลือ
                st.markdown(f"""
                <div style="text-align: center; font-size: 11px; color: #64748b; line-height: 1.6; margin-bottom: 8px;">
                    <div>รหัสสินค้า: <span style="color: #334155;">{barcode if barcode else '-'}</span></div>
                    <div>รหัสรอง: <b style="color: #2563eb;">{sub_code if sub_code else '-'}</b></div>
                    <div>จำนวนคงเหลือ : <b style="color: {'#dc2626' if '-' in stock else '#059669'};">{stock}</b></div>
                </div>
                """, unsafe_allow_html=True)
                
                # 4. ปุ่มเปิดดูบนเว็บ TKK Online
                st.link_button("🛒 รายละเอียด / ใส่ตะกร้า", web_link, use_container_width=True)
