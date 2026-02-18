import streamlit as st
from supabase import create_client
import pandas as pd
import datetime
import time
import io
import os

# --- 1. ตั้งค่าและเชื่อมต่อ (SETUP) ---
# 🌟 เปลี่ยนกลับมาใช้อิโมจิ เพื่อป้องกันหน้าเว็บพังเวลาโหลดโลโก้ไม่ขึ้น
st.set_page_config(page_title="ระบบคลังยา รพ.สต. โพนบก", layout="wide", page_icon="🏥")

st.markdown("""
<style>
    .stButton>button { border-radius: 8px; transition: all 0.3s ease; border: 1px solid #e0e0e0; font-weight: bold; }
    .stButton>button:hover { transform: scale(1.02); border-color: #2e7bcf; color: #2e7bcf; }
    [data-testid="stForm"] { border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); padding: 2rem; }
    [data-testid="stAlert"] { border-radius: 8px; }
    [data-testid="stMetricValue"] { color: #2e7bcf; }
    .item-box { border: 1px solid #eee; padding: 15px; border-radius: 8px; margin-bottom: 10px; background-color: #fafafa;}
    .alert-box { border-left: 5px solid #e74c3c; padding: 10px; background-color: #fdf2f0; border-radius: 5px; margin-bottom: 10px; }
    .warn-box { border-left: 5px solid #f39c12; padding: 10px; background-color: #fef9f1; border-radius: 5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["supabase_url"]
        key = st.secrets["supabase"]["supabase_key"]
        return create_client(url, key)
    except:
        st.error("❌ ไม่พบ Secrets! กรุณาตั้งค่า supabase_url และ supabase_key ใน Streamlit")
        return None

supabase = init_connection()

if 'user' not in st.session_state: st.session_state.user = None
if 'role' not in st.session_state: st.session_state.role = None
if 'user_email' not in st.session_state: st.session_state.user_email = None
if 'full_name' not in st.session_state: st.session_state.full_name = None

THAI_MONTHS = {'01': 'มกราคม', '02': 'กุมภาพันธ์', '03': 'มีนาคม', '04': 'เมษายน', '05': 'พฤษภาคม', '06': 'มิถุนายน', '07': 'กรกฎาคม', '08': 'สิงหาคม', '09': 'กันยายน', '10': 'ตุลาคม', '11': 'พฤศจิกายน', '12': 'ธันวาคม'}

def format_thai_month(ym_str):
    if not isinstance(ym_str, str) or '-' not in ym_str: return ym_str
    y, m = ym_str.split('-')
    return f"{THAI_MONTHS.get(m, m)} {int(y) + 543}"

def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        profile = supabase.table("profiles").select("*").eq("id", response.user.id).execute()
        if profile.data:
            if profile.data[0]['is_approved']:
                st.session_state.user = response.user
                st.session_state.role = profile.data[0]['role']
                st.session_state.user_email = email
                
                saved_name = profile.data[0].get('full_name')
                st.session_state.full_name = saved_name if saved_name else email
                
                st.success(f"เข้าสู่ระบบสำเร็จ! ยินดีต้อนรับ {st.session_state.full_name}")
                time.sleep(1)
                st.rerun()
            else: st.warning("บัญชีของคุณอยู่ระหว่างรอการอนุมัติจากผู้ดูแลระบบ")
        else: st.error("ไม่พบข้อมูลสิทธิ์ผู้ใช้งาน หรือบัญชีถูกระงับ")
    except Exception as e:
        st.error("อีเมลหรือรหัสผ่านไม่ถูกต้อง")

def logout_user():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.role = None
    st.session_state.full_name = None
    st.rerun()

def get_medicines():
    return pd.DataFrame(supabase.table("medicines").select("*").eq("is_active", True).execute().data)

def get_inventory_view():
    meds = pd.DataFrame(supabase.table("medicines").select("id, generic_name, unit").execute().data)
    inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
    if inv.empty: return pd.DataFrame()
    merged = pd.merge(inv, meds, left_on="medicine_id", right_on="id", how="left", suffixes=('', '_med'))
    return merged[merged['qty'] > 0]

def get_transactions_view():
    trans_response = supabase.table("transactions").select("*").order("created_at", desc=True).execute()
    meds_response = supabase.table("medicines").select("id, generic_name, unit").execute()
    trans = pd.DataFrame(trans_response.data)
    meds = pd.DataFrame(meds_response.data)
    if trans.empty: return pd.DataFrame()
    merged = pd.merge(trans, meds, left_on="medicine_id", right_on="id", how="left", suffixes=('', '_med'))
    return merged

# --- 4. ส่วนหน้าจอ (FRONTEND) ---
if not st.session_state.user:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # 🌟 ระบบดึงรูปจากเครื่อง ถ้าไม่มีไฟล์ moph_logo.png จะใช้ตึก รพ. แทนหน้าเว็บจะได้ไม่พัง
        if os.path.exists("moph_logo.png"):
            st.image("moph_logo.png", width=120)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=100)
            
        st.title("ระบบคลังเวชภัณฑ์")
        st.markdown("##### รพ.สต. โพนบก 🏥")
        
        tab_login, tab_register = st.tabs(["🔐 เข้าสู่ระบบ", "📝 สมัครใช้งาน"])
        
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("อีเมลผู้ใช้งาน")
                password = st.text_input("รหัสผ่าน", type="password")
                if st.form_submit_button("เข้าสู่ระบบ", use_container_width=True):
                    login_user(email, password)
                    
        with tab_register:
            with st.form("register_form"):
                st.info("💡 สมัครสมาชิกใหม่ แล้วรอผู้ดูแลระบบอนุมัติเพื่อเข้าใช้งาน")
                reg_name = st.text_input("ชื่อ - นามสกุล")
                reg_email = st.text_input("อีเมล")
                reg_password = st.text_input("รหัสผ่าน (ขั้นต่ำ 6 ตัวอักษร)", type="password")
                if st.form_submit_button("สมัครสมาชิก", use_container_width=True):
                    if reg_name and reg_email and len(reg_password) >= 6:
                        try:
                            res = supabase.auth.sign_up({"email": reg_email, "password": reg_password})
                            if res.user:
                                try:
                                    supabase.table("profiles").update({"full_name": reg_name}).eq("id", res.user.id).execute()
                                except: pass
                            st.success("สมัครสมาชิกสำเร็จ! โปรดแจ้งผู้ดูแลระบบเพื่ออนุมัติการใช้งาน")
                        except Exception as e:
                            st.error(f"สมัครไม่สำเร็จ (อีเมลอาจซ้ำ หรือรหัสผ่านสั้นไป): {e}")
                    else:
                        st.warning("กรุณากรอกชื่อ-สกุล, อีเมล และรหัสผ่านให้ครบถ้วน")

else:
    with st.sidebar:
        # 🌟 ระบบดึงรูปจากเครื่อง สำหรับแถบเมนู
        if os.path.exists("moph_logo.png"):
            st.image("moph_logo.png", width=80)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=60)
            
        display_name = st.session_state.full_name if st.session_state.full_name else st.session_state.user_email
        st.write(f"👤 **{display_name}**")
        st.caption(f"✉️ {st.session_state.user_email}")
        st.caption(f"⭐ สถานะ: {st.session_state.role.upper()}")
        if st.button("ออกจากระบบ", use_container_width=True): logout_user()
        st.divider()

    menu_options = [
        "🖥️ แดชบอร์ด", 
        "📤 เบิกจ่ายยา (Dispense)", 
        "📥 รับยาเข้า (Receive)", 
        "🧾 ประวัติรับ-จ่าย", 
        "🗃️ สต๊อกการ์ด", 
        "📊 สรุปยอด และ ขอเบิก", 
        "📋 ข้อมูลยา (Master Data)"
    ]
    if st.session_state.role == 'admin': menu_options.append("⚙️ จัดการระบบ (Admin)")
    
    menu = st.sidebar.radio("📌 เมนูหลัก", menu_options)

    # ----------------------------------------------------------------------
    # ⚙️ จัดการระบบ (Admin)
    # ----------------------------------------------------------------------
    if menu == "⚙️ จัดการระบบ (Admin)":
        st.header("⚙️ จัดการระบบ (Admin Panel)")
        
        tab_manage, tab_add, tab_delete = st.tabs(["👥 จัดการคำขอ / อนุมัติ", "➕ สร้างผู้ใช้ใหม่", "🗑️ ลบบัญชีผู้ใช้"])
        
        with tab_manage:
            profiles = pd.DataFrame(supabase.table("profiles").select("*").execute().data)
            if not profiles.empty:
                profiles['status'] = profiles['is_approved'].map({True: 'อนุมัติแล้ว', False: 'รออนุมัติ'})
                cols_to_show = ['email', 'full_name', 'role', 'status', 'created_at']
                existing_cols = [c for c in cols_to_show if c in profiles.columns]
                st.dataframe(profiles[existing_cols], use_container_width=True)
                
                st.divider()
                st.subheader("จัดการคำขอใช้งาน")
                pending_users = profiles[profiles['is_approved'] == False]
                if not pending_users.empty:
                    user_to_approve = st.selectbox("เลือกผู้ใช้เพื่ออนุมัติ", pending_users['email'])
                    c1, c2 = st.columns(2)
                    if c1.button("อนุมัติให้เป็น Staff", use_container_width=True):
                        supabase.table("profiles").update({"is_approved": True}).eq("email", user_to_approve).execute()
                        st.success("อนุมัติเรียบร้อย!"); st.rerun()
                    if c2.button("แต่งตั้งเป็น Admin", use_container_width=True):
                        supabase.table("profiles").update({"is_approved": True, "role": "admin"}).eq("email", user_to_approve).execute()
                        st.success("แต่งตั้งเป็น Admin เรียบร้อย!"); st.rerun()
                else: st.info("ไม่มีคำขอรออนุมัติ")
                
        with tab_add:
            st.subheader("สร้างบัญชีผู้ใช้งานใหม่")
            with st.form("admin_add_user"):
                new_name = st.text_input("ชื่อ - นามสกุล")
                new_email = st.text_input("อีเมลผู้ใช้งานใหม่")
                new_password = st.text_input("รหัสผ่าน (ขั้นต่ำ 6 ตัวอักษร)", type="password")
                new_role = st.selectbox("สิทธิ์การใช้งาน", ["staff", "admin"])
                
                if st.form_submit_button("สร้างบัญชี", use_container_width=True):
                    if new_name and new_email and len(new_password) >= 6:
                        try:
                            res = supabase.auth.sign_up({"email": new_email, "password": new_password})
                            if res.user:
                                supabase.table("profiles").update({"is_approved": True, "role": new_role, "full_name": new_name}).eq("id", res.user.id).execute()
                                st.success(f"สร้างบัญชี {new_email} สำเร็จ!")
                                st.warning("ข้อควรระวัง: หลังจากนี้ให้กดปุ่ม 'ออกจากระบบ' แล้วล็อกอินบัญชี Admin กลับเข้ามาอีกครั้ง")
                                time.sleep(4)
                                st.rerun()
                        except Exception as e:
                            st.error(f"ไม่สามารถสร้างบัญชีได้: {e}")
                    else:
                        st.warning("กรุณากรอกข้อมูลให้ครบถ้วน (และรหัสผ่านขั้นต่ำ 6 ตัวอักษร)")

        with tab_delete:
            st.subheader("เพิกถอนสิทธิ์ / ลบบัญชีผู้ใช้งาน")
            
            all_profiles = pd.DataFrame(supabase.table("profiles").select("*").execute().data)
            if not all_profiles.empty:
                other_users = all_profiles[all_profiles['email'] != st.session_state.user_email]
                if not other_users.empty:
                    user_to_delete = st.selectbox("เลือกอีเมลที่ต้องการลบสิทธิ์การเข้าถึง:", other_users['email'].tolist())
                    confirm_del_user = st.checkbox("ยืนยันว่าต้องการลบสิทธิ์ผู้ใช้นี้", key="confirm_del_user")
                    
                    if st.button("ลบผู้ใช้งาน", type="primary"):
                        if confirm_del_user:
                            try:
                                supabase.table("profiles").delete().eq("email", user_to_delete).execute()
                                st.success(f"ลบสิทธิ์ของ {user_to_delete} เรียบร้อยแล้ว!")
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"เกิดข้อผิดพลาดในการลบ: {e}")
                        else:
                            st.error("กรุณาติ๊กช่องยืนยันก่อนกดปุ่มลบ")
                else:
                    st.info("ไม่มีผู้ใช้งานอื่นในระบบ")

    # ----------------------------------------------------------------------
    # 🖥️ แดชบอร์ด
    # ----------------------------------------------------------------------
    elif menu == "🖥️ แดชบอร์ด":
        st.header("🖥️ ภาพรวมคลังเวชภัณฑ์ (Dashboard)")
        try:
            meds = pd.DataFrame(supabase.table("medicines").select("id, generic_name, unit, min_stock, category").eq("is_active", True).execute().data)
            inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
            
            if not meds.empty:
                count_drugs = len(meds[meds['category'].isin(['ยาในบัญชี', 'ยานอกบัญชี'])])
                count_supplies = len(meds[meds['category'] == 'เวชภัณฑ์/วัสดุ'])

                if not inv.empty:
                    inv_agg = inv.groupby('medicine_id')['qty'].sum().reset_index()
                    df_dash = pd.merge(meds, inv_agg, left_on='id', right_on='medicine_id', how='left')
                    df_dash['qty'] = df_dash['qty'].fillna(0)
                else:
                    df_dash = meds.copy()
                    df_dash['qty'] = 0

                low_stock = df_dash[df_dash['qty'] <= df_dash['min_stock']]
                
                near_exp = pd.DataFrame()
                if not inv.empty:
                    inv_active = inv[inv['qty'] > 0].copy()
                    if not inv_active.empty:
                        inv_active['exp_date'] = pd.to_datetime(inv_active['exp_date'])
                        today = pd.to_datetime(datetime.date.today())
                        near_exp_raw = inv_active[inv_active['exp_date'] <= today + pd.Timedelta(days=90)]
                        if not near_exp_raw.empty:
                            near_exp = pd.merge(near_exp_raw, meds, left_on='medicine_id', right_on='id', how='left')
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("รายการเวชภัณฑ์ยา", f"{count_drugs}", "รายการ")
                c2.metric("รายการเวชภัณฑ์ที่มิใช่ยา", f"{count_supplies}", "รายการ")
                c3.metric("ต่ำกว่าจุดสั่งซื้อ (Re-order)", f"{len(low_stock)}", "รายการ", delta_color="inverse")
                c4.metric("ใกล้หมดอายุ (< 3 เดือน)", f"{len(near_exp)}", "ล็อต", delta_color="inverse")
                
                st.divider()
                
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("#### แจ้งเตือน: ต่ำกว่าจุดสั่งซื้อ (Re-order Point)")
                    st.caption("รายการเวชภัณฑ์ที่ต้องดำเนินการจัดหาเพิ่ม (คงเหลือน้อยกว่าหรือเท่ากับ Min Stock)")
                    if not low_stock.empty:
                        for _, row in low_stock.iterrows():
                            st.markdown(f'<div class="warn-box"><strong>{row["generic_name"]}</strong><br>คงเหลือ: <span style="color:#d35400; font-size:18px;"><b>{int(row["qty"])}</b></span> {row["unit"]} (จุดสั่งซื้อ: {row["min_stock"]})</div>', unsafe_allow_html=True)
                    else: st.success("ยอดคงคลังเพียงพอทุกรายการ")
                    
                with col_r:
                    st.markdown("#### แจ้งเตือน: เวชภัณฑ์ใกล้หมดอายุ (Near Expiry)")
                    st.caption("รายการที่จะหมดอายุภายใน 3 เดือนข้างหน้า (90 วัน) - เร่งกระจายตามหลัก FEFO")
                    if not near_exp.empty:
                        for _, row in near_exp.iterrows():
                            exp_date = row['exp_date'].strftime('%d/%m/%Y')
                            st.markdown(f'<div class="alert-box"><strong>{row["generic_name"]}</strong><br>Lot: {row["lot_no"]} | เหลือ: {int(row["qty"])} {row["unit"]}<br>📅 <b>หมดอายุ: {exp_date}</b></div>', unsafe_allow_html=True)
                    else: st.success("ไม่มีเวชภัณฑ์เสี่ยงหมดอายุใน 3 เดือน")
            else: st.info("ยังไม่มีข้อมูล Master Data ในระบบ")
        except Exception as e: st.error(f"Error: {e}")

    # ----------------------------------------------------------------------
    # 📊 สรุปยอดประจำเดือน และ รายงานขอเบิก
    # ----------------------------------------------------------------------
    elif menu == "📊 สรุปยอด และ ขอเบิก":
        st.header("📊 สรุปยอด และ ขอเบิกเวชภัณฑ์")
        
        tab_summary, tab_reorder = st.tabs(["📅 สรุปยอดรับ-จ่าย ประจำเดือน", "🛒 รายงานขอเบิก (ต่ำกว่าจุดสั่งซื้อ)"])

        with tab_summary:
            st.caption("รายงานสรุปยอดการรับเข้า เบิกจ่ายในแต่ละเดือน และยอดคงเหลือปัจจุบัน แยกตามรายการยา")

            df_trans = get_transactions_view()

            if not df_trans.empty:
                df_trans['created_at_dt'] = pd.to_datetime(df_trans['created_at'], utc=True).dt.tz_convert('Asia/Bangkok')
                df_trans['ym'] = df_trans['created_at_dt'].dt.strftime('%Y-%m')

                all_months = df_trans['ym'].dropna().unique().tolist()
                all_months.sort(reverse=True)

                if all_months:
                    month_opts = {ym: format_thai_month(ym) for ym in all_months}
                    selected_ym = st.selectbox("เลือกเดือนที่ต้องการดูรายงาน:", options=all_months, format_func=lambda x: month_opts[x])

                    st.divider()
                    st.subheader(f"รายงานประจำเดือน: {format_thai_month(selected_ym)}")

                    df_month = df_trans[df_trans['ym'] == selected_ym]

                    df_recv = df_month[df_month['action_type'] == 'RECEIVE'].groupby('medicine_id')['qty_change'].sum().reset_index()
                    df_recv.rename(columns={'qty_change': 'receive_qty'}, inplace=True)

                    df_disp = df_month[df_month['action_type'] == 'DISPENSE'].groupby('medicine_id')['qty_change'].sum().reset_index()
                    df_disp['qty_change'] = df_disp['qty_change'].abs()
                    df_disp.rename(columns={'qty_change': 'dispense_qty'}, inplace=True)

                    inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
                    if not inv.empty:
                        inv_agg = inv.groupby('medicine_id')['qty'].sum().reset_index()
                    else:
                        inv_agg = pd.DataFrame(columns=['medicine_id', 'qty'])

                    meds = get_medicines()

                    if not meds.empty:
                        report = pd.merge(meds[['id', 'generic_name', 'unit', 'min_stock']], df_recv, left_on='id', right_on='medicine_id', how='left')
                        report = pd.merge(report, df_disp, left_on='id', right_on='medicine_id', how='left')
                        report = pd.merge(report, inv_agg, left_on='id', right_on='medicine_id', how='left')

                        report['receive_qty'] = report['receive_qty'].fillna(0).astype(int)
                        report['dispense_qty'] = report['dispense_qty'].fillna(0).astype(int)
                        report['qty'] = report['qty'].fillna(0).astype(int)
                        report['min_stock'] = report['min_stock'].fillna(0).astype(int)

                        report_display = report[['generic_name', 'unit', 'min_stock', 'receive_qty', 'dispense_qty', 'qty']].copy()
                        report_display.insert(0, 'ลำดับ', range(1, len(report_display) + 1))
                        
                        report_display.columns = ['ลำดับ', 'รายการ', 'หน่วยนับ', 'จุดสั่งซื้อ', 'รับมา', 'เบิกจ่าย', 'คงเหลือ']

                        st.dataframe(report_display, use_container_width=True, hide_index=True)

                        csv = report_display.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="ดาวน์โหลดรายงาน (CSV)",
                            data=csv,
                            file_name=f'Summary_Report_{selected_ym}.csv',
                            mime='text/csv'
                        )
                    else:
                        st.warning("ไม่พบข้อมูลเวชภัณฑ์ในระบบ")
                else:
                    st.info("ยังไม่มีข้อมูลในเดือนที่เลือก")
            else:
                st.info("ยังไม่มีประวัติการทำรายการรับ-จ่ายในระบบ")

        with tab_reorder:
            st.subheader("🛒 รายงานขอเบิกเวชภัณฑ์ (Re-order Report)")
            st.caption("แสดงเฉพาะรายการที่ 'จำนวนคงเหลือ' ต่ำกว่าหรือเท่ากับ 'จุดสั่งซื้อ'")
            
            meds = get_medicines()
            if not meds.empty:
                inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
                if not inv.empty:
                    inv_agg = inv.groupby('medicine_id')['qty'].sum().reset_index()
                    df_reorder = pd.merge(meds, inv_agg, left_on='id', right_on='medicine_id', how='left')
                    df_reorder['qty'] = df_reorder['qty'].fillna(0).astype(int)
                else:
                    df_reorder = meds.copy()
                    df_reorder['qty'] = 0

                df_reorder = df_reorder[df_reorder['qty'] <= df_reorder['min_stock']].copy()

                if not df_reorder.empty:
                    df_reorder['suggested_reorder'] = df_reorder['min_stock']

                    df_display_reorder = df_reorder[['generic_name', 'unit', 'min_stock', 'qty', 'suggested_reorder']].copy()
                    df_display_reorder.insert(0, 'ลำดับ', range(1, len(df_display_reorder) + 1))
                    
                    df_display_reorder.columns = ['ลำดับ', 'รายการ', 'หน่วยนับ', 'อัตราใช้ต่อเดือน', 'จำนวนคงเหลือ', 'จำนวนขอเบิก']

                    st.dataframe(df_display_reorder, use_container_width=True, hide_index=True)

                    st.divider()
                    
                    buffer = io.BytesIO()
                    try:
                        df_display_reorder.to_excel(buffer, index=False, sheet_name='ใบขอเบิก')
                        st.download_button(
                            label="📥 ดาวน์โหลดไฟล์ Excel (.xlsx)",
                            data=buffer.getvalue(),
                            file_name=f"ใบขอเบิกเวชภัณฑ์_{datetime.date.today().strftime('%Y_%m_%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )
                    except Exception as e:
                        csv_reorder = df_display_reorder.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 ดาวน์โหลดไฟล์ขอเบิก (CSV รองรับ Excel)",
                            data=csv_reorder,
                            file_name=f"ใบขอเบิกเวชภัณฑ์_{datetime.date.today().strftime('%Y_%m_%d')}.csv",
                            mime="text/csv",
                            type="primary"
                        )
                else:
                    st.success("✅ ยอดคงคลังเพียงพอทุกรายการ ยังไม่มีรายการที่ต้องออกใบขอเบิกในขณะนี้ครับ")
            else:
                st.warning("ไม่พบข้อมูลเวชภัณฑ์ในระบบ")

    # ----------------------------------------------------------------------
    # 🧾 ประวัติรับ-จ่าย (ตารางคลิกได้)
    # ----------------------------------------------------------------------
    elif menu == "🧾 ประวัติรับ-จ่าย":
        st.header("🧾 ประวัติการรับและเบิกจ่ายเวชภัณฑ์")
        st.info("💡 **วิธีแก้ไขหรือลบ:** ให้ใช้เมาส์ **'คลิกที่แถวของตาราง'** ที่ต้องการแก้ไขได้เลยครับ ฟอร์มจัดการจะโผล่ขึ้นมาด้านล่างทันที")
        
        df_trans = get_transactions_view()
        if not df_trans.empty:
            df_trans['created_at_dt'] = pd.to_datetime(df_trans['created_at'], utc=True).dt.tz_convert('Asia/Bangkok')
            df_trans['ym'] = df_trans['created_at_dt'].dt.strftime('%Y-%m')
            df_trans['created_at_str'] = df_trans['created_at_dt'].dt.strftime('%d/%m/%Y %H:%M:%S')
            df_trans['action_type_th'] = df_trans['action_type'].map({'RECEIVE': 'รับเข้า', 'DISPENSE': 'เบิกจ่าย', 'INITIAL': 'ยอดยกมา'}).fillna(df_trans['action_type'])
            
            df_trans['qty_change_str'] = df_trans['qty_change'].apply(lambda x: f"+{x}" if x > 0 else str(x))
            
            c1, c2 = st.columns([1, 1])
            with c1:
                filter_action = st.radio("ตัวกรองประเภท:", ["แสดงทั้งหมด", "เฉพาะรับเข้า", "เฉพาะเบิกจ่าย"], horizontal=True)
            with c2:
                all_months = df_trans['ym'].dropna().unique().tolist()
                all_months.sort(reverse=True)
                month_opts = {"ทั้งหมด": "ดูทุกเดือน (All Time)"}
                for ym in all_months: month_opts[ym] = format_thai_month(ym)
                selected_ym = st.selectbox("เลือกเดือนที่ต้องการแสดงผล:", options=["ทั้งหมด"] + all_months, format_func=lambda x: month_opts[x])
            
            df_display = df_trans.copy()
            if filter_action == "เฉพาะรับเข้า": df_display = df_display[df_display['action_type'] == 'RECEIVE']
            elif filter_action == "เฉพาะเบิกจ่าย": df_display = df_display[df_display['action_type'] == 'DISPENSE']
            if selected_ym != "ทั้งหมด": df_display = df_display[df_display['ym'] == selected_ym]
            
            df_view = df_display[['created_at_str', 'action_type_th', 'generic_name', 'lot_no', 'qty_change_str', 'unit', 'user_name', 'note']].copy()
            df_view.columns = ['วัน-เวลา', 'ประเภท', 'รายการยา', 'เลข Lot', 'จำนวน (+/-)', 'หน่วย', 'ผู้บันทึก', 'หมายเหตุ']
            
            event = st.dataframe(
                df_view, 
                use_container_width=True, 
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun"
            )
            
            if len(event.selection.rows) > 0:
                selected_idx = event.selection.rows[0]
                selected_row = df_display.iloc[selected_idx]
                
                st.divider()
                st.subheader("⚙️ จัดการประวัติ (รายการที่เลือก)")
                
                recorder_name = st.session_state.full_name if st.session_state.full_name else st.session_state.user_email
                
                can_edit = False
                if st.session_state.role == 'admin':
                    can_edit = True
                    st.caption("👑 **สิทธิ์ Admin:** สามารถจัดการได้ทุกรายการ")
                elif selected_row['user_name'] == recorder_name:
                    can_edit = True
                    st.caption(f"👤 **สิทธิ์ Staff:** จัดการรายการของคุณ {recorder_name}")
                else:
                    st.error(f"❌ คุณไม่มีสิทธิ์แก้ไขรายการนี้ (ผู้บันทึกคือ: {selected_row['user_name']}) แอดมินหรือเจ้าของรายการเท่านั้นที่ทำได้")
                
                if can_edit:
                    trans_id = str(selected_row['id'])
                    med_id = str(selected_row['medicine_id'])
                    lot_no = str(selected_row['lot_no'])
                    old_qty_change = int(selected_row['qty_change'])
                    action_type = selected_row['action_type']
                    
                    with st.form("edit_delete_trans_form"):
                        st.markdown(f"**รายการ:** {selected_row['generic_name']} (Lot: `{lot_no}`) | **ประเภท:** {selected_row['action_type_th']}")
                        
                        c1, c2 = st.columns(2)
                        
                        if action_type == 'RECEIVE':
                            new_abs_qty = c1.number_input("จำนวนรับเข้า (ชิ้น)", min_value=1, value=abs(old_qty_change))
                            new_qty_change = new_abs_qty
                        elif action_type == 'DISPENSE':
                            new_abs_qty = c1.number_input("จำนวนเบิกจ่าย (ชิ้น)", min_value=1, value=abs(old_qty_change))
                            new_qty_change = -new_abs_qty
                        else:
                            st.info("ยอดยกมาเริ่มต้น ไม่สามารถแก้ไขจำนวนได้ (ลบได้อย่างเดียว)")
                            new_qty_change = old_qty_change
                            
                        new_note = c2.text_input("หมายเหตุ", value=str(selected_row['note']) if pd.notna(selected_row['note']) else "")
                        
                        st.warning("⚠️ การอัปเดตหรือลบ จะมีการคำนวณปรับยอดในคลังให้อัตโนมัติ")
                        confirm_del = st.checkbox("กดยืนยันหากต้องการ **ลบ** รายการนี้ทิ้งถาวร (คืนยอดเข้าคลัง)")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        submit_edit = col_btn1.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True)
                        submit_delete = col_btn2.form_submit_button("❌ ลบรายการนี้", type="primary", use_container_width=True)
                        
                        if submit_edit:
                            if action_type == 'INITIAL' and new_qty_change != old_qty_change:
                                st.error("ไม่สามารถแก้ไขจำนวนของยอดยกมาได้")
                            else:
                                try:
                                    if new_qty_change != old_qty_change:
                                        qty_diff = new_qty_change - old_qty_change
                                        inv_res = supabase.table("inventory").select("*").eq("medicine_id", med_id).eq("lot_no", lot_no).execute()
                                        
                                        if inv_res.data:
                                            current_inv_qty = inv_res.data[0]['qty']
                                            inv_id = inv_res.data[0]['id']
                                            new_inv_qty = current_inv_qty + qty_diff
                                            
                                            if new_inv_qty < 0:
                                                st.error("❌ แก้ไขไม่ได้: การลดรับเข้า หรือเพิ่มเบิกจ่ายนี้ จะทำให้สต๊อกติดลบ!")
                                                st.stop()
                                                
                                            supabase.table("inventory").update({"qty": new_inv_qty}).eq("id", inv_id).execute()
                                        else:
                                            st.warning("ไม่พบ Lot นี้ในคลัง ทำการอัปเดตเฉพาะประวัติ")
                                            
                                    supabase.table("transactions").update({
                                        "qty_change": new_qty_change,
                                        "note": new_note
                                    }).eq("id", trans_id).execute()
                                    
                                    st.success("✅ อัปเดตประวัติและปรับยอดในคลังสำเร็จ!")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"เกิดข้อผิดพลาดในการอัปเดต: {e}")
                                
                        if submit_delete:
                            if confirm_del:
                                try:
                                    inv_res = supabase.table("inventory").select("*").eq("medicine_id", med_id).eq("lot_no", lot_no).execute()
                                    if inv_res.data:
                                        current_inv_qty = inv_res.data[0]['qty']
                                        inv_id = inv_res.data[0]['id']
                                        new_inv_qty = current_inv_qty - old_qty_change 
                                        
                                        if new_inv_qty < 0:
                                            st.error("❌ ลบไม่ได้: การลบรายการรับเข้านี้ จะทำให้สต๊อกคงเหลือในคลังติดลบ!")
                                            st.stop()
                                            
                                        supabase.table("inventory").update({"qty": new_inv_qty}).eq("id", inv_id).execute()
                                        
                                    supabase.table("transactions").delete().eq("id", trans_id).execute()
                                    st.success("✅ ลบประวัติและคืนยอดเข้าคลังสำเร็จ!")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"เกิดข้อผิดพลาดในการลบ: {e}")
                            else:
                                st.error("กรุณาติ๊กกล่องสี่เหลี่ยม 'กดยืนยัน' ก่อนทำการลบรายการ")

        else: st.info("ยังไม่มีประวัติการทำรายการในระบบ")

    # ----------------------------------------------------------------------
    # 🗃️ สต๊อกการ์ด
    # ----------------------------------------------------------------------
    elif menu == "🗃️ สต๊อกการ์ด":
        st.header("🗃️ บัญชีคุมสินค้าคงคลัง (Stock Card)")
        
        meds = get_medicines()
        if not meds.empty:
            med_options = meds['id'] + " | " + meds['generic_name'] + " (" + meds['unit'] + ")"
            selected_med = st.selectbox("ค้นหาและเลือกรายการเวชภัณฑ์ที่ต้องการดูประวัติ:", med_options)
            
            if selected_med:
                selected_id = selected_med.split(" | ")[0]
                selected_name = selected_med.split(" | ")[1].split(" (")[0]
                selected_unit = meds[meds['id'] == selected_id]['unit'].values[0]
                
                t_res = supabase.table("transactions").select("*").eq("medicine_id", selected_id).order("created_at", desc=False).execute()
                df_t = pd.DataFrame(t_res.data)
                i_res = supabase.table("inventory").select("lot_no, exp_date, qty").eq("medicine_id", selected_id).execute()
                df_i = pd.DataFrame(i_res.data)

                if not df_t.empty:
                    if not df_i.empty:
                        df_i_unique = df_i.drop_duplicates(subset=['lot_no'])[['lot_no', 'exp_date']]
                        df_t = pd.merge(df_t, df_i_unique, on='lot_no', how='left')
                    else: df_t['exp_date'] = '-'

                    df_t = df_t.sort_values(by='created_at', ascending=True)
                    df_t['running_balance'] = df_t['qty_change'].cumsum()
                    df_t = df_t.sort_values(by='created_at', ascending=False)
                    
                    df_t['created_at_dt'] = pd.to_datetime(df_t['created_at'], utc=True).dt.tz_convert('Asia/Bangkok')
                    df_t['ym'] = df_t['created_at_dt'].dt.strftime('%Y-%m')
                    df_t['created_at_str'] = df_t['created_at_dt'].dt.strftime('%d/%m/%Y %H:%M')
                    df_t['action_type_th'] = df_t['action_type'].map({'RECEIVE': 'รับเข้า', 'DISPENSE': 'เบิกจ่าย', 'INITIAL': 'ยอดยกมา'}).fillna(df_t['action_type'])
                    
                    df_t['qty_change_str'] = df_t['qty_change'].apply(lambda x: f"+{x}" if x > 0 else str(x))
                    
                    all_months_sc = df_t['ym'].dropna().unique().tolist()
                    all_months_sc.sort(reverse=True)
                    month_opts_sc = {"ทั้งหมด": "ดูทุกรอบเดือน (All Time)"}
                    for ym in all_months_sc: month_opts_sc[ym] = format_thai_month(ym)
                    
                    selected_ym_sc = st.selectbox("เลือกดูประวัติเฉพาะเดือน:", options=["ทั้งหมด"] + all_months_sc, format_func=lambda x: month_opts_sc[x])
                    
                    if selected_ym_sc != "ทั้งหมด": df_show = df_t[df_t['ym'] == selected_ym_sc].copy()
                    else: df_show = df_t.copy()
                    
                    cols = ['created_at_str', 'action_type_th', 'lot_no', 'exp_date', 'qty_change_str', 'running_balance', 'user_name', 'note']
                    df_show = df_show[cols]
                    df_show.columns = ['วัน-เวลา', 'ประเภท', 'เลข Lot', 'วันหมดอายุ', 'จำนวนรับ/จ่าย', f'ยอดคงเหลือ ({selected_unit})', 'ผู้บันทึก', 'หมายเหตุ']
                    
                    st.markdown(f"**ประวัติความเคลื่อนไหว: {selected_name}**")
                    if not df_show.empty: st.dataframe(df_show, use_container_width=True, hide_index=True)
                    else: st.info(f"ไม่พบประวัติการเคลื่อนไหวในเดือนที่เลือก")
                else: st.info(f"ยังไม่มีประวัติการรับ-จ่าย ของเวชภัณฑ์ {selected_name}")

                st.divider()
                st.subheader(f"สรุปยอดคงเหลือปัจจุบัน")
                if not df_i.empty:
                    df_i_active = df_i[df_i['qty'] > 0]
                    if not df_i_active.empty:
                        total_current = df_i_active['qty'].sum()
                        st.metric(f"รวมทั้งสิ้น ({selected_name})", f"{total_current:,} {selected_unit}")
                        st.dataframe(df_i_active[['lot_no', 'exp_date', 'qty']].rename(columns={'lot_no': 'เลข Lot', 'exp_date': 'วันหมดอายุ', 'qty': f'คงเหลือ ({selected_unit})'}), hide_index=True)
                    else: st.warning("ยอดเวชภัณฑ์ในคลังเป็น 0")
                else: st.warning("ไม่มีข้อมูลในคลัง (ยอดยกเป็น 0)")
        else:
            st.info("ยังไม่มีข้อมูลเวชภัณฑ์ในระบบ")

    # ----------------------------------------------------------------------
    # 📤 เบิกจ่ายยา (Dispense)
    # ----------------------------------------------------------------------
    elif menu == "📤 เบิกจ่ายยา (Dispense)":
        st.header("📤 การเบิกจ่ายเวชภัณฑ์ (Dispense)")
        df_inv = get_inventory_view()
        if not df_inv.empty:
            df_inv['display_label'] = df_inv['generic_name'] + " | Lot: " + df_inv['lot_no'] + " | หมดอายุ: " + df_inv['exp_date'].astype(str) + " (เหลือ " + df_inv['qty'].astype(str) + " " + df_inv['unit'] + ")"
            st.info("💡 สามารถค้นหาและเลือกเวชภัณฑ์ได้หลายรายการพร้อมกัน เพื่อความรวดเร็วในการเบิกจ่าย")
            selected_labels = st.multiselect("ค้นหาและเลือกรายการเวชภัณฑ์ (เลือกได้มากกว่า 1 ล็อต)", df_inv['display_label'].tolist())
            
            if selected_labels:
                st.divider()
                st.subheader("ระบุจำนวนที่ต้องการเบิกจ่าย")
                with st.form("bulk_dispense_form"):
                    dispense_data = []
                    for i, label in enumerate(selected_labels):
                        row = df_inv[df_inv['display_label'] == label].iloc[0]
                        st.markdown(f'<div class="item-box">', unsafe_allow_html=True)
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{row['generic_name']}**")
                            st.caption(f"Lot: `{row['lot_no']}` | คงเหลือ: {row['qty']} {row['unit']}")
                        with col2:
                            amount = st.number_input(f"จำนวนที่เบิก ({row['unit']})", min_value=1, max_value=int(row['qty']), key=f"disp_{i}")
                        st.markdown('</div>', unsafe_allow_html=True)
                        dispense_data.append({
                            'inventory_id': row['id'], 'medicine_id': row['medicine_id'],
                            'lot_no': row['lot_no'], 'current_qty': int(row['qty']), 'dispense_qty': amount
                        })
                        
                    note = st.text_input("หมายเหตุ (เช่น เบิกให้แผนก ER, รพ.สต.เครือข่าย)", value="จ่ายหน้างาน")
                    recorder_name = st.session_state.full_name if st.session_state.full_name else st.session_state.user_email
                    st.caption(f"ผู้บันทึกการเบิกจ่าย: {recorder_name}")
                    
                    if st.form_submit_button("ยืนยันการเบิกจ่าย", use_container_width=True):
                        try:
                            for data in dispense_data:
                                new_qty = data['current_qty'] - data['dispense_qty']
                                supabase.table("inventory").update({"qty": new_qty}).eq("id", data['inventory_id']).execute()
                                supabase.table("transactions").insert({
                                    "medicine_id": data['medicine_id'], "action_type": "DISPENSE",
                                    "qty_change": -data['dispense_qty'], "lot_no": data['lot_no'],
                                    "user_name": recorder_name, "note": note
                                }).execute()
                            st.success("บันทึกการเบิกจ่ายสำเร็จ!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"เกิดข้อผิดพลาดจากฐานข้อมูล: {e}")

    # ----------------------------------------------------------------------
    # 📥 รับยาเข้า (Receive)
    # ----------------------------------------------------------------------
    elif menu == "📥 รับยาเข้า (Receive)":
        st.header("📥 การรับเวชภัณฑ์เข้าคลัง (Receive)")
        meds = get_medicines()
        med_options = meds['id'] + " | " + meds['generic_name'] + " (" + meds['unit'] + ")"
        
        num_items = st.number_input("จำนวนรายการเวชภัณฑ์ที่ต้องการรับเข้าพร้อมกัน", min_value=1, max_value=20, value=1)
        st.divider()
        
        with st.form("bulk_receive_form"):
            receive_data = []
            for i in range(int(num_items)):
                st.markdown(f"**รายการที่ {i+1}**")
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                with c1: d_choice = st.selectbox("เลือกเวชภัณฑ์", med_options, key=f"med_{i}")
                with c2: lot = st.text_input("รหัส Lot", key=f"lot_{i}")
                with c3: mfg = st.date_input("วันผลิต", key=f"mfg_{i}")
                with c4: exp = st.date_input("วันหมดอายุ", key=f"exp_{i}")
                
                selected_id = d_choice.split(" | ")[0]
                qty = st.number_input("จำนวนที่รับเข้า", min_value=1, key=f"qty_{i}")
                st.markdown("---")
                
                final_lot = lot if lot.strip() != "" else "-"
                
                receive_data.append({
                    "medicine_id": selected_id, "lot_no": final_lot,
                    "mfg_date": str(mfg), "exp_date": str(exp), "qty": qty
                })
                
            receive_note = st.text_input("หมายเหตุ (สามารถแก้ไขได้)", value="รับเข้า (Receive)")
            recorder_name = st.session_state.full_name if st.session_state.full_name else st.session_state.user_email
            st.caption(f"ผู้บันทึกการรับเข้า: {recorder_name}")
            
            if st.form_submit_button("บันทึกรับเข้าคลัง", use_container_width=True):
                try:
                    for data in receive_data:
                        supabase.table("inventory").insert(data).execute()
                        supabase.table("transactions").insert({
                            "medicine_id": data['medicine_id'], "action_type": "RECEIVE", "qty_change": data['qty'],
                            "lot_no": data['lot_no'], "user_name": recorder_name, "note": receive_note 
                        }).execute()
                    st.success("บันทึกรับเข้าสำเร็จ!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")
                    st.info("คำแนะนำ: โปรดตรวจสอบว่ารหัส Lot มีการซ้ำซ้อนในระบบหรือไม่")

    # ----------------------------------------------------------------------
    # 📋 ข้อมูลยา (Master Data)
    # ----------------------------------------------------------------------
    elif menu == "📋 ข้อมูลยา (Master Data)":
        st.header("📋 จัดการข้อมูลเวชภัณฑ์หลัก (Master Data)")
        
        tab1, tab2, tab3 = st.tabs(["📄 รายการที่มีอยู่", "📝 เพิ่มรายการใหม่", "⚙️ แก้ไข / ลบข้อมูล"])
        
        with tab1:
            st.info("แสดงเฉพาะรายการเวชภัณฑ์ที่เปิดใช้งานอยู่ (Active) ในระบบ")
            st.dataframe(get_medicines(), use_container_width=True)

        with tab2:
            with st.form("new_med"):
                c1, c2 = st.columns(2)
                nid = c1.text_input("รหัสเวชภัณฑ์ (เช่น DRUG009)")
                nname = c2.text_input("ชื่อสามัญ (Generic Name)")
                nunit = c1.text_input("หน่วยนับ (เช่น เม็ด, ขวด, หลอด)")
                ncat = c2.selectbox("หมวดหมู่", ["ยาในบัญชี", "ยานอกบัญชี", "เวชภัณฑ์/วัสดุ"])
                nmin = st.number_input("จุดสั่งซื้อ (Min Stock) เพื่อแจ้งเตือนเมื่อใกล้หมด", min_value=0, value=100)
                
                if st.form_submit_button("บันทึกรายการใหม่", use_container_width=True):
                    if nid and nname and nunit:
                        try:
                            supabase.table("medicines").insert({"id": nid, "generic_name": nname, "unit": nunit, "category": ncat, "min_stock": nmin, "is_active": True}).execute()
                            st.success("เพิ่มข้อมูลสำเร็จ!"); time.sleep(1); st.rerun()
                        except: st.error("รหัสเวชภัณฑ์ซ้ำ หรือกรอกข้อมูลไม่ถูกต้อง")
                    else: st.warning("กรุณากรอกรหัส ชื่อเวชภัณฑ์ และหน่วยนับให้ครบถ้วน")
                        
        with tab3:
            all_meds_data = supabase.table("medicines").select("*").execute().data
            if all_meds_data:
                all_meds = pd.DataFrame(all_meds_data)
                
                all_meds['display_name'] = all_meds['id'].astype(str) + " | " + all_meds['generic_name'].fillna('-ไม่มีชื่อยา-').astype(str)
                
                edit_choice = st.selectbox("ค้นหาและเลือกรายการที่ต้องการแก้ไข หรือ ลบ:", all_meds['display_name'])
                
                if edit_choice:
                    selected_id = edit_choice.split(" | ")[0]
                    med_info = all_meds[all_meds['id'] == selected_id].iloc[0]
                    
                    st.divider()
                    
                    with st.form("edit_med_form"):
                        st.caption(f"รหัสเวชภัณฑ์: {selected_id} (ไม่สามารถแก้ไขรหัสได้)")
                        c1, c2 = st.columns(2)
                        
                        old_name = "" if pd.isna(med_info['generic_name']) else med_info['generic_name']
                        e_name = c1.text_input("ชื่อสามัญ (Generic Name)", value=old_name)
                        
                        old_unit = "" if pd.isna(med_info['unit']) else med_info['unit']
                        e_unit = c2.text_input("หน่วยนับ", value=old_unit)
                        
                        cat_options = ["ยาในบัญชี", "ยานอกบัญชี", "เวชภัณฑ์/วัสดุ"]
                        try: cat_idx = cat_options.index(med_info['category'])
                        except: cat_idx = 0
                        e_cat = c1.selectbox("หมวดหมู่", cat_options, index=cat_idx)
                        
                        min_stock_val = 0 if pd.isna(med_info.get('min_stock')) else int(med_info.get('min_stock', 0))
                        e_min = c2.number_input("จุดสั่งซื้อ (Min Stock)", min_value=0, value=min_stock_val)
                        e_active = st.checkbox("เปิดใช้งานรายการนี้ (นำไปรับ/เบิกได้ปกติ)", value=bool(med_info['is_active']))
                        
                        if st.form_submit_button("บันทึกการแก้ไข", use_container_width=True):
                            if e_name and e_unit:
                                try:
                                    supabase.table("medicines").update({"generic_name": e_name, "unit": e_unit, "category": e_cat, "min_stock": e_min, "is_active": e_active}).eq("id", selected_id).execute()
                                    st.success(f"อัปเดตข้อมูลของ {selected_id} สำเร็จ!"); time.sleep(1); st.rerun()
                                except Exception as e: st.error(f"เกิดข้อผิดพลาดในการอัปเดต: {e}")
                            else: st.warning("กรุณากรอกชื่อเวชภัณฑ์และหน่วยนับให้ครบถ้วน")
                    
                    st.divider()
                    st.markdown("#### ลบข้อมูลถาวร")
                    st.warning("แนะนำให้ใช้วิธี **'เอาเครื่องหมายถูกเปิดใช้งานออก'** แทนการลบ เพื่อเก็บประวัติไว้ตรวจสอบ (ระบบจะอนุญาตให้ลบถาวรได้ **เฉพาะรายการที่ไม่เคยมีประวัติรับ-จ่าย** เท่านั้น)")
                    
                    del_col1, del_col2 = st.columns([1, 1])
                    with del_col1:
                        confirm_del = st.checkbox("ยืนยันว่าต้องการลบรายการนี้ทิ้งถาวร", key="confirm_delete_box")
                    with del_col2:
                        if st.button("ลบรายการเวชภัณฑ์ถาวร", type="primary", use_container_width=True):
                            if confirm_del:
                                try:
                                    supabase.table("medicines").delete().eq("id", selected_id).execute()
                                    st.success(f"ลบรายการ {selected_id} ออกจากระบบเรียบร้อยแล้ว!")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error("ไม่สามารถลบได้! เนื่องจากรายการนี้เคยถูกทำรับ/เบิกไปแล้ว (กรุณาใช้วิธีปิดใช้งานแทน)")
                            else:
                                st.error("กรุณาติ๊กเครื่องหมายถูกที่ช่อง 'ยืนยัน' ก่อนกดปุ่มลบ")
            else: st.info("ยังไม่มีข้อมูลในระบบ")
