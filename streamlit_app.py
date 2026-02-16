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
    .alert-box { border-left: 5px solid #ff4b4b; padding: 10px; background-color: #fff5f5; border-radius: 5px; margin-bottom: 10px; }
    .warn-box { border-left: 5px solid #ffa000; padding: 10px; background-color: #fff9ec; border-radius: 5px; margin-bottom: 10px; }
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

    menu_options = ["📊 แดชบอร์ด", "💊 เบิกจ่ายยา (Bulk)", "📦 รับยาเข้า (Bulk)", "📜 ประวัติรับ-จ่าย", "📝 ข้อมูลยา (Master)"]
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
        st.header("📊 ภาพรวมคลังยา และการแจ้งเตือน")
        try:
            meds = pd.DataFrame(supabase.table("medicines").select("id, generic_name, unit, min_stock").eq("is_active", True).execute().data)
            inv = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
            
            if not meds.empty:
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
                        near_exp_raw = inv_active[inv_active['exp_date'] <= today + pd.Timedelta(days=180)]
                        if not near_exp_raw.empty:
                            near_exp = pd.merge(near_exp_raw, meds, left_on='medicine_id', right_on='id', how='left')
                
                total_items = len(meds)
                total_qty = df_dash['qty'].sum()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("📌 ยาเปิดใช้งาน", f"{total_items}", "รายการ")
                c2.metric("📦 ชิ้นรวมในคลัง", f"{total_qty:,.0f}", "Unit")
                c3.metric("📉 ต่ำกว่าจุดสั่งซื้อ", f"{len(low_stock)}", "รายการ", delta_color="inverse")
                c4.metric("🚨 เสี่ยงหมดอายุ (<6ด.)", f"{len(near_exp)}", "ล็อต", delta_color="inverse")
                
                st.divider()
                
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("### 📉 แจ้งเตือน: ยาใกล้หมดสต๊อก")
                    st.caption("รายการยาที่มียอดคงเหลือน้อยกว่าหรือเท่ากับ 'จุดสั่งซื้อ (Min Stock)'")
                    if not low_stock.empty:
                        for _, row in low_stock.iterrows():
                            st.markdown(f'<div class="warn-box"><strong>{row["generic_name"]}</strong><br>คงเหลือ: <span style="color:red; font-size:18px;"><b>{int(row["qty"])}</b></span> {row["unit"]} (จุดสั่งซื้อ: {row["min_stock"]})</div>', unsafe_allow_html=True)
                    else: st.success("✅ ยอดสต๊อกเพียงพอทุกรายการ")
                with col_r:
                    st.markdown("### 🚨 แจ้งเตือน: ยาใกล้หมดอายุ (FEFO)")
                    st.caption("รายการยาที่จะหมดอายุภายใน 180 วันข้างหน้า (ควรเบิกจ่ายก่อน)")
                    if not near_exp.empty:
                        for _, row in near_exp.iterrows():
                            exp_date = row['exp_date'].strftime('%d/%m/%Y')
                            st.markdown(f'<div class="alert-box"><strong>{row["generic_name"]}</strong><br>Lot: {row["lot_no"]} | เหลือ: {int(row["qty"])} {row["unit"]}<br>📅 <b>หมดอายุ: {exp_date}</b></div>', unsafe_allow_html=True)
                    else: st.success("✅ ไม่มียาเสี่ยงหมดอายุใน 6 เดือน")
            else: st.info("📭 ยังไม่มีข้อมูล Master ยาในระบบ")
        except Exception as e: st.error(f"Error: {e}")

    elif menu == "📜 ประวัติรับ-จ่าย":
        st.header("📜 ประวัติการรับและเบิกจ่ายเวชภัณฑ์")
        tab_history, tab_stockcard = st.tabs(["ประวัติรวมทั้งหมด (All History)", "🗂️ สต๊อกการ์ดแยกรายตัว (Stock Card)"])
        with tab_history:
            st.caption("บันทึกการเคลื่อนไหวของคลังยาทั้งหมด (เรียงจากล่าสุด)")
            df_trans = get_transactions_view()
            if not df_trans.empty:
                df_trans['created_at_dt'] = pd.to_datetime(df_trans['created_at'], utc=True).dt.tz_convert('Asia/Bangkok')
                df_trans['ym'] = df_trans['created_at_dt'].dt.strftime('%Y-%m')
                df_trans['created_at_str'] = df_trans['created_at_dt'].dt.strftime('%d/%m/%Y %H:%M:%S')
                df_trans['action_type_th'] = df_trans['action_type'].map({'RECEIVE': '📥 รับเข้า', 'DISPENSE': '📤 เบิกจ่าย', 'INITIAL': 'ตั้งต้น'}).fillna(df_trans['action_type'])
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    filter_action = st.radio("ตัวกรองประเภท:", ["แสดงทั้งหมด", "📥 เฉพาะรับเข้า", "📤 เฉพาะเบิกจ่าย"], horizontal=True)
                with c2:
                    all_months = df_trans['ym'].dropna().unique().tolist()
                    all_months.sort(reverse=True)
                    month_opts = {"ทั้งหมด": "ดูทุกเดือน (All Time)"}
                    for ym in all_months: month_opts[ym] = format_thai_month(ym)
                    selected_ym = st.selectbox("📅 เลือกเดือน (เดือน/ปี พ.ศ.)", options=["ทั้งหมด"] + all_months, format_func=lambda x: month_opts[x])
                
                df_display = df_trans.copy()
                if filter_action == "📥 เฉพาะรับเข้า": df_display = df_display[df_display['action_type'] == 'RECEIVE']
                elif filter_action == "📤 เฉพาะเบิกจ่าย": df_display = df_display[df_display['action_type'] == 'DISPENSE']
                if selected_ym != "ทั้งหมด": df_display = df_display[df_display['ym'] == selected_ym]
                
                cols_to_show = ['created_at_str', 'action_type_th', 'generic_name', 'lot_no', 'qty_change', 'unit', 'user_name', 'note']
                df_display = df_display[cols_to_show]
                df_display.columns = ['วัน-เวลา', 'ประเภท', 'รายการยา', 'เลข Lot', 'จำนวน (+/-)', 'หน่วย', 'ผู้บันทึก', 'หมายเหตุ']
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
            else: st.info("📭 ยังไม่มีประวัติการทำรายการในระบบ")

        with tab_stockcard:
            st.subheader("🗂️ บัญชีคุมสินค้าคงคลัง (Stock Card)")
            meds = get_medicines()
            if not meds.empty:
                med_options = meds['id'] + " | " + meds['generic_name'] + " (" + meds['unit'] + ")"
                selected_med = st.selectbox("🔍 ค้นหาและเลือกรายการยาที่ต้องการดูประวัติ", med_options)
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
                    df_t['action_type_th'] = df_t['action_type'].map({'RECEIVE': '📥 รับเข้า', 'DISPENSE': '📤 เบิกจ่าย', 'INITIAL': 'ตั้งต้น'}).fillna(df_t['action_type'])
                    
                    all_months_sc = df_t['ym'].dropna().unique().tolist()
                    all_months_sc.sort(reverse=True)
                    month_opts_sc = {"ทั้งหมด": "ดูทุกรอบเดือน (All Time)"}
                    for ym in all_months_sc: month_opts_sc[ym] = format_thai_month(ym)
                    
                    selected_ym_sc = st.selectbox("📅 เลือกดูประวัติเฉพาะเดือน:", options=["ทั้งหมด"] + all_months_sc, format_func=lambda x: month_opts_sc[x])
                    
                    if selected_ym_sc != "ทั้งหมด": df_show = df_t[df_t['ym'] == selected_ym_sc].copy()
                    else: df_show = df_t.copy()
                    
                    cols = ['created_at_str', 'action_type_th', 'lot_no', 'exp_date', 'qty_change', 'running_balance', 'user_name', 'note']
                    df_show = df_show[cols]
                    df_show.columns = ['วัน-เวลา', 'ประเภท', 'เลข Lot', 'วันหมดอายุ', 'จำนวนรับ/จ่าย', f'ยอดคงเหลือ ({selected_unit})', 'ผู้บันทึก', 'หมายเหตุ']
                    
                    st.markdown(f"**ประวัติความเคลื่อนไหว: {selected_name}**")
                    if not df_show.empty: st.dataframe(df_show, use_container_width=True, hide_index=True)
                    else: st.info(f"ไม่พบประวัติการเคลื่อนไหวในเดือนที่เลือก")
                else: st.info(f"📭 ยังไม่มีประวัติการรับ-จ่าย ของยา {selected_name}")

                st.divider()
                st.subheader(f"📦 สรุปยอดคงเหลือปัจจุบัน")
                if not df_i.empty:
                    df_i_active = df_i[df_i['qty'] > 0]
                    if not df_i_active.empty:
                        total_current = df_i_active['qty'].sum()
                        st.metric(f"รวมทั้งสิ้น ({selected_name})", f"{total_current:,} {selected_unit}")
                        st.dataframe(df_i_active[['lot_no', 'exp_date', 'qty']].rename(columns={'lot_no': 'เลข Lot', 'exp_date': 'วันหมดอายุ', 'qty': f'คงเหลือ ({selected_unit})'}), hide_index=True)
                    else: st.warning("ยอดยาในคลังเป็น 0")
                else: st.warning("ไม่มีข้อมูลในคลัง (ยอดยกเป็น 0)")

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
                            amount = st.number_input(f"จำนวนที่เบิก ({row['unit']})", min_value=1, max_value=int(row['qty']), key=f"disp_{i}")
                        st.markdown('</div>', unsafe_allow_html=True)
                        dispense_data.append({
                            'inventory_id': row['id'], 'medicine_id': row['medicine_id'],
                            'lot_no': row['lot_no'], 'current_qty': int(row['qty']), 'dispense_qty': amount
                        })
                        
                    note = st.text_input("หมายเหตุ (เช่น เบิกให้ ER, รพ.สต.เครือข่าย)", value="จ่ายหน้างาน")
                    st.info(f"👤 ผู้บันทึกการเบิกจ่าย: **{st.session_state.user_email}**")
                    
                    if st.form_submit_button("✅ ยืนยันการเบิกจ่ายทั้งหมด", use_container_width=True):
                        try:
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
                        except Exception as e:
                            st.error(f"❌ เกิดข้อผิดพลาดจากฐานข้อมูล: {e}")

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
                with c1: d_choice = st.selectbox("เลือกยา (หน่วยนับ)", med_options, key=f"med_{i}")
                with c2: lot = st.text_input("รหัส Lot", key=f"lot_{i}")
                with c3: mfg = st.date_input("วันผลิต", key=f"mfg_{i}")
                with c4: exp = st.date_input("วันหมดอายุ", key=f"exp_{i}")
                
                selected_id = d_choice.split(" | ")[0]
                qty = st.number_input("จำนวนที่รับเข้า", min_value=1, key=f"qty_{i}")
                st.markdown("---")
                receive_data.append({
                    "medicine_id": selected_id, "lot_no": lot,
                    "mfg_date": str(mfg), "exp_date": str(exp), "qty": qty
                })
                
            st.info(f"👤 ผู้บันทึกการรับเข้า: **{st.session_state.user_email}**")
            
            if st.form_submit_button("📥 บันทึกรับเข้าทั้งหมด", use_container_width=True):
                try:
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
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล: {e}")
                    st.info("💡 **วิธีแก้เบื้องต้น:**\n1. โปรดตรวจสอบว่าตาราง `inventory` ใน Supabase มีคอลัมน์ `mfg_date` (ชนิด DATE) แล้วหรือยัง\n2. คุณอาจกรอกรหัส Lot ที่เคยมีอยู่ในระบบแล้ว (ถ้าใน Supabase ตั้งค่าให้รหัส Lot ห้ามซ้ำ)")

    elif menu == "📝 ข้อมูลยา (Master)":
        st.header("📝 จัดการบัญชียาหลัก")
        tab1, tab2, tab3 = st.tabs(["➕ เพิ่มรายการใหม่", "📋 รายการที่มีอยู่", "✏️ แก้ไข / ลบข้อมูลยา"])
        
        with tab1:
            with st.form("new_med"):
                c1, c2 = st.columns(2)
                nid = c1.text_input("รหัสยา (เช่น DRUG009)")
                nname = c2.text_input("ชื่อสามัญ (Generic Name)")
                nunit = c1.text_input("หน่วยนับ (เช่น เม็ด, ขวด, หลอด)")
                ncat = c2.selectbox("หมวดหมู่", ["ยาในบัญชี", "ยานอกบัญชี", "เวชภัณฑ์/วัสดุ"])
                nmin = st.number_input("จุดสั่งซื้อ (Min Stock) เตือนเมื่อยาใกล้หมด", min_value=0, value=100)
                
                if st.form_submit_button("💾 เพิ่มข้อมูลยา", use_container_width=True):
                    if nid and nname and nunit:
                        try:
                            supabase.table("medicines").insert({"id": nid, "generic_name": nname, "unit": nunit, "category": ncat, "min_stock": nmin, "is_active": True}).execute()
                            st.success("เพิ่มข้อมูลสำเร็จ!"); time.sleep(1); st.rerun()
                        except: st.error("❌ รหัสยาซ้ำ หรือกรอกข้อมูลไม่ถูกต้อง")
                    else: st.warning("⚠️ กรุณากรอกรหัสยา ชื่อยา และหน่วยนับให้ครบถ้วน")
                        
        with tab2:
            st.info("💡 แสดงเฉพาะรายการยาที่เปิดใช้งานอยู่ (Active)")
            st.dataframe(get_medicines(), use_container_width=True)
            
        with tab3:
            all_meds_data = supabase.table("medicines").select("*").execute().data
            if all_meds_data:
                all_meds = pd.DataFrame(all_meds_data)
                
                all_meds['display_name'] = all_meds['id'].astype(str) + " | " + all_meds['generic_name'].fillna('-ไม่มีชื่อยา-').astype(str)
                
                edit_choice = st.selectbox("🔍 ค้นหาและเลือกยาที่ต้องการแก้ไข หรือ ลบ", all_meds['display_name'])
                
                if edit_choice:
                    selected_id = edit_choice.split(" | ")[0]
                    med_info = all_meds[all_meds['id'] == selected_id].iloc[0]
                    
                    st.divider()
                    
                    with st.form("edit_med_form"):
                        st.caption(f"รหัสยา (ID): **{selected_id}** (ไม่สามารถแก้ไขรหัสได้)")
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
                        e_active = st.checkbox("✅ เปิดใช้งานรายการนี้ (สามารถนำไปรับ/เบิกได้ปกติ)", value=bool(med_info['is_active']))
                        
                        if st.form_submit_button("💾 บันทึกการแก้ไข", use_container_width=True):
                            if e_name and e_unit:
                                try:
                                    supabase.table("medicines").update({"generic_name": e_name, "unit": e_unit, "category": e_cat, "min_stock": e_min, "is_active": e_active}).eq("id", selected_id).execute()
                                    st.success(f"อัปเดตข้อมูลของ {selected_id} สำเร็จ!"); time.sleep(1); st.rerun()
                                except Exception as e: st.error(f"❌ เกิดข้อผิดพลาดในการอัปเดต: {e}")
                            else: st.warning("⚠️ กรุณากรอกชื่อยาและหน่วยนับให้ครบถ้วน")
                    
                    st.divider()
                    st.markdown("### 🗑️ ลบข้อมูล (Danger Zone)")
                    st.warning("⚠️ แนะนำให้ใช้วิธี **'เอาเครื่องหมายถูกเปิดใช้งานออก'** แทนการลบ เพื่อเก็บประวัติไว้ตรวจสอบ \n\n (ระบบจะอนุญาตให้ลบถาวรได้ **เฉพาะรายการที่ไม่เคยมีประวัติรับ-จ่าย** เท่านั้น เพื่อป้องกันข้อมูลบัญชีผิดพลาด)")
                    
                    del_col1, del_col2 = st.columns([1, 1])
                    with del_col1:
                        confirm_del = st.checkbox("ยืนยันว่าต้องการลบรายการนี้ทิ้งถาวร", key="confirm_delete_box")
                    with del_col2:
                        if st.button("❌ ลบรายการยานี้ถาวร", type="primary", use_container_width=True):
                            if confirm_del:
                                try:
                                    supabase.table("medicines").delete().eq("id", selected_id).execute()
                                    st.success(f"ลบรายการยา {selected_id} ออกจากระบบเรียบร้อยแล้ว!")
                                    time.sleep(1.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error("❌ ไม่สามารถลบได้! เนื่องจากยานี้เคยถูกทำรายการรับ/เบิกไปแล้ว (กรุณาใช้วิธีปิดใช้งานแทน)")
                            else:
                                st.error("กรุณาติ๊กเครื่องหมายถูกที่ 'ยืนยันว่าต้องการลบ' ก่อนกดปุ่มลบครับ")
            else: st.info("📭 ยังไม่มีข้อมูลยาในระบบ")
