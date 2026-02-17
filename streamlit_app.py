import streamlit as st
from supabase import create_client
import pandas as pd
import datetime
import time

# --- 1. ตั้งค่าและเชื่อมต่อ (SETUP) ---
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
                                # 🌟 หน่วงเวลา 2 วินาที ให้ฐานข้อมูลสร้าง Profile ให้เสร็จก่อนอัปเดตชื่อ
                                time.sleep(2)
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
        "📊 สรุปยอดประจำเดือน", 
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
                
                # 🌟 เอาคอลัมน์ created_at ออกจากตารางแสดงผล
                cols_to_show = ['email', 'full_name', 'role', 'status']
                existing_cols = [c for c in cols_to_show if c in profiles.columns]
                
                df_show = profiles[existing_cols].copy()
                df_show.rename(columns={'email': 'อีเมล', 'full_name': 'ชื่อ-นามสกุล', 'role': 'สิทธิ์', 'status': 'สถานะ'}, inplace=True)
                
                st.dataframe(df_show, use_container_width=True, hide_index=True)
                
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
                                # 🌟 หน่วงเวลา 2 วินาที
                                time.sleep(2)
                                supabase.table("profiles").update({"is_approved": True, "role": new_role, "full_name": new_name}).eq("id",
