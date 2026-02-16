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
        st.caption("💡 หากยังไม่มีบัญชี โปรดแจ้งผู้ดูแลระบบ (Admin) เพื่อสร้างบัญชีใหม่")

else:
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=60)
        st.write(f"👤 **{st.session_state.user_email}**")
        st.caption(f"⭐ สถานะ: {st.session_state.role.upper()}")
        if st.button("ออกจากระบบ", use_container_width=True): logout_user()
        st.divider()

    menu_options = ["📊 แดชบอร์ด", "💊 เบิกจ่ายยา (Bulk)", "📦 รับยาเข้า (Bulk)", "📝 ข้อมูลยา (Master)"]
    if st.session_state.role == 'admin': menu_options.append("👑 Admin Panel")
    menu = st.sidebar.radio("📌 เมนูใช้งาน", menu_options)

    if menu == "👑 Admin Panel":
        st.header("👑 ผู้ดูแลระบบ (Admin)")
        profiles = pd.DataFrame(supabase.table("profiles").select("*").execute().data)
        if not profiles.empty:
            profiles['status'] = profiles['is_approved'].map({True: '✅ อนุมัติแล้ว', False: '⏳ รออนุมัติ'})
            st.dataframe(profiles[['email', 'role', 'status', 'created_at']], use_container_width=True)
            st.divider()
            st.subheader("จัดการคำขอใช้งาน")
            pending_users = profiles[profiles['is_approved'] == False]
            if not pending_users.empty:
                user_to_approve = st.selectbox("เลือกผู้ใช้เพื่ออนุมัติ", pending_users['email'])
                c1, c2 = st.columns(2)
                if c1.button("✅ อนุมัติให้เป็น Staff", use_container_width=True):
                    supabase.table("profiles").update({"is_approved": True}).eq("email", user_to_approve).execute()
                    st.success("อนุมัติเรียบร้อย!"); st.rerun()
                if c2.button("👮 แต่งตั้งเป็น Admin", use_container_width=True):
                    supabase.table("profiles").update({"is_approved": True, "role": "admin"}).eq("email", user_to_approve).execute()
                    st.success("แต่งตั้งเป็น Admin เรียบร้อย!"); st.rerun()
            else: st.info("🎉 ไม่มีคำขอรออนุมัติ")

    elif menu == "📊 แดชบอร์ด":
        st.header("📊 ภาพรวมคลังยา")
        try:
            df_inv = get_inventory_view()
            if not df_inv.empty:
                total_items = df_inv['generic_name'].nunique()
                total_qty = df_inv['qty'].sum()
                df_inv['exp_date'] = pd.to_datetime(df_inv['exp_date'])
                today = pd.to_datetime(datetime.date.today())
                near_exp = df_inv[df_inv['exp_date'] <= today + pd.Timedelta(days=180)]
                
                c1, c2, c3 = st.columns(3)
                c1.metric("📌 รายการยาที่มี", f"{total_items}", "รายการ")
                c2.metric("📦 จำนวนชิ้นรวม", f"{total_qty:,}", "Unit")
                c3.metric("🚨 เสี่ยงหมดอายุ (<6ด.)", f"{len(near_exp)}", "ล็อต", delta_color="inverse")
                st.divider()
                
                col_l, col_r = st.columns([2,1])
                with col_l:
                    st.subheader("ยอดคงเหลือแยกรายการ")
                    summary = df_inv.groupby(['generic_name', 'unit'])['qty'].sum().reset_index()
                    st.dataframe(summary, use_container_width=True)
                with col_r:
                    if not near_exp.empty:
                        st.subheader("ต้องรีบใช้ (FEFO)")
                        st.dataframe(near_exp[['generic_name', 'exp_date', 'qty']], hide_index=True)
                    else: st.success("✅ คลังยาสุขภาพดีเยี่ยม")
            else: st.info("📭 คลังยาว่างเปล่า ยังไม่มีข้อมูลเวชภัณฑ์")
        except Exception as e: st.error(f"Error: {e}")

    elif menu == "💊 เบิกจ่ายยา (Bulk)":
        st.header("💊 เบิกจ่ายเวชภัณฑ์ (ตะกร้าเบิก)")
        df_inv = get_inventory_view()
        
        if not df_inv.empty:
            df_inv['display_label'] = df_inv['generic_name'] + " | Lot: " + df_inv['lot_no'] + " | หมดอายุ: " + df_inv['exp_date'].astype(str) + " (เหลือ " + df_inv['qty'].astype(str) + " " + df_inv['unit'] + ")"
            
            st.info("💡 ท่านสามารถคลิกเลือกยาได้หลายรายการพร้อมกัน เพื่อเบิกในครั้งเดียว")
            
            selected_labels = st.multiselect("🔍 ค้นหาและเลือกรายการยา (เลือกได้มากกว่า 1 ล็อต)", df_inv['display_label'].tolist())
            
            if selected_labels:
                st.divider()
                st.subheader("🛒 ระบุจำนวนที่ต้องการเบิก")
                
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
                            # ✅ แก้ไขตรงนี้: เติมหน่วยนับ {row['unit']} ลงไปในชื่อกล่อง
                            amount = st.number_input(f"จำนวนที่เบิก ({row['unit']})", min_value=1, max_value=int(row['qty']), key=f"disp_{i}")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        dispense_data.append({
                            'inventory_id': row['id'], 
                            'medicine_id': row['medicine_id'],
                            'lot_no': row['lot_no'],
                            'current_qty': int(row['qty']),
                            'dispense_qty': amount
                        })
                        
                    note = st.text_input("หมายเหตุ (เช่น เบิกให้ ER, รพ.สต.เครือข่าย)", value="จ่ายหน้างาน")
                    
                    if st.form_submit_button("✅ ยืนยันการเบิกจ่ายทั้งหมด", use_container_width=True):
                        for data in dispense_data:
                            new_qty = data['current_qty'] - data['dispense_qty']
                            supabase.table("inventory").update({"qty": new_qty}).eq("id", data['inventory_id']).execute()
                            supabase.table("transactions").insert({
                                "medicine_id": data['medicine_id'], "action_type": "DISPENSE",
                                "qty_change": -data['dispense_qty'], "lot_no": data['lot_no'],
                                "user_name": st.session_state.user_email, "note": note
                            }).execute()
                            
                        st.success("✅ บันทึกการเบิกจ่ายสำเร็จทั้งหมด!")
                        time.sleep(1.5)
                        st.rerun()

    elif menu == "📦 รับยาเข้า (Bulk)":
        st.header("📦 รับเวชภัณฑ์เข้าคลัง (ทีละหลายรายการ)")
        meds = get_medicines()
        med_options = meds['id'] + " | " + meds['generic_name'] + " (" + meds['unit'] + ")"
        
        num_items = st.number_input("🔢 จำนวนรายการยาที่ต้องการรับเข้าพร้อมกัน", min_value=1, max_value=20, value=1)
        st.divider()
        
        with st.form("bulk_receive_form"):
            receive_data = []
            
            for i in range(int(num_items)):
                st.markdown(f"**รายการที่ {i+1}**")
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                
                with c1: d_choice = st.selectbox("เลือกยา", med_options, key=f"med_{i}")
                with c2: lot = st.text_input("รหัส Lot", key=f"lot_{i}")
                with c3: mfg = st.date_input("วันผลิต", key=f"mfg_{i}")
                with c4: exp = st.date_input("วันหมดอายุ", key=f"exp_{i}")
                
                selected_id = d_choice.split(" | ")[0]
                selected_unit = meds[meds['id'] == selected_id]['unit'].values[0]
                qty = st.number_input(f"จำนวนที่รับเข้า ({selected_unit})", min_value=1, key=f"qty_{i}")
                
                st.markdown("---")
                
                receive_data.append({
                    "medicine_id": selected_id, "lot_no": lot,
                    "mfg_date": str(mfg), "exp_date": str(exp), "qty": qty
                })
                
            if st.form_submit_button("📥 บันทึกรับเข้าทั้งหมด", use_container_width=True):
                for data in receive_data:
                    if data['lot_no']:
                        supabase.table("inventory").insert(data).execute()
                        supabase.table("transactions").insert({
                            "medicine_id": data['medicine_id'], "action_type": "RECEIVE", "qty_change": data['qty'],
                            "lot_no": data['lot_no'], "user_name": st.session_state.user_email, "note": "รับเข้า (Bulk)"
                        }).execute()
                        
                st.success("✅ บันทึกรับเข้าสำเร็จทั้งหมด!")
                time.sleep(1.5)
                st.rerun()

    elif menu == "📝 ข้อมูลยา (Master)":
        st.header("📝 จัดการบัญชียาหลัก")
        tab1, tab2 = st.tabs(["➕ เพิ่มรายการใหม่", "📋 รายการที่มีอยู่"])
        with tab1:
            with st.form("new_med"):
                c1, c2 = st.columns(2)
                nid = c1.text_input("รหัสยา (เช่น DRUG009)")
                nname = c2.text_input("ชื่อสามัญ (Generic Name)")
                nunit = c1.text_input("หน่วยนับ (เช่น เม็ด, ขวด, หลอด)")
                ncat = c2.selectbox("หมวดหมู่", ["ยาในบัญชี", "ยานอกบัญชี", "เวชภัณฑ์/วัสดุ"])
                if st.form_submit_button("💾 เพิ่มข้อมูลยา", use_container_width=True):
                    try:
                        supabase.table("medicines").insert({"id": nid, "generic_name": nname, "unit": nunit, "category": ncat}).execute()
                        st.success("เพิ่มข้อมูลสำเร็จ!")
                    except: st.error("❌ รหัสยาซ้ำ หรือกรอกข้อมูลไม่ครบถ้วน")
        with tab2:
            st.dataframe(get_medicines(), use_container_width=True)
