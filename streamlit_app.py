import streamlit as st
from supabase import create_client
import pandas as pd
import datetime
import time

# --- 1. ตั้งค่าและเชื่อมต่อ (SETUP) ---
st.set_page_config(page_title="ระบบคลังยา รพ.สต. โพนบก", layout="wide", page_icon="🏥")

# เชื่อมต่อ Supabase
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
if 'user' not in st.session_state:
    st.session_state.user = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

def login_user(email, password):
    try:
        # 1. Login กับ Supabase Auth
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = response.user
        
        # 2. ตรวจสอบ Role ในตาราง Profiles
        profile = supabase.table("profiles").select("*").eq("id", user.id).execute()
        
        if profile.data:
            user_role = profile.data[0]['role']
            is_approved = profile.data[0]['is_approved']
            
            if is_approved:
                st.session_state.user = user
                st.session_state.role = user_role
                st.session_state.user_email = email
                st.success(f"ยินดีต้อนรับ! {email} ({user_role})")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("⏳ บัญชีของคุณรอการอนุมัติจาก Admin")
        else:
            st.error("ไม่พบข้อมูลผู้ใช้ในระบบ")
            
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาด: อีเมลหรือรหัสผ่านไม่ถูกต้อง ({e})")

def logout_user():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.role = None
    st.rerun()

# --- 3. ฟังก์ชันดึงข้อมูล (DATA FUNCTIONS) ---
def get_medicines():
    return pd.DataFrame(supabase.table("medicines").select("*").eq("is_active", True).execute().data)

def get_inventory_view():
    # ดึงข้อมูลมา Join ใน Python
    meds = pd.DataFrame(supabase.table("medicines").select("id, generic_name, unit").execute().data)
    inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
    
    if inv.empty: return pd.DataFrame()
    
    merged = pd.merge(inv, meds, left_on="medicine_id", right_on="id", how="left")
    return merged[merged['qty'] > 0] # เอาเฉพาะที่มีของ

# --- 4. ส่วนหน้าจอ (FRONTEND) ---

# === ส่วนที่ A: หน้า Login ===
if not st.session_state.user:
    st.title("🏥 ระบบคลังยา รพ.สต. โพนบก")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=150)
    with col2:
        st.subheader("เข้าสู่ระบบ (Login)")
        email = st.text_input("อีเมล")
        password = st.text_input("รหัสผ่าน", type="password")
        
        if st.button("เข้าใช้งาน", type="primary"):
            login_user(email, password)
            
        st.info("💡 หากยังไม่มีบัญชี ให้กด Sign up ในหน้า Auth ของ Supabase (หรือแจ้ง Admin)")

