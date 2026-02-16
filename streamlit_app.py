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
    .stButton>button:hover { transform: scale(1.02); border-color: #ff4b4b; color: #ff4b4b; }
    [data-testid="stForm"] { border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); padding: 2rem; }
    [data-testid="stAlert"] { border-radius: 8px; }
    [data-testid="stMetricValue"] { color: #2e7bcf; }
    .item-box { border: 1px solid #eee; padding: 15px; border-radius: 8px; margin-bottom: 10px; background-color: #fafafa;}
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

# --- 2. ระบบจัดการ Session (LOGIN STATE) ---
if 'user' not in st.session_state: st.session_state.user = None
if 'role' not in st.session_state: st.session_state.role = None
if 'user_email' not in st.session_state: st.session_state.user_email = None

def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        profile = supabase.table("profiles").select("*").eq("id", response.user.id).execute()
        if profile.data:
            if profile.data[0]['is_approved']:
                st.session_state.user = response.user
                st.session_state.role = profile.data[0]['role']
                st.session_state.user_email = email
                st.success(f"🎉 ยินดีต้อนรับ! {email}")
                time.sleep(1)
                st.rerun()
            else: st.warning("⏳ บัญชีของคุณรอการอนุมัติจาก Admin")
        else: st.error("❌ ไม่พบข้อมูลสิทธิ์ผู้ใช้")
    except Exception as e:
        st.error("❌ อีเมลหรือรหัสผ่านไม่ถูกต้อง")

def logout_user():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()

# --- 3. ฟังก์ชันดึงข้อมูล ---
def get_medicines():
    return pd.DataFrame(supabase.table("medicines").select("*").eq("is_active", True).execute().data)

def get_inventory_view():
    meds = pd.DataFrame(supabase.table("medicines").select("id, generic_name, unit").execute().data)
    inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
    if inv.empty: return pd.DataFrame()
    
    merged = pd.merge(inv, meds, left_on="medicine_id", right_on="id", how="left", suffixes=('', '_med'))
    return merged[merged['qty'] > 0]

# --- 4. ส่วนหน้าจอ (FRONTEND) ---
if not st.session_state.user:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=100)
        st.title("ระบบคลังยา")
        st.markdown("##### รพ.สต. โพนบก 🏥")
        with st.form("login_form"):
            email = st.text_input("อีเมลผู้ใช้งาน")
            password = st.text_input("รหัสผ่าน", type="password")
            if st.form_submit_button("เข้าสู่ระบบ", use_container_width=True):
                login_user(email, password)
        st.caption("💡 หากยังไม่มีบัญชี โปรดแจ้ง
