import os
import requests
import json
import pandas as pd
import datetime
from supabase import create_client

# 1. ดึงกุญแจความลับจาก GitHub Secrets
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

    meds_res = supabase.table("medicines").select("*").eq("is_active", True).execute()
    meds = pd.DataFrame(meds_res.data)
    inv_df = pd.DataFrame(supabase.table("inventory").select("*").execute().data)
    trans_res = supabase.table("transactions").select("*").gte("created_at", str(first_day_of_prev_month)).lt("created_at", str(first_day_of_this_month)).execute()
    trans_df = pd.DataFrame(trans_res.data)

    if not meds.empty:
        drugs_count = len(meds[meds['category'].isin(['ยาในบัญชี', 'ยานอกบัญชี', 'เวชภัณฑ์ยา'])])
        supplies_count = len(meds[meds['category'].isin(['เวชภัณฑ์/วัสดุ', 'เวชภัณฑ์ที่มิใช่ยา'])])
    else:
        drugs_count, supplies_count = 0, 0

    msg_part1 = f"\n\n🏥 ข้อมูล ณ ปัจจุบัน:\n- เวชภัณฑ์ยา: {drugs_count} รายการ\n- เวชภัณฑ์มิใช่ยา: {supplies_count} รายการ"
    msg_part2 = "\n\n📥 รับเข้ามากที่สุด 5 อันดับ:"
    msg_part3 = "\n\n📤 เบิกจ่ายมากที่สุด 5 อันดับ:"
    
    if not trans_df.empty and not meds.empty:
        df_merged = pd.merge(trans_df, meds[['id', 'generic_name', 'unit']], left_on='medicine_id', right_on='id', how='left')
        df_recv = df_merged[df_merged['action_type'] == 'RECEIVE'].groupby('generic_name')['qty_change'].sum().reset_index().sort_values(by='qty_change', ascending=False).head(5)
        if not df_recv.empty:
            for idx, row in df_recv.iterrows():
                unit = meds[meds['generic_name'] == row['generic_name']]['unit'].values[0] if not meds[meds['generic_name'] == row['generic_name']].empty else ''
                msg_part2 += f"\n{idx+1}. {row['generic_name']} (+{int(row['qty_change'])} {unit})"
        else: msg_part2 += "\n(ไม่มีรายการรับเข้า)"

        df_disp = df_merged[df_merged['action_type'] == 'DISPENSE'].copy()
        df_disp['qty_change'] = df_disp['qty_change'].abs()
        df_disp = df_disp.groupby('generic_name')['qty_change'].sum().reset_index().sort_values(by='qty_change', ascending=False).head(5)
        if not df_disp.empty:
            for idx, row in df_disp.iterrows():
                unit = meds[meds['generic_name'] == row['generic_name']]['unit'].values[0] if not meds[meds['generic_name'] == row['generic_name']].empty else ''
                msg_part3 += f"\n{idx+1}. {row['generic_name']} (-{int(row['qty_change'])} {unit})"
        else: msg_part3 += "\n(ไม่มีรายการเบิกจ่าย)"
    else:
        msg_part2 += "\n(ไม่มีการเคลื่อนไหว)"
        msg_part3 += "\n(ไม่มีการเคลื่อนไหว)"

    # 🌟 ส่วนที่ปรับแก้ใหม่: บังคับแสดงยอดสรุปยา/มิใช่ยา เสมอ
    msg_part4 = "\n\n⚠️ แจ้งเตือน: ต่ำกว่าจุดสั่งซื้อ"
    low_total = 0
    low_drugs = 0
    low_supplies = 0
    low_stock = pd.DataFrame()

    if not meds.empty:
        if not inv_df.empty:
            inv_agg = inv_df.groupby('medicine_id')['qty'].sum().reset_index()
            df_stock = pd.merge(meds, inv_agg, left_on='id', right_on='medicine_id', how='left')
            df_stock['qty'] = df_stock['qty'].fillna(0)
        else:
            df_stock = meds.copy()
            df_stock['qty'] = 0
            
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
        msg_part4 += "✅ สต๊อกเพียงพอทุกรายการ"

    msg_part5 = "\n\n⏰ ใกล้หมดอายุ (<90 วัน)"
    if not inv_df.empty:
        inv_active = inv_df[inv_df['qty'] > 0].copy()
        if not inv_active.empty:
            inv_active['exp_date'] = pd.to_datetime(inv_active['exp_date'])
            near_exp_raw = inv_active[inv_active['exp_date'] <= pd.to_datetime(today) + pd.Timedelta(days=90)]
            if not near_exp_raw.empty:
                near_exp = pd.merge(near_exp_raw, meds[['id', 'generic_name']], left_on='medicine_id', right_on='id', how='left')
                msg_part5 += f" ({len(near_exp)} ล็อต)"
                for _, row in near_exp.head(10).iterrows():
                    msg_part5 += f"\n- {row['generic_name']}\n  เหลือ {int(row['qty'])} | หมด: {row['exp_date'].strftime('%d/%m/%Y')}"
                if len(near_exp) > 10: msg_part5 += f"\n...และอื่นๆ อีก {len(near_exp)-10} ล็อต"
            else: msg_part5 += "\n✅ ไม่มีเวชภัณฑ์ใกล้หมดอายุ"
        else: msg_part5 += "\n✅ ไม่มีเวชภัณฑ์ใกล้หมดอายุ"
    else: msg_part5 += "\n✅ ไม่มีข้อมูลสต๊อก"

    final_message = report_title + msg_part1 + msg_part2 + msg_part3 + msg_part4 + msg_part5
    send_line_message(LINE_TOKEN, LINE_TARGET_ID, final_message)

if __name__ == "__main__":
    generate_and_send_report()
