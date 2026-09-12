# --- 0. หน้าแดชบอร์ดภาพรวมระบบ (Executive Dashboard) ---
if "แดชบอร์ดภาพรวมระบบ" in selected_menu:
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
            <h1 style="font-size: 28px; font-weight: 800; margin: 0; color: #0f172a;">📊 แดชบอร์ดภาพรวมระบบคลังสินค้า (30 โซน)</h1>
        </div>
        <p style="color: #64748b; font-size: 14px; margin-bottom: 20px;">ศูนย์รวมสถิติ ตัวเลขชี้วัดหลัก (KPIs) และสถานะสต็อกสินค้าทั่วทั้งองค์กรแบบเรียลไทม์</p>
    """, unsafe_allow_html=True)

    if not df_all.empty and "คงเหลือ" in df_all.columns:
        df_dash = df_all.copy()
        df_dash["คงเหลือ_ตัวเลข"] = pd.to_numeric(df_dash["คงเหลือ"], errors="coerce").fillna(0)
        
        # คำนวณตัวเลขทางสถิติ
        total_skus = len(df_dash)
        total_units = int(df_dash["คงเหลือ_ตัวเลข"].sum())
        neg_items = (df_dash["คงเหลือ_ตัวเลข"] < 0).sum()
        zero_items = (df_dash["คงเหลือ_ตัวเลข"] == 0).sum()
        active_zones_count = df_dash["โซน"].nunique() if "โซน" in df_dash.columns else 0

        # 1. การ์ดตัวเลขสรุปหลัก (KPI Cards 4 ช่อง)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">📦 รายการสินค้าทั้งหมด</div>
                    <div class="kpi-value" style="color: #2563eb;">{total_skus:,} <span style="font-size: 15px;">รายการ</span></div>
                    <div class="kpi-sub">กระจายอยู่ใน {active_zones_count} โซนที่มีข้อมูล</div>
                </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">🔢 ยอดชิ้นคงคลังรวม</div>
                    <div class="kpi-value" style="color: #059669;">{total_units:,} <span style="font-size: 15px;">ชิ้น</span></div>
                    <div class="kpi-sub">ปริมาณสินค้าทั้งหมดในคลัง</div>
                </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">⚠️ สินค้าสต็อกติดลบ</div>
                    <div class="kpi-value" style="color: #dc2626;">{neg_items:,} <span style="font-size: 15px;">รายการ</span></div>
                    <div class="kpi-sub">ต้องตรวจสอบยอดและเคลียร์สต็อก</div>
                </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-title">⭕ สินค้าหมดสต็อก (0)</div>
                    <div class="kpi-value" style="color: #f59e0b;">{zero_items:,} <span style="font-size: 15px;">รายการ</span></div>
                    <div class="kpi-sub">สินค้าพร้อมสั่งซื้อเติมสต็อก</div>
                </div>
            """, unsafe_allow_html=True)

        st.write("")

        # 2. แผนภูมิวิเคราะห์เปรียบเทียบ
        col_g1, col_g2 = st.columns([1.6, 1])
        with col_g1:
            with st.container(border=True):
                st.markdown("##### 📍 ปริมาณสินค้าแยกตามแต่ละโซน (SKU Count)")
                zone_counts = df_dash.groupby("โซน").size().sort_values(ascending=False)
                st.bar_chart(zone_counts, color="#3b82f6")

        with col_g2:
            with st.container(border=True):
                st.markdown("##### 🏷️ 10 อันดับแท็กที่มีสต็อกชิ้นมากที่สุด")
                tag_stock = df_dash.groupby("แท็ก {Tag}")["คงเหลือ_ตัวเลข"].sum().sort_values(ascending=False).head(10)
                st.bar_chart(tag_stock, color="#10b981")

        st.divider()

        # 3. ตารางสรุปภาพรวมรายโซน (Zone Summary Table)
        st.markdown("#### 📋 ตารางสรุปภาพรวมแยกตามโซนสินค้า")
        zone_summary_table = df_dash.groupby("โซน").agg(
            จำนวนรายการ_SKU=("รหัสสินค้า", "count"),
            ยอดชิ้นคงคลังรวม=("คงเหลือ_ตัวเลข", "sum"),
            รายการติดลบ=("คงเหลือ_ตัวเลข", lambda x: (x < 0).sum()),
            รายการสต็อกศูนย์=("คงเหลือ_ตัวเลข", lambda x: (x == 0).sum())
        ).reset_index()

        st.dataframe(zone_summary_table, use_container_width=True)

        # ปุ่มดาวน์โหลดสรุปภาพรวม 30 โซนเป็น Excel
        out_dash = io.BytesIO()
        with pd.ExcelWriter(out_dash, engine="openpyxl") as writer:
            zone_summary_table.to_excel(writer, sheet_name="Zone_Summary", index=False)
            df_dash.drop(columns=["คงเหลือ_ตัวเลข"], errors="ignore").to_excel(writer, sheet_name="All_Inventory", index=False)

        st.download_button(
            label="📥 ดาวน์โหลดรายงานภาพรวมทั้งคลัง (Excel)",
            data=out_dash.getvalue(),
            file_name="รายงานภาพรวมคลังสินค้า_30โซน.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.info("💡 ขณะนี้ยังไม่มีข้อมูลในระบบ สามารถล็อกอินโหมด Admin เพื่อเริ่มนำเข้าข้อมูลได้ทันที")

# --- 1. หน้าจัดการสินค้า (รายโซน) ---
elif "จัดการสินค้า" in selected_menu:
    # โค้ดเดิม...