# === ส่วนที่ B: ระบบหลัก (เมื่อ Login แล้ว) ===
else:
    # Sidebar แสดงข้อมูลผู้ใช้
    with st.sidebar:
        st.write(f"👤 **{st.session_state.user_email}**")
        st.caption(f"สถานะ: {st.session_state.role.upper()}")
        if st.button("ออกจากระบบ", type="secondary"):
            logout_user()
        st.divider()

    # เมนูหลัก
    menu_options = ["📊 แดชบอร์ด", "💊 เบิกจ่ายยา", "📦 รับยาเข้า", "📝 ข้อมูลยา (Master)"]
    if st.session_state.role == 'admin':
        menu_options.append("👑 Admin Panel") # เมนูพิเศษสำหรับ Admin
    
    menu = st.sidebar.radio("เมนูใช้งาน", menu_options)

    # ---------------------------------------------------------
    # 👑 MENU: ADMIN PANEL (อนุมัติผู้ใช้)
    # ---------------------------------------------------------
    if menu == "👑 Admin Panel":
        st.title("👑 ผู้ดูแลระบบ (Admin)")
        st.info("จัดการสิทธิ์ผู้ใช้งานระบบ")
        
        # ดึงรายชื่อผู้ใช้ทั้งหมด
        profiles = pd.DataFrame(supabase.table("profiles").select("*").execute().data)
        
        if not profiles.empty:
            # แปลงข้อมูลให้อ่านง่าย
            profiles['status'] = profiles['is_approved'].map({True: '✅ อนุมัติแล้ว', False: '⏳ รออนุมัติ'})
            
            st.dataframe(profiles[['email', 'role', 'status', 'created_at']], use_container_width=True)
            
            st.subheader("จัดการคำขอ")
            # เลือกคนที่จะอนุมัติ
            pending_users = profiles[profiles['is_approved'] == False]
            if not pending_users.empty:
                user_to_approve = st.selectbox("เลือกผู้ใช้เพื่ออนุมัติ", pending_users['email'])
                
                col1, col2 = st.columns(2)
                if col1.button("✅ อนุมัติให้ใช้งาน"):
                    supabase.table("profiles").update({"is_approved": True}).eq("email", user_to_approve).execute()
                    st.success(f"อนุมัติ {user_to_approve} เรียบร้อย!")
                    st.rerun()
                    
                if col2.button("👮 แต่งตั้งเป็น Admin"):
                    supabase.table("profiles").update({"is_approved": True, "role": "admin"}).eq("email", user_to_approve).execute()
                    st.success(f"แต่งตั้ง {user_to_approve} เป็น Admin เรียบร้อย!")
                    st.rerun()
            else:
                st.success("ไม่มีคำขอรออนุมัติ")

    # ---------------------------------------------------------
    # 📊 MENU: DASHBOARD
    # ---------------------------------------------------------
    elif menu == "📊 แดชบอร์ด":
        st.title("ภาพรวมคลังยา")
        try:
            df_inv = get_inventory_view()
            if not df_inv.empty:
                # สรุปยอด
                total_items = df_inv['generic_name'].nunique()
                total_qty = df_inv['qty'].sum()
                
                # เช็ควันหมดอายุ
                df_inv['exp_date'] = pd.to_datetime(df_inv['exp_date'])
                today = pd.to_datetime(datetime.date.today())
                near_exp = df_inv[df_inv['exp_date'] <= today + pd.Timedelta(days=180)]
                
                # แสดง Card
                c1, c2, c3 = st.columns(3)
                c1.metric("รายการยา", f"{total_items}", "รายการ")
                c2.metric("จำนวนชิ้นรวม", f"{total_qty:,}", "Unit")
                c3.metric("เสี่ยงหมดอายุ (<6ด.)", f"{len(near_exp)}", "ล็อต", delta_color="inverse")
                
                st.divider()
                
                col_l, col_r = st.columns([2,1])
                with col_l:
                    st.subheader("📦 คงเหลือแยกรายการ")
                    summary = df_inv.groupby(['generic_name', 'unit'])['qty'].sum().reset_index()
                    st.dataframe(summary, use_container_width=True)
                
                with col_r:
                    if not near_exp.empty:
                        st.subheader("🚨 ต้องรีบใช้ (FEFO)")
                        st.dataframe(near_exp[['generic_name', 'exp_date', 'qty']], hide_index=True)
                    else:
                        st.success("✅ คลังยาสุขภาพดีเยี่ยม")
            else:
                st.info("คลังยาว่างเปล่า")
        except Exception as e:
            st.error(f"Error loading dashboard: {e}")

    # ---------------------------------------------------------
    # 💊 MENU: DISPENSE (เบิกจ่าย)
    # ---------------------------------------------------------
    elif menu == "💊 เบิกจ่ายยา":
        st.title("เบิกจ่ายเวชภัณฑ์")
        df_inv = get_inventory_view()
        
        if not df_inv.empty:
            drug_name = st.selectbox("ค้นหาชื่อยา", df_inv['generic_name'].unique())
            
            # Filter Lots
            lots = df_inv[df_inv['generic_name'] == drug_name].sort_values("exp_date")
            
            st.info(f"รายการ Lot ของ {drug_name} (เรียงตามวันหมดอายุ)")
            for idx, row in lots.iterrows():
                with st.expander(f"Lot: {row['lot_no']} | Exp: {row['exp_date']} | มี: {row['qty']} {row['unit']}"):
                    with st.form(f"dispense_{row['id']}"):
                        amount = st.number_input("จำนวนที่เบิก", min_value=1, max_value=int(row['qty']))
                        note = st.text_input("หมายเหตุ (เช่น เบิกให้ ER)", value="จ่ายหน้างาน")
                        
                        if st.form_submit_button("ยืนยันจ่าย"):
                            # Update Inventory
                            new_q = int(row['qty']) - amount
                            supabase.table("inventory").update({"qty": new_q}).eq("id", row['id']).execute()
                            
                            # Log Transaction
                            supabase.table("transactions").insert({
                                "medicine_id": row['medicine_id'],
                                "action_type": "DISPENSE",
                                "qty_change": -amount,
                                "lot_no": row['lot_no'],
                                "user_name": st.session_state.user_email,
                                "note": note
                            }).execute()
                            st.success("✅ บันทึกสำเร็จ")
                            time.sleep(1)
                            st.rerun()

    # ---------------------------------------------------------
    # 📦 MENU: RECEIVE (รับเข้า)
    # ---------------------------------------------------------
    elif menu == "📦 รับยาเข้า":
        st.title("รับเวชภัณฑ์เข้าคลัง")
        meds = get_medicines()
        
        with st.form("recv_form"):
            d_choice = st.selectbox("เลือกยา", meds['id'] + " | " + meds['generic_name'])
            c1, c2 = st.columns(2)
            lot = c1.text_input("เลข Lot")
            exp = c2.date_input("วันหมดอายุ")
            qty = st.number_input("จำนวนรับ", min_value=1)
            
            if st.form_submit_button("บันทึกรับเข้า"):
                did = d_choice.split(" | ")[0]
                
                supabase.table("inventory").insert({
                    "medicine_id": did, "lot_no": lot, "exp_date": str(exp), "qty": qty
                }).execute()
                
                supabase.table("transactions").insert({
                    "medicine_id": did, "action_type": "RECEIVE", "qty_change": qty,
                    "lot_no": lot, "user_name": st.session_state.user_email, "note": "รับเข้าปกติ"
                }).execute()
                
                st.success("✅ รับเข้าสำเร็จ")

    # ---------------------------------------------------------
    # 📝 MENU: MASTER DATA (จัดการชื่อยา)
    # ---------------------------------------------------------
    elif menu == "📝 ข้อมูลยา (Master)":
        st.title("จัดการบัญชียาหลัก")
        
        tab1, tab2 = st.tabs(["เพิ่มรายการใหม่", "รายการที่มีอยู่"])
        
        with tab1:
            with st.form("new_med"):
                c1, c2 = st.columns(2)
                nid = c1.text_input("รหัสยา (เช่น DRUG009)")
                nname = c2.text_input("ชื่อสามัญ")
                nunit = c1.text_input("หน่วยนับ")
                ncat = c2.selectbox("หมวดหมู่", ["ยาในบัญชี", "ยานอกบัญชี", "วัสดุ"])
                
                if st.form_submit_button("เพิ่มข้อมูล"):
                    try:
                        supabase.table("medicines").insert({
                            "id": nid, "generic_name": nname, "unit": nunit, "category": ncat
                        }).execute()
                        st.success("✅ เพิ่มสำเร็จ")
                    except:
                        st.error("❌ รหัสยาซ้ำ หรือข้อมูลผิดพลาด")
        
        with tab2:
            st.dataframe(get_medicines(), use_container_width=True)
