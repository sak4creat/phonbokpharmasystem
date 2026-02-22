import os
import requests
import json
import pandas as pd
import datetime
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
LINE_TOKEN = os.environ.get("LINE_BOT_TOKEN")
LINE_TARGET_ID = os.environ.get("LINE_TARGET_ID")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

THAI_MONTHS = {'01': 'มกราคม', '02': 'กุมภาพันธ์', '03': 'มีนาคม', '04': 'เมษายน', '05': 'พฤษภาคม', '06': 'มิถุนายน', '07': 'กรกฎาคม', '08': 'สิงหาคม', '09': 'กันยายน', '10': 'ตุลาคม', '11': 'พฤศจิกายน', '12': 'ธันวาคม'}

def send_line_message(token, target_id, message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    data = {"to": target_id, "messages": [{"type": "text", "text": message}]}
    requests.post(url, headers=headers, data=json.dumps(data))

def generate_and_send_report():
    today = datetime.date.today()
    first_day_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_day_of_this_month - datetime.timedelta(days=1)
    first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
    
    month_name = THAI_MONTHS.get(last_day_of_prev_month.strftime('%m'))
    year_th = last_day_of_prev_month.year + 543
    report_title = f"📊 สรุปคลังเวชภัณฑ์ประจำเดือน {month_name} {year_th}"

    try:
        meds_res = supabase.table("medicines").select("id, generic_name, unit, min_stock, category").eq("is_active", True).execute()
        meds = pd.DataFrame(meds_res.data)
        inv_df = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
        trans_res = supabase.table("transactions").select("*").gte("created_at", str(first_day_of_prev_month)).lt("created_at", str(first_day_of_this_month)).execute()
        trans_df = pd.DataFrame(trans_res.data)
    except Exception as e:
        send_line_message(LINE_TOKEN, LINE_TARGET_ID, f"❌ เกิดข้อผิดพลาดการดึงข้อมูลจากฐานข้อมูล: {e}")
        return

    if meds.empty:
        msg_part1 = "\n\n❌ ไม่พบข้อมูล Master Data ในระบบ"
        msg_part2 = "\n\n📥 รับเข้ามากที่สุด 5 อันดับ:\n(ไม่มีการเคลื่อนไหว)"
        msg_part3 = "\n\n📤 เบิกจ่ายมากที่สุด 5 อันดับ:\n(ไม่มีการเคลื่อนไหว)"
        msg_part4 = "\n\n⚠️ แจ้งเตือน: ต่ำกว่าจุดสั่งซื้อ\n(ไม่มีข้อมูล Master Data)"
        msg_part5 = "\n\n⏰ แจ้งเตือน: ใกล้หมดอายุ (<90 วัน)\n(ไม่มีข้อมูลสต๊อก)"
        final_message = report_title + msg_part1 + msg_part2 + msg_part3 + msg_part4 + msg_part5
        send_line_message(LINE_TOKEN, LINE_TARGET_ID, final_message)
        return

    meds['category'] = meds['category'].astype(str).str.strip() 

    # 🌟 1. ข้อมูล ณ ปัจจุบัน (นับเฉพาะที่มีของในคลัง > 0)
    drugs_in_stock = 0
    supplies_in_stock = 0
    if not inv_df.empty:
        inv_agg_current = inv_df.groupby('medicine_id')['qty'].sum().reset_index()
        inv_active_current = inv_agg_current[inv_agg_current['qty'] > 0]
        if not inv_active_current.empty:
            active_meds = pd.merge(inv_active_current, meds, left_on='medicine_id', right_on='id', how='left')
            drugs_in_stock = len(active_meds[active_meds['category'].isin(['ยาในบัญชี', 'ยานอกบัญชี', 'เวชภัณฑ์ยา'])])
            supplies_in_stock = len(active_meds[active_meds['category'].isin(['เวชภัณฑ์/วัสดุ', 'เวชภัณฑ์ที่มิใช่ยา'])])

    msg_part1 = f"\n\n🏥 ข้อมูล ณ ปัจจุบัน (ที่มียอดคงเหลือ):\n- เวชภัณฑ์ยา: {drugs_in_stock} รายการ\n- เวชภัณฑ์มิใช่ยา: {supplies_in_stock} รายการ"

    # 🌟 2. สรุปการรับ-จ่าย
    msg_part2 = "\n\n📥 รับเข้ามากที่สุด 5 อันดับ:"
    msg_part3 = "\n\n📤 เบิกจ่ายมากที่สุด 5 อันดับ:"
    
    if not trans_df.empty:
        df_merged = pd.merge(trans_df, meds[['id', 'generic_name', 'unit']], left_on='medicine_id', right_on='id', how='left')
        
        df_recv = df_merged[df_merged['action_type'] == 'RECEIVE'].groupby('generic_name')['qty_change'].sum().reset_index()
        df_recv = df_recv.sort_values(by='qty_change', ascending=False).head(5)
        if not df_recv.empty:
            for idx, row in df_recv.iterrows():
                unit_vals = meds[meds['generic_name'] == row['generic_name']]['unit'].values
                unit = unit_vals[0] if len(unit_vals) > 0 else ''
                msg_part2 += f"\n{idx+1}. {row['generic_name']} (+{int(row['qty_change'])} {unit})"
        else: msg_part2 += "\n(ไม่มีการเคลื่อนไหว)"

        df_disp = df_merged[df_merged['action_type'] == 'DISPENSE'].copy()
        df_disp['qty_change'] = df_disp['qty_change'].abs()
        df_disp = df_disp.groupby('generic_name')['qty_change'].sum().reset_index()
        df_disp = df_disp.sort_values(by='qty_change', ascending=False).head(5)
        if not df_disp.empty:
            for idx, row in df_disp.iterrows():
                unit_vals = meds[meds['generic_name'] == row['generic_name']]['unit'].values
                unit = unit_vals[0] if len(unit_vals) > 0 else ''
                msg_part3 += f"\n{idx+1}. {row['generic_name']} (-{int(row['qty_change'])} {unit})"
        else: msg_part3 += "\n(ไม่มีการเคลื่อนไหว)"
    else:
        msg_part2 += "\n(ไม่มีการเคลื่อนไหว)"
        msg_part3 += "\n(ไม่มีการเคลื่อนไหว)"

    # 🌟 3. ต่ำกว่าจุดสั่งซื้อ (แสดงแค่ยอดรวม ตัดรายชื่อทิ้ง)
    msg_part4 = "\n\n⚠️ แจ้งเตือน: ต่ำกว่าจุดสั่งซื้อ"
    
    if not inv_df.empty:
        inv_agg = inv_df.groupby('medicine_id')['qty'].sum().reset_index()
        df_stock = pd.merge(meds, inv_agg, left_on='id', right_on='medicine_id', how='left')
        df_stock['qty'] = df_stock['qty'].fillna(0)
    else:
        df_stock = meds.copy()
        df_stock['qty'] = 0
        
    df_stock['qty'] = pd.to_numeric(df_stock['qty'], errors='coerce').fillna(0)
    df_stock['min_stock'] = pd.to_numeric(df_stock['min_stock'], errors='coerce').fillna(0)
        
    low_stock = df_stock[df_stock['qty'] <= df_stock['min_stock']]
    low_total = len(low_stock)
    low_drugs = len(low_stock[low_stock['category'].isin(['ยาในบัญชี', 'ยานอกบัญชี', 'เวชภัณฑ์ยา'])])
    low_supplies = len(low_stock[low_stock['category'].isin(['เวชภัณฑ์/วัสดุ', 'เวชภัณฑ์ที่มิใช่ยา'])])

    msg_part4 += f"\nรวมทั้งหมด {low_total} รายการ แบ่งเป็น:"
    msg_part4 += f"\n💊 เวชภัณฑ์ยา จำนวน {low_drugs} รายการ"
    msg_part4 += f"\n📦 เวชภัณฑ์ที่มิใช่ยา จำนวน {low_supplies} รายการ"

    # 🌟 4. แจ้งเตือนใกล้หมดอายุ
    msg_part5 = "\n\n⏰ แจ้งเตือน: ใกล้หมดอายุ (<90 วัน)"
    if not inv_df.empty:
        inv_active = inv_df[inv_df['qty'] > 0].copy()
        if not inv_active.empty:
            inv_active['exp_date'] = pd.to_datetime(inv_active['exp_date'])
            near_exp_raw = inv_active[inv_active['exp_date'] <= pd.to_datetime(today) + pd.Timedelta(days=90)]
            if not near_exp_raw.empty:
                near_exp = pd.merge(near_exp_raw, meds[['id', 'generic_name']], left_on='medicine_id', right_on='id', how='left')
                msg_part5 += f" ({len(near_exp)} ล็อต)"
                count_exp = 0
                for _, row in near_exp.iterrows():
                    if count_exp >= 10: break
                    exp_str = row['exp_date'].strftime('%d/%m/%Y')
                    msg_part5 += f"\n- {row['generic_name']} (Lot: {row['lot_no']})\n  เหลือ {int(row['qty'])} | หมด: {exp_str}"
                    count_exp += 1
                if len(near_exp) > 10: 
                    msg_part5 += f"\n...และอื่นๆ อีก {len(near_exp)-10} ล็อต"
            else: 
                msg_part5 += "\n(ไม่มีรายการเสี่ยงหมดอายุ)"
        else: 
            msg_part5 += "\n(ไม่มีรายการเสี่ยงหมดอายุ)"
    else: 
        msg_part5 += "\n(ไม่มีข้อมูลสต๊อก)"

    final_message = report_title + msg_part1 + msg_part2 + msg_part3 + msg_part4 + msg_part5
    send_line_message(LINE_TOKEN, LINE_TARGET_ID, final_message)

if __name__ == "__main__":
    generate_and_send_report()
