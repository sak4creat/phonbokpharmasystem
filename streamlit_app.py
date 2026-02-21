import streamlit as st
from supabase import create_client
import pandas as pd
import datetime
import time
import io
import os
import requests
import json

# --- 1. ตั้งค่าและเชื่อมต่อ (SETUP) ---
st.set_page_config(page_title="ระบบคลังยา รพ.สต. โพนบก", layout="wide", page_icon="🏥")

# 🌟 CSS จัดการสีปุ่ม (บันทึกสีฟ้า, ลบสีแดง)
st.markdown("""
<style>
    .stButton>button { 
        border-radius: 8px; 
        transition: all 0.3s ease; 
        border: 1px solid #e0e0e0; 
        font-weight: bold; 
    }
    .stButton>button:hover { 
        transform: scale(1.02); 
    }
    
    /* 🌟 สีฟ้าสำหรับปุ่ม Primary ทั่วไป (เช่น บันทึก) */
    button[kind="primary"] {
        background-color: #2e7bcf !important;
        border-color: #2e7bcf !important;
        color: white !important;
    }
    button[kind="primary"]:hover {
        background-color: #1c5a9e !important;
        border-color: #1c5a9e !important;
        color: white !important;
    }

    /* 🌟 ระบบดักจับเปลี่ยนสีปุ่ม "ลบ" ให้เป็นสีแดง */
    div.element-container:has(.red-btn-hook) {
        display: none !important;
    }
    div.element-container:has(.red-btn-hook) + div.element-container button {
        background-color: #e74c3c !important;
        border-color: #e74c3c !important;
        color: white !important;
    }
    div.element-container:has(.red-btn-hook) + div.element-container button:hover {
        background-color: #c0392b !important;
        border-color: #c0392b !important;
        color: white !important;
    }

    [data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); padding: 2rem; }
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
if 'reorder_manual_added' not in st.session_state: st.session_state.reorder_manual_added = []
if 'reorder_manual_removed' not in st.session_state: st.session_state.reorder_manual_removed = []
if 'reorder_quantities' not in st.session_state: st.session_state.reorder_quantities = {}

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
    st.session_state.reorder_manual_added = []
    st.session_state.reorder_manual_removed = []
    st.session_state.reorder_quantities = {}
    if "reorder_table" in st.session_state:
        del st.session_state["reorder_table"]
    st.rerun()

def get_medicines():
    return pd.DataFrame(supabase.table("medicines").select("*").eq("is_active", True).execute().data)

def get_inventory_view():
    meds = pd.DataFrame(supabase.table("medicines").select("id, generic_name, unit").execute().data)
    inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
    if inv.empty: return pd.DataFrame()
    merged = pd.merge(inv, meds, left_on="medicine_id", right_on="id", how="left", suffixes=('', '_med'))
    return merged[merged['qty'] > 0]

def map_user_names(df, col_name='user_name'):
    if df.empty or col_name not in df.columns: return df
    try:
        prof_res = supabase.table("profiles").select("email, full_name").execute()
        if prof_res.data:
            prof_df = pd.DataFrame(prof_res.data)
            valid_prof = prof_df[
                prof_df['full_name'].notna() & 
                (prof_df['full_name'].astype(str).str.strip() != '') & 
                (prof_df['full_name'].astype(str).str.strip() != 'None')
            ]
            
            email_to_name = {}
            for e, n in zip(valid_prof['email'], valid_prof['full_name']):
                clean_e = str(e).strip().lower()
                email_to_name[clean_e] = str(n).strip()
                
            def replace_name(val):
                if pd.isna(val): return val
                clean_val = str(val).strip().lower()
                if clean_val in email_to_name:
                    return email_to_name[clean_val]
                return val
                
            df[col_name] = df[col_name].apply(replace_name)
    except Exception as e:
        pass
    return df

def get_transactions_view():
    trans_response = supabase.table("transactions").select("*").order("created_at", desc=True).execute()
    meds_response = supabase.table("medicines").select("id, generic_name, unit").execute()
    trans = pd.DataFrame(trans_response.data)
    meds = pd.DataFrame(meds_response.data)
    if trans.empty: return pd.DataFrame()
    merged = pd.merge(trans, meds, left_on="medicine_id", right_on="id", how="left", suffixes=('', '_med'))
    return map_user_names(merged)

# 🌟 ฟังก์ชันส่ง LINE Messaging API
def send_line_message(token, target_id, message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "to": target_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        return response.status_code == 200
    except Exception as e:
        return False

# 🌟 ฟังก์ชันสร้างรายงานสรุป
def generate_monthly_executive_report():
    today = datetime.date.today()
    first_day_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_day_of_this_month - datetime.timedelta(days=1)
    first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
    
    month_name = THAI_MONTHS.get(last_day_of_prev_month.strftime('%m'))
    year_th = last_day_of_prev_month.year + 543
    report_title = f"📊 สรุปคลังเวชภัณฑ์ประจำเดือน {month_name} {year_th}"

    meds_res = supabase.table("medicines").select("id, generic_name, unit, min_stock, category").eq("is_active", True).execute()
    meds = pd.DataFrame(meds_res.data)
    inv_df = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
    trans_res = supabase.table("transactions").select("*").gte("created_at", str(first_day_of_prev_month)).lt("created_at", str(first_day_of_this_month)).execute()
    trans_df = pd.DataFrame(trans_res.data)

    if not meds.empty:
        meds['category'] = meds['category'].astype(str).str.strip() 
        drugs_count = len(meds[meds['category'].isin(['ยาในบัญชี', 'ยานอกบัญชี', 'เวชภัณฑ์ยา'])])
        supplies_count = len(meds[meds['category'].isin(['เวชภัณฑ์/วัสดุ', 'เวชภัณฑ์ที่มิใช่ยา'])])
    else:
        drugs_count, supplies_count = 0, 0

    msg_part1 = f"\n\n🏥 ข้อมูล ณ ปัจจุบัน:\n- เวชภัณฑ์ยา: {drugs_count} รายการ\n- เวชภัณฑ์มิใช่ยา: {supplies_count} รายการ"

    msg_part2 = "\n\n📥 รับเข้ามากที่สุด 5 อันดับ:"
    msg_part3 = "\n\n📤 เบิกจ่ายมากที่สุด 5 อันดับ:"
    if not trans_df.empty and not meds.empty:
        df_merged = pd.merge(trans_df, meds[['id', 'generic_name', 'unit']], left_on='medicine_id', right_on='id', how='left')
        df_recv = df_merged[df_merged['action_type'] == 'RECEIVE'].groupby('generic_name')['qty_change'].sum().reset_index()
        df_recv = df_recv.sort_values(by='qty_change', ascending=False).head(5)
        if not df_recv.empty:
            for idx, row in df_recv.iterrows():
                unit = meds[meds['generic_name'] == row['generic_name']]['unit'].values[0] if not meds[meds['generic_name'] == row['generic_name']].empty else ''
                msg_part2 += f"\n{idx+1}. {row['generic_name']} (+{int(row['qty_change'])} {unit})"
        else: msg_part2 += "\n(ไม่มีการเคลื่อนไหว)"

        df_disp = df_merged[df_merged['action_type'] == 'DISPENSE'].copy()
        df_disp['qty_change'] = df_disp['qty_change'].abs() 
        df_disp = df_disp.groupby('generic_name')['qty_change'].sum().reset_index()
        df_disp = df_disp.sort_values(by='qty_change', ascending=False).head(5)
        if not df_disp.empty:
            for idx, row in df_disp.iterrows():
                unit = meds[meds['generic_name'] == row['generic_name']]['unit'].values[0] if not meds[meds['generic_name'] == row['generic_name']].empty else ''
                msg_part3 += f"\n{idx+1}. {row['generic_name']} (-{int(row['qty_change'])} {unit})"
        else: msg_part3 += "\n(ไม่มีการเคลื่อนไหว)"
    else:
        msg_part2 += "\n(ไม่มีการเคลื่อนไหว)"
        msg_part3 += "\n(ไม่มีการเคลื่อนไหว)"

    msg_part4 = "\n\n⚠️ แจ้งเตือน: ต่ำกว่าจุดสั่งซื้อ"
    low_total = 0
    low_drugs = 0
    low_supplies = 0
    low_stock = pd.DataFrame()

    if not meds.empty:
        if not inv_df.empty:
            inv_agg = inv_df.groupby('medicine_id')['qty'].sum().reset_index()
            df_stock = pd.merge(meds, inv_agg, left_on='id', right_on='medicine_id', how='left')
        else:
            df_stock = meds.copy()
            df_stock['qty'] = 0
            
        df_stock['qty'] = pd.to_numeric(df_stock['qty'], errors='coerce').fillna(0)
        df_stock['min_stock'] = pd.to_numeric(df_stock['min_stock'], errors='coerce').fillna(0)
        df_stock['category'] = df_stock['category'].astype(str).str.strip()
            
        low_stock = df_stock[df_stock['qty'] <= df_stock['min_stock']]
        low_total = len(low_stock)
        low_drugs = len(low_stock[low_stock['category'].isin(['ยาในบัญชี', 'ยานอกบัญชี', 'เวชภัณฑ์ยา'])])
        low_supplies = len(low_stock[low_stock['category'].isin(['เวชภัณฑ์/วัสดุ', 'เวชภัณฑ์ที่มิใช่ยา'])])

        msg_part4 += f"\nรวมทั้งหมด {low_total} รายการ แบ่งเป็น:"
        msg_part4 += f"\n💊 เวชภัณฑ์ยา จำนวน {low_drugs} รายการ"
        msg_part4 += f"\n📦 เวชภัณฑ์ที่มิใช่ยา จำนวน {low_supplies} รายการ\n"

        if low_total > 0:
            for _, row in low_stock.head(10).iterrows():
                msg_part4 += f"\n- {row['generic_name']}: เหลือ {int(row['qty'])} (เป้า: {int(row['min_stock'])})"
            if low_total > 10: 
                msg_part4 += f"\n...และอื่นๆ อีก {low_total-10} รายการ"
    else:
        msg_part4 += "\n(ไม่มีข้อมูล Master Data)"

    msg_part5 = "\n\n⏰ แจ้งเตือน: ใกล้หมดอายุ (<90 วัน)"
    if not inv_df.empty:
        inv_active = inv_df[inv_df['qty'] > 0].copy()
        if not inv_active.empty:
            inv_active['exp_date'] = pd.to_datetime(inv_active['exp_date'])
            near_exp_raw = inv_active[inv_active['exp_date'] <= pd.to_datetime(today) + pd.Timedelta(days=90)]
            
            if not near_exp_raw.empty:
                near_exp = pd.merge(near_exp_raw, meds[['id', 'generic_name']], left_on='medicine_id', right_on='id', how='left')
                msg_part5 += f" ({len(near_exp)} ล็อต)"
                for _, row in near_exp.head(10).iterrows():
                    exp_str = row['exp_date'].strftime('%d/%m/%Y')
                    msg_part5 += f"\n- {row['generic_name']} (Lot: {row['lot_no']})\n  เหลือ {int(row['qty'])} | หมด: {exp_str}"
                if len(near_exp) > 10:
                     msg_part5 += f"\n...และอื่นๆ อีก {len(near_exp)-10} ล็อต"
            else: msg_part5 += "\n(ไม่มีรายการเสี่ยงหมดอายุ)"
        else: msg_part5 += "\n(ไม่มีรายการเสี่ยงหมดอายุ)"
    else: msg_part5 += "\n(ไม่มีข้อมูลสต๊อก)"

    final_message = report_title + msg_part1 + msg_part2 + msg_part3 + msg_part4 + msg_part5
    return final_message

# --- 4. ส่วนหน้าจอ (FRONTEND) ---
if not st.session_state.user:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
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
        "📥 รับเข้า (Receive)", 
        "📤 เบิกจ่าย (Dispense)", 
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
        
        tab_manage, tab_add, tab_delete, tab_line = st.tabs(["👥 จัดการข้อมูลผู้ใช้ / อนุมัติ", "➕ สร้างผู้ใช้ใหม่", "🗑️ ลบบัญชีผู้ใช้", "📱 ตั้งค่ารายงาน LINE"])
        
        with tab_manage:
            profiles = pd.DataFrame(supabase.table("profiles").select("*").execute().data)
            if not profiles.empty:
                profiles_view = profiles.copy()
                profiles_view['status'] = profiles_view['is_approved'].map({True: 'อนุมัติแล้ว', False: 'รออนุมัติ'})
                cols_to_show = ['email', 'full_name', 'role', 'status', 'created_at']
                existing_cols = [c for c in cols_to_show if c in profiles_view.columns]
                st.dataframe(profiles_view[existing_cols], use_container_width=True)
                
                st.divider()
                col_m1, col_m2 = st.columns(2)
                
                with col_m1:
                    st.subheader("✅ จัดการคำขอใช้งาน")
                    pending_users = profiles[profiles['is_approved'] == False]
                    if not pending_users.empty:
                        user_to_approve = st.selectbox("เลือกผู้ใช้เพื่ออนุมัติ", pending_users['email'])
                        c1, c2 = st.columns(2)
                        if c1.button("อนุมัติให้เป็น Staff", use_container_width=True):
                            supabase.table("profiles").update({"is_approved": True}).eq("email", user_to_approve).execute()
                            st.success("อนุมัติเรียบร้อย!"); time.sleep(1); st.rerun()
                        if c2.button("แต่งตั้งเป็น Admin", use_container_width=True):
                            supabase.table("profiles").update({"is_approved": True, "role": "admin"}).eq("email", user_to_approve).execute()
                            st.success("แต่งตั้งเป็น Admin เรียบร้อย!"); time.sleep(1); st.rerun()
                    else: st.info("ไม่มีคำขอรออนุมัติ")
                    
                with col_m2:
                    st.subheader("✏️ แก้ไขสิทธิ์และชื่อผู้ใช้งาน")
                    user_to_edit_email = st.selectbox("เลือกผู้ใช้ที่ต้องการแก้ไข", profiles['email'].tolist())
                    if user_to_edit_email:
                        selected_user = profiles[profiles['email'] == user_to_edit_email].iloc[0]
                        with st.form("edit_user_profile_form"):
                            current_name = selected_user['full_name'] if pd.notna(selected_user['full_name']) else ""
                            new_name = st.text_input("ชื่อ - นามสกุล", value=current_name)
                            
                            current_role = selected_user['role']
                            role_options = ["staff", "admin"]
                            try: role_idx = role_options.index(current_role)
                            except: role_idx = 0
                            new_role = st.selectbox("สิทธิ์การใช้งาน (Role)", role_options, index=role_idx)
                            
                            if st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True):
                                try:
                                    supabase.table("profiles").update({
                                        "full_name": new_name,
                                        "role": new_role
                                    }).eq("id", selected_user['id']).execute()
                                    st.success(f"✅ อัปเดตข้อมูลของ {user_to_edit_email} เรียบร้อยแล้ว!")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
            else: st.info("ไม่มีผู้ใช้งานในระบบ")
                
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
                    
                    # บังคับปุ่มลบผู้ใช้เป็นสีแดง
                    st.markdown('<div class="red-btn-hook"></div>', unsafe_allow_html=True)
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
                    
        with tab_line:
            st.subheader("📱 ทดสอบส่งรายงานบทสรุปผู้บริหารเข้า LINE")
            st.info("ใช้ระบบ LINE Messaging API (LINE Official Account)")
            
            line_token_input = st.text_input("1. LINE Channel Access Token (จากแท็บ Messaging API)", type="password")
            line_target_id = st.text_input("2. LINE User ID หรือ Group ID ปลายทาง (เช่น U1a2b3c...)", type="password")
            
            if st.button("🚀 จำลองการส่งรายงานสรุปของเดือนที่แล้วเข้า LINE", type="primary"):
                if line_token_input and line_target_id:
                    with st.spinner("กำลังรวบรวมข้อมูลและสร้างรายงาน..."):
                        report_text = generate_monthly_executive_report()
                        success = send_line_message(line_token_input, line_target_id, report_text)
                        
                        if success:
                            st.success("✅ ส่งรายงานเข้า LINE สำเร็จ! ลองเช็กในแอป LINE ของคุณดูครับ")
                            with st.expander("ดูตัวอย่างข้อความที่ถูกส่งไป"):
                                st.text(report_text)
                        else:
                            st.error("❌ ส่งไม่สำเร็จ! กรุณาตรวจสอบว่า Token และ User ID ถูกต้องหรือไม่ (หรือบอทยังไม่ได้เป็นเพื่อนกับคุณ)")
                else:
                    st.warning("กรุณาใส่ Token และ Target ID ให้ครบถ้วนก่อนกดส่งครับ")

    # ----------------------------------------------------------------------
    # 🖥️ แดชบอร์ด
    # ----------------------------------------------------------------------
    elif menu == "🖥️ แดชบอร์ด":
        st.header("🖥️ ภาพรวมคลังเวชภัณฑ์ (Dashboard)")
        try:
            meds = pd.DataFrame(supabase.table("medicines").select("id, generic_name, unit, min_stock, category").eq("is_active", True).execute().data)
            inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
            
            if not meds.empty:
                meds['category'] = meds['category'].astype(str).str.strip()
                count_drugs = len(meds[meds['category'].isin(['ยาในบัญชี', 'ยานอกบัญชี', 'เวชภัณฑ์ยา'])])
                count_supplies = len(meds[meds['category'].isin(['เวชภัณฑ์/วัสดุ', 'เวชภัณฑ์ที่มิใช่ยา'])])

                if not inv.empty:
                    inv_agg = inv.groupby('medicine_id')['qty'].sum().reset_index()
                    df_dash = pd.merge(meds, inv_agg, left_on='id', right_on='medicine_id', how='left')
                    df_dash['qty'] = df_dash['qty'].fillna(0)
                else:
                    df_dash = meds.copy()
                    df_dash['qty'] = 0
                
                df_dash['qty'] = pd.to_numeric(df_dash['qty'], errors='coerce').fillna(0)
                df_dash['min_stock'] = pd.to_numeric(df_dash['min_stock'], errors='coerce').fillna(0)
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
    # 📥 รับเข้า (Receive) 
    # ----------------------------------------------------------------------
    elif menu == "📥 รับเข้า (Receive)":
        st.header("📥 การรับเวชภัณฑ์เข้าคลัง (Receive)")
        meds = get_medicines()
        
        med_dict = dict(zip(meds['id'], meds['generic_name'] + " (" + meds['unit'] + ")"))
        med_options = meds['id'].tolist()
        
        num_items = st.number_input("จำนวนรายการเวชภัณฑ์ที่ต้องการรับเข้าพร้อมกัน", min_value=1, max_value=20, value=1)
        st.divider()
        
        with st.form("bulk_receive_form"):
            receive_data = []
            for i in range(int(num_items)):
                st.markdown(f"**รายการที่ {i+1}**")
                
                selected_id = st.selectbox(
                    "เลือกเวชภัณฑ์", 
                    options=med_options, 
                    format_func=lambda x: med_dict[x], 
                    key=f"med_{i}"
                )
                
                c1, c2, c3, c4 = st.columns(4)
                with c1: lot = st.text_input("รหัส Lot", key=f"lot_{i}")
                with c2: mfg = st.date_input("วันผลิต", key=f"mfg_{i}")
                with c3: exp = st.date_input("วันหมดอายุ", key=f"exp_{i}")
                with c4: qty = st.number_input("จำนวนรับเข้า", min_value=1, key=f"qty_{i}")
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
    # 📤 เบิกจ่าย (Dispense)
    # ----------------------------------------------------------------------
    elif menu == "📤 เบิกจ่าย (Dispense)":
        st.header("📤 การเบิกจ่ายเวชภัณฑ์ (Dispense)")
        df_inv = get_inventory_view()
        
        if not df_inv.empty:
            df_grouped = df_inv.groupby(['medicine_id', 'generic_name', 'unit'])['qty'].sum().reset_index()
            med_dict = dict(zip(df_grouped['medicine_id'], df_grouped['generic_name'] + " (เหลือ " + df_grouped['qty'].astype(int).astype(str) + " " + df_grouped['unit'] + ")"))
            med_options = df_grouped['medicine_id'].tolist()
            
            st.info("💡 ระบบจะหักยอดคงเหลือจาก Lot ที่กำลังจะหมดอายุก่อนให้อัตโนมัติ (หลักการ FEFO)")
            
            num_items = st.number_input("จำนวนรายการเวชภัณฑ์ที่ต้องการเบิกจ่ายพร้อมกัน", min_value=1, max_value=20, value=1)
            st.divider()
            
            with st.form("bulk_dispense_form"):
                dispense_requests = []
                for i in range(int(num_items)):
                    st.markdown(f"**รายการที่ {i+1}**")
                    c1, c2 = st.columns([3, 1])
                    
                    with c1:
                        selected_id = st.selectbox(
                            "เลือกชื่อเวชภัณฑ์", 
                            options=med_options, 
                            format_func=lambda x: med_dict[x], 
                            key=f"disp_med_{i}"
                        )
                    with c2:
                        amount = st.number_input("จำนวนที่เบิก", min_value=1, key=f"disp_qty_{i}")
                        
                    st.markdown("---")
                    
                    dispense_requests.append({
                        'medicine_id': selected_id,
                        'dispense_qty': amount
                    })
                    
                note = st.text_input("หมายเหตุ (เช่น เบิกให้แผนก ER, รพ.สต.เครือข่าย)", value="จ่ายหน้างาน")
                recorder_name = st.session_state.full_name if st.session_state.full_name else st.session_state.user_email
                st.caption(f"ผู้บันทึกการเบิกจ่าย: {recorder_name}")
                
                if st.form_submit_button("ยืนยันการเบิกจ่าย", use_container_width=True):
                    req_df = pd.DataFrame(dispense_requests)
                    req_grouped = req_df.groupby('medicine_id')['dispense_qty'].sum().reset_index()
                    
                    has_error = False
                    for _, row in req_grouped.iterrows():
                        med_id = row['medicine_id']
                        total_req = row['dispense_qty']
                        avail_qty = df_grouped[df_grouped['medicine_id'] == med_id]['qty'].values[0]
                        
                        if total_req > avail_qty:
                            med_name = df_grouped[df_grouped['medicine_id'] == med_id]['generic_name'].values[0]
                            st.error(f"❌ ยอดคงเหลือของ '{med_name}' ไม่พอเบิก! (มียอดรวม {int(avail_qty)} แต่ต้องการเบิก {int(total_req)})")
                            has_error = True
                            
                    if not has_error:
                        try:
                            for req in dispense_requests:
                                med_id = req['medicine_id']
                                qty_needed = req['dispense_qty']
                                
                                lot_res = supabase.table("inventory").select("*").eq("medicine_id", med_id).gt("qty", 0).order("exp_date").execute()
                                available_lots = pd.DataFrame(lot_res.data)
                                
                                for _, lot in available_lots.iterrows():
                                    if qty_needed <= 0:
                                        break
                                        
                                    take_qty = min(lot['qty'], qty_needed)
                                    new_inv_qty = lot['qty'] - take_qty
                                    
                                    supabase.table("inventory").update({"qty": new_inv_qty}).eq("id", lot['id']).execute()
                                    
                                    supabase.table("transactions").insert({
                                        "medicine_id": med_id, 
                                        "action_type": "DISPENSE",
                                        "qty_change": -take_qty, 
                                        "lot_no": lot['lot_no'],
                                        "user_name": recorder_name, 
                                        "note": note
                                    }).execute()
                                    
                                    qty_needed -= take_qty
                                    
                            st.success("✅ บันทึกการเบิกจ่ายสำเร็จ! (ระบบตัดสต๊อกตาม Lot ที่หมดอายุก่อนให้อัตโนมัติเรียบร้อยแล้ว)")
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"เกิดข้อผิดพลาดจากฐานข้อมูล: {e}")
        else:
            st.info("ไม่มียอดยกมาในคลังสำหรับเบิกจ่าย")

    # ----------------------------------------------------------------------
    # 📊 สรุปยอดประจำเดือน และ รายงานขอเบิก 
    # ----------------------------------------------------------------------
    elif menu == "📊 สรุปยอด และ ขอเบิก":
        st.header("📊 สรุปยอด และ ขอเบิกเวชภัณฑ์")
        
        tab_summary, tab_reorder = st.tabs(["📅 สรุปยอดรับ-จ่าย ประจำเดือน", "🛒 รายงานขอเบิก"])

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
            st.subheader("🛒 จัดการและรายงานใบขอเบิกเวชภัณฑ์")
            
            meds = get_medicines()
            if not meds.empty:
                inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
                if not inv.empty:
                    inv_agg = inv.groupby('medicine_id')['qty'].sum().reset_index()
                    df_all = pd.merge(meds, inv_agg, left_on='id', right_on='medicine_id', how='left')
                    df_all['qty'] = df_all['qty'].fillna(0).astype(int)
                else:
                    df_all = meds.copy()
                    df_all['qty'] = 0

                low_stock_ids = df_all[df_all['qty'] <= df_all['min_stock']]['id'].tolist()
                
                base_ids = [id for id in low_stock_ids if id not in st.session_state.reorder_manual_removed]
                table_med_ids = list(set(base_ids + st.session_state.reorder_manual_added))
                
                df_table = df_all[df_all['id'].isin(table_med_ids)].copy()
                df_available = df_all[~df_all['id'].isin(table_med_ids)].copy()

                st.markdown("##### 📝 รายการขอเบิก")
                st.caption("💡 **วิธีแก้ไขจำนวน:** คลิกที่ตัวเลขในช่อง 'จำนวนขอเบิก' เพื่อพิมพ์แก้ได้เลย <br>💡 **วิธีลบรายการ:** ติ๊กเครื่องหมายถูกที่ช่อง **'ลบรายการ'** ท้ายตาราง แถวนั้นจะหายวับไปทันทีครับ!", unsafe_allow_html=True)
                
                if not df_table.empty:
                    df_table['suggested_reorder'] = df_table.apply(
                        lambda row: st.session_state.reorder_quantities.get(row['id'], row['min_stock']), 
                        axis=1
                    )

                    df_display_reorder = df_table[['generic_name', 'unit', 'min_stock', 'qty', 'suggested_reorder']].copy()
                    df_display_reorder.insert(0, 'ลำดับ', range(1, len(df_display_reorder) + 1))
                    
                    df_display_reorder['ลบรายการ'] = False
                    
                    df_display_reorder.columns = ['ลำดับ', 'รายการ', 'หน่วยนับ', 'อัตราใช้ต่อเดือน', 'จำนวนคงเหลือ', 'จำนวนขอเบิก', 'ลบรายการ']

                    edited_df = st.data_editor(
                        df_display_reorder,
                        hide_index=True,
                        use_container_width=True,
                        disabled=["ลำดับ", "รายการ", "หน่วยนับ", "อัตราใช้ต่อเดือน", "จำนวนคงเหลือ"], 
                        column_config={
                            "ลบรายการ": st.column_config.CheckboxColumn(
                                "ลบรายการ",
                                help="ติ๊กถูกช่องนี้ แถวนี้จะถูกลบทิ้งทันที",
                                default=False,
                            )
                        },
                        key="reorder_table" 
                    )

                    needs_rerun = False
                    
                    for idx, row in edited_df.iterrows():
                        med_name = row['รายการ']
                        med_id = df_all[df_all['generic_name'] == med_name]['id'].values[0]
                        
                        if st.session_state.reorder_quantities.get(med_id) != row['จำนวนขอเบิก']:
                            st.session_state.reorder_quantities[med_id] = row['จำนวนขอเบิก']
                            
                        if row['ลบรายการ'] == True:
                            if med_id in st.session_state.reorder_manual_added:
                                st.session_state.reorder_manual_added.remove(med_id)
                            else:
                                if med_id not in st.session_state.reorder_manual_removed:
                                    st.session_state.reorder_manual_removed.append(med_id)
                                    
                            if med_id in st.session_state.reorder_quantities:
                                del st.session_state.reorder_quantities[med_id]
                                
                            needs_rerun = True 

                    if needs_rerun:
                        if "reorder_table" in st.session_state:
                            del st.session_state["reorder_table"]
                        st.rerun()

                    st.divider()
                    final_export_df = edited_df.drop(columns=['ลบรายการ']).copy()
                    final_export_df['ลำดับ'] = range(1, len(final_export_df) + 1) 
                    
                    buffer = io.BytesIO()
                    try:
                        final_export_df.to_excel(buffer, index=False, sheet_name='ใบขอเบิก')
                        st.download_button(
                            label="📥 บันทึกและดาวน์โหลดไฟล์ Excel (.xlsx)",
                            data=buffer.getvalue(),
                            file_name=f"ใบขอเบิกเวชภัณฑ์_{datetime.date.today().strftime('%Y_%m_%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )
                    except Exception as e:
                        csv_reorder = final_export_df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 ดาวน์โหลดไฟล์ขอเบิก (CSV รองรับ Excel)",
                            data=csv_reorder,
                            file_name=f"ใบขอเบิกเวชภัณฑ์_{datetime.date.today().strftime('%Y_%m_%d')}.csv",
                            mime="text/csv",
                            type="primary"
                        )
                else:
                    st.success("✅ ยอดคงคลังเพียงพอทุกรายการ (หากต้องการออกใบเบิก ให้ค้นหาแล้วกดปุ่มเพิ่มลงตารางด้านล่างได้เลยครับ)")

                st.divider()
                
                st.markdown("##### ➕ เพิ่มรายการขอเบิก (นอกเหนือจากที่ระบบแนะนำ)")
                st.info("💡 กล่องค้นหาด้านล่าง จะแสดงเฉพาะ 'รายชื่อยาที่ยังไม่มีอยู่ในตาราง' เท่านั้นครับ")
                
                c_add1, c_add2, c_add3 = st.columns([3, 1, 1])
                with c_add1:
                    if not df_available.empty:
                        avail_dict = dict(zip(df_available['id'], df_available['generic_name'] + " (" + df_available['unit'] + ")"))
                        add_choice_id = st.selectbox(
                            "เลือกรายการเวชภัณฑ์:", 
                            options=[None] + df_available['id'].tolist(),
                            format_func=lambda x: "-- เลือกรายการเวชภัณฑ์ --" if x is None else avail_dict[x],
                            label_visibility="collapsed"
                        )
                    else:
                        add_choice_id = None
                        st.selectbox("เลือกรายการเวชภัณฑ์:", ["(เวชภัณฑ์ทุกตัวอยู่ในตารางขอเบิกหมดแล้ว)"], disabled=True, label_visibility="collapsed")
                
                with c_add2:
                    if st.button("➕ เพิ่มลงตาราง", use_container_width=True):
                        if add_choice_id is not None:
                            st.session_state.reorder_manual_added.append(add_choice_id)
                            if add_choice_id in st.session_state.reorder_manual_removed:
                                st.session_state.reorder_manual_removed.remove(add_choice_id)
                            st.rerun()
                            
                with c_add3:
                    if st.button("🔄 ล้างรายการที่เพิ่มเอง", use_container_width=True):
                        st.session_state.reorder_manual_added = []
                        st.session_state.reorder_manual_removed = []
                        st.session_state.reorder_quantities = {}
                        if "reorder_table" in st.session_state:
                            del st.session_state["reorder_table"]
                        st.rerun()

            else:
                st.warning("ไม่พบข้อมูลเวชภัณฑ์ในระบบ")

    # ----------------------------------------------------------------------
    # 🧾 ประวัติรับ-จ่าย 
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
                elif selected_row.get('user_name') == recorder_name or selected_row.get('user_name') == st.session_state.user_email:
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
                        with col_btn1:
                            submit_edit = st.form_submit_button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True)
                        with col_btn2:
                            # บังคับปุ่มลบประวัติเป็นสีแดง
                            st.markdown('<div class="red-btn-hook"></div>', unsafe_allow_html=True)
                            submit_delete = st.form_submit_button("❌ ลบรายการนี้", type="primary", use_container_width=True)
                        
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
            med_dict = dict(zip(meds['id'], meds['generic_name'] + " (" + meds['unit'] + ")"))
            
            selected_id = st.selectbox(
                "ค้นหาและเลือกรายการเวชภัณฑ์ที่ต้องการดูประวัติ:", 
                options=meds['id'].tolist(),
                format_func=lambda x: med_dict[x]
            )
            
            if selected_id:
                selected_name = meds[meds['id'] == selected_id]['generic_name'].values[0]
                selected_unit = meds[meds['id'] == selected_id]['unit'].values[0]
                
                t_res = supabase.table("transactions").select("*").eq("medicine_id", selected_id).order("created_at", desc=False).execute()
                df_t = pd.DataFrame(t_res.data)
                
                df_t = map_user_names(df_t)
                
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
    # 📋 ข้อมูลยา (Master Data)
    # ----------------------------------------------------------------------
    elif menu == "📋 ข้อมูลยา (Master Data)":
        st.header("📋 จัดการข้อมูลเวชภัณฑ์หลัก (Master Data)")
        
        # เตรียมรายการกลุ่มยา
        base_groups = [
            "กลุ่มยาแก้ปวด-ลดไข้", "กลุ่มยาแก้แพ้", "กลุ่มยาระงับอาการไอ ขับเสมหะ",
            "กลุ่มยารักษาโรคหืด", "กลุ่มยาต้านแบคทีเรีย / ยาปฏิชีวนะ", "กลุ่มยาถ่ายพยาธิ",
            "กลุ่มยาลดกรด - ขับลม", "กลุ่มยาระบาย", "กลุ่มยาแก้ท้องเสีย",
            "กลุ่มยาแก้ปวดเกร็งในช่องท้อง", "กลุ่มยาแก้คลื่นไส้อาเจียน-วิงเวียนศีรษะ",
            "กลุ่มน้ำเกลือและสารน้ำให้ทางหลอดเลือดดำ", "กลุ่มยาชาเฉพาะที่", "กลุ่มยาช่วยชีวิต",
            "กลุ่มน้ำยาฆ่าเชื้อ", "กลุ่มยาที่ใช้สำหรับผิวหนัง",
            "กลุ่มยาหยอดตา-ยาหยอดหู-ยาป้ายแผลในปาก", "กลุ่มยาบำรุงโลหิต-ยาวิตามิน", "กลุ่มยาสมุนไพร"
        ]
        
        try:
            all_meds_raw = supabase.table("medicines").select("drug_group").execute().data
            existing_groups = [m['drug_group'] for m in all_meds_raw if m.get('drug_group') and m['drug_group'] != '-']
        except:
            existing_groups = []
            
        unique_groups = sorted(list(set(base_groups + existing_groups)))
        group_options = ["- (ไม่มีกลุ่มยา / ไม่ระบุ)"] + unique_groups + ["➕ พิมพ์เพิ่มกลุ่มยาใหม่เอง..."]
        
        tab1, tab2, tab3 = st.tabs(["📄 รายการที่มีอยู่", "📝 เพิ่มรายการใหม่", "⚙️ แก้ไข / ลบข้อมูล"])
        
        with tab1:
            st.info("แสดงเฉพาะรายการเวชภัณฑ์ที่เปิดใช้งานอยู่ (Active) ในระบบ")
            df_meds = get_medicines()
            if not df_meds.empty:
                category_mapping = {
                    'ยาในบัญชี': 'เวชภัณฑ์ยา',
                    'ยานอกบัญชี': 'เวชภัณฑ์ยา',
                    'เวชภัณฑ์/วัสดุ': 'เวชภัณฑ์ที่มิใช่ยา'
                }
                df_meds['category'] = df_meds['category'].replace(category_mapping)
                
                df_meds['id'] = df_meds['id'].apply(lambda x: "-" if str(x).startswith("SYS-") else x)
                df_meds.insert(0, 'ลำดับ', range(1, len(df_meds) + 1))
                
                df_meds.rename(columns={'id': 'รหัสยามาตรฐาน', 'generic_name': 'ชื่อสามัญ', 'unit': 'หน่วยนับ', 'category': 'หมวดหมู่', 'drug_group': 'กลุ่มยา', 'min_stock': 'จุดสั่งซื้อ', 'is_active': 'สถานะ Active'}, inplace=True)
                
                cols_to_show = ['ลำดับ', 'รหัสยามาตรฐาน', 'ชื่อสามัญ', 'หน่วยนับ', 'หมวดหมู่']
                if 'กลุ่มยา' in df_meds.columns: cols_to_show.append('กลุ่มยา') 
                cols_to_show.extend(['จุดสั่งซื้อ', 'สถานะ Active'])
                
                st.dataframe(df_meds[cols_to_show], use_container_width=True, hide_index=True)
            else:
                st.info("ยังไม่มีข้อมูลเวชภัณฑ์")

        with tab2:
            with st.container(border=True):
                st.markdown("#### เพิ่มรายการเวชภัณฑ์ใหม่")
                c1, c2 = st.columns(2)
                nid_input = c1.text_input("รหัสยามาตรฐาน (เว้นว่างได้ ระบบจะแสดงผลเป็น - ให้อัตโนมัติ)", key="add_id")
                nname = c2.text_input("ชื่อสามัญ (Generic Name) *บังคับ", key="add_name")
                nunit = c1.text_input("หน่วยนับ (เช่น เม็ด, ขวด) *บังคับ", key="add_unit")
                ncat = c2.selectbox("หมวดหมู่", ["เวชภัณฑ์ยา", "เวชภัณฑ์ที่มิใช่ยา"], key="add_cat")
                
                final_group = "-"
                if ncat == "เวชภัณฑ์ยา":
                    ngroup_choice = st.selectbox("กลุ่มยา", group_options, key="add_group_choice")
                    
                    if ngroup_choice == "➕ พิมพ์เพิ่มกลุ่มยาใหม่เอง...":
                        ngroup_custom = st.text_input("พิมพ์ชื่อกลุ่มยาใหม่", key="add_group_custom")
                        final_group = ngroup_custom.strip() if ngroup_custom.strip() else "-"
                    elif ngroup_choice != "- (ไม่มีกลุ่มยา / ไม่ระบุ)":
                        final_group = ngroup_choice
                else:
                    final_group = "-"
                
                nmin = st.number_input("จุดสั่งซื้อ (Min Stock)", min_value=0, value=100, key="add_min")
                
                if st.button("บันทึกรายการใหม่", use_container_width=True, type="primary", key="btn_add_med"):
                    if nname and nunit:
                        final_nid = nid_input.strip() if nid_input.strip() != "" else f"SYS-{int(time.time())}"
                        try:
                            supabase.table("medicines").insert({
                                "id": final_nid, "generic_name": nname, "unit": nunit, 
                                "category": ncat, "drug_group": final_group, 
                                "min_stock": nmin, "is_active": True
                            }).execute()
                            st.success("เพิ่มข้อมูลสำเร็จ!"); time.sleep(1); st.rerun()
                        except Exception as e: 
                            st.error(f"เกิดข้อผิดพลาดจากฐานข้อมูล: {e} (คุณลืมเพิ่มคอลัมน์ drug_group ใน Supabase หรือเปล่า?)")
                    else: st.warning("กรุณากรอกชื่อเวชภัณฑ์ และหน่วยนับ ให้ครบถ้วน")
                        
        with tab3:
            all_meds_data = supabase.table("medicines").select("*").execute().data
            if all_meds_data:
                all_meds = pd.DataFrame(all_meds_data)
                
                med_dict = dict(zip(all_meds['id'], all_meds['generic_name'].fillna('-ไม่มีชื่อยา-') + " (" + all_meds['unit'].fillna('-') + ")"))
                
                selected_id_real = st.selectbox(
                    "ค้นหาและเลือกรายการที่ต้องการแก้ไข หรือ ลบ:", 
                    options=all_meds['id'].tolist(),
                    format_func=lambda x: med_dict[x],
                    key="edit_med_select"
                )
                
                if selected_id_real:
                    med_info = all_meds[all_meds['id'] == selected_id_real].iloc[0]
                    
                    st.divider()
                    
                    # 🌟 ระบบกุญแจแบบแปรผัน บังคับฟอร์มเปลี่ยนข้อมูล
                    k_suffix = str(selected_id_real)
                    
                    with st.container(border=True):
                        st.markdown("#### แก้ไขข้อมูล")
                        c1, c2 = st.columns(2)
                        
                        display_nid = "" if str(selected_id_real).startswith("SYS-") else selected_id_real
                        e_id = c1.text_input("รหัสยามาตรฐาน (แก้ไขหรือเพิ่มใหม่ได้เลย หากเว้นว่างระบบจะใช้รหัสอัตโนมัติ)", value=display_nid, key=f"edit_id_{k_suffix}")
                        
                        old_name = "" if pd.isna(med_info['generic_name']) else med_info['generic_name']
                        e_name = c2.text_input("ชื่อสามัญ (Generic Name)", value=old_name, key=f"edit_name_{k_suffix}")
                        
                        old_unit = "" if pd.isna(med_info['unit']) else med_info['unit']
                        e_unit = c1.text_input("หน่วยนับ", value=old_unit, key=f"edit_unit_{k_suffix}")
                        
                        cat_options = ["เวชภัณฑ์ยา", "เวชภัณฑ์ที่มิใช่ยา"]
                        current_cat = str(med_info.get('category', ''))
                        if current_cat in ['ยาในบัญชี', 'ยานอกบัญชี', 'เวชภัณฑ์ยา']: cat_idx = 0 
                        elif current_cat in ['เวชภัณฑ์/วัสดุ', 'เวชภัณฑ์ที่มิใช่ยา']: cat_idx = 1 
                        else: cat_idx = 0 
                            
                        e_cat = c2.selectbox("หมวดหมู่", cat_options, index=cat_idx, key=f"edit_cat_{k_suffix}")
                        
                        final_egroup = "-"
                        if e_cat == "เวชภัณฑ์ยา":
                            current_group = str(med_info.get('drug_group', '-'))
                            if current_group == 'None' or current_group == 'nan' or current_group == '': 
                                current_group = '-'
                                
                            try:
                                group_idx = group_options.index(current_group)
                            except:
                                if current_group != '-':
                                    group_options.insert(1, current_group)
                                    group_idx = 1
                                else:
                                    group_idx = 0
                                    
                            egroup_choice = st.selectbox("กลุ่มยา", group_options, index=group_idx, key=f"edit_group_choice_{k_suffix}")
                            
                            if egroup_choice == "➕ พิมพ์เพิ่มกลุ่มยาใหม่เอง...":
                                egroup_custom = st.text_input("พิมพ์ชื่อกลุ่มยาใหม่", value="", key=f"edit_group_custom_{k_suffix}")
                                final_egroup = egroup_custom.strip() if egroup_custom.strip() else "-"
                            elif egroup_choice != "- (ไม่มีกลุ่มยา / ไม่ระบุ)":
                                final_egroup = egroup_choice
                        else:
                            final_egroup = "-"
                        
                        min_stock_val = 0 if pd.isna(med_info.get('min_stock')) else int(med_info.get('min_stock', 0))
                        e_min = st.number_input("จุดสั่งซื้อ (Min Stock)", min_value=0, value=min_stock_val, key=f"edit_min_{k_suffix}")
                        e_active = st.checkbox("เปิดใช้งานรายการนี้ (นำไปรับ/เบิกได้ปกติ)", value=bool(med_info['is_active']), key=f"edit_active_{k_suffix}")
                        
                        if st.button("บันทึกการแก้ไข", use_container_width=True, type="primary", key=f"btn_save_edit_{k_suffix}"):
                            if e_name and e_unit:
                                final_new_id = e_id.strip()
                                if final_new_id == "":
                                    if str(selected_id_real).startswith("SYS-"): final_new_id = selected_id_real
                                    else: final_new_id = f"SYS-{int(time.time())}"
                                        
                                try:
                                    if final_new_id != selected_id_real:
                                        check = supabase.table("medicines").select("id").eq("id", final_new_id).execute()
                                        if check.data:
                                            st.error(f"❌ เปลี่ยนรหัสไม่ได้! รหัส '{final_new_id}' มีซ้ำอยู่ในระบบแล้ว")
                                            st.stop()
                                            
                                        supabase.table("medicines").insert({
                                            "id": final_new_id, "generic_name": e_name, "unit": e_unit, 
                                            "category": e_cat, "drug_group": final_egroup, 
                                            "min_stock": e_min, "is_active": e_active
                                        }).execute()
                                        
                                        supabase.table("inventory").update({"medicine_id": final_new_id}).eq("medicine_id", selected_id_real).execute()
                                        supabase.table("transactions").update({"medicine_id": final_new_id}).eq("medicine_id", selected_id_real).execute()
                                        supabase.table("medicines").delete().eq("id", selected_id_real).execute()
                                        
                                    else:
                                        supabase.table("medicines").update({
                                            "generic_name": e_name, "unit": e_unit, 
                                            "category": e_cat, "drug_group": final_egroup, 
                                            "min_stock": e_min, "is_active": e_active
                                        }).eq("id", selected_id_real).execute()
                                        
                                    st.success(f"✅ อัปเดตข้อมูลสำเร็จ!"); time.sleep(1.5); st.rerun()
                                except Exception as e:
                                    st.error(f"เกิดข้อผิดพลาดในการอัปเดต: {e} (ลืมเพิ่มคอลัมน์ drug_group ใน Supabase หรือเปล่า?)")
                            else:
                                st.warning("กรุณากรอกชื่อเวชภัณฑ์และหน่วยนับให้ครบถ้วน")
                    
                    st.divider()
                    st.markdown("#### ลบข้อมูลถาวร")
                    st.warning("แนะนำให้ใช้วิธี **'เอาเครื่องหมายถูกเปิดใช้งานออก'** แทนการลบ เพื่อเก็บประวัติไว้ตรวจสอบ (ระบบจะอนุญาตให้ลบถาวรได้ **เฉพาะรายการที่ไม่เคยมีประวัติรับ-จ่าย** เท่านั้น)")
                    
                    del_col1, del_col2 = st.columns([1, 1])
                    with del_col1:
                        confirm_del = st.checkbox("ยืนยันว่าต้องการลบรายการนี้ทิ้งถาวร", key=f"confirm_delete_box_{k_suffix}")
                    with del_col2:
                        # บังคับปุ่มลบรายการยาเป็นสีแดง
                        st.markdown('<div class="red-btn-hook"></div>', unsafe_allow_html=True)
                        if st.button("ลบรายการเวชภัณฑ์ถาวร", type="primary", use_container_width=True, key=f"btn_del_med_{k_suffix}"):
                            if confirm_del:
                                try:
                                    supabase.table("medicines").delete().eq("id", selected_id_real).execute()
                                    st.success(f"ลบรายการออกจากระบบเรียบร้อยแล้ว!")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error("ไม่สามารถลบได้! เนื่องจากรายการนี้เคยถูกทำรับ/เบิกไปแล้ว (กรุณาใช้วิธีปิดใช้งานแทน)")
                            else:
                                st.error("กรุณาติ๊กเครื่องหมายถูกที่ช่อง 'ยืนยัน' ก่อนกดปุ่มลบ")
            else: st.info("ยังไม่มีข้อมูลในระบบ")
