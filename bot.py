import json
import os
import threading
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import telebot
from telebot.types import ReplyKeyboardMarkup
from collections import defaultdict

DATA_FILE = "attendance.json"
REGISTER_FILE = "registered_users.json"

ATTENDANCE = defaultdict(lambda: defaultdict(dict))
REGISTERED_USERS = set()

def load_attendance():
    global ATTENDANCE
    if not os.path.exists(DATA_FILE):
        print("📂 attendance.json not found, starting fresh")
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        for uid, months in raw.items():
            uid = int(uid)
            for month, days in months.items():
                for day, rec in days.items():
                    ATTENDANCE[uid][month][day] = {}

                    # ===== 上下班时间 =====
                    if rec.get("checkin"):
                        ATTENDANCE[uid][month][day]["checkin"] = datetime.fromisoformat(rec["checkin"])

                    if rec.get("checkout"):
                        ATTENDANCE[uid][month][day]["checkout"] = datetime.fromisoformat(rec["checkout"])

                    # ===== 早班/晚班上班时间 =====
                    if rec.get("morning_checkin"):
                        ATTENDANCE[uid][month][day]["morning_checkin"] = datetime.fromisoformat(rec["morning_checkin"])

                    if rec.get("morning_checkout"):
                        ATTENDANCE[uid][month][day]["morning_checkout"] = datetime.fromisoformat(rec["morning_checkout"])

                    if rec.get("night_checkin"):
                        ATTENDANCE[uid][month][day]["night_checkin"] = datetime.fromisoformat(rec["night_checkin"])

                    if rec.get("night_checkout"):
                        ATTENDANCE[uid][month][day]["night_checkout"] = datetime.fromisoformat(rec["night_checkout"])

                    # ===== 迟到 / 早退 =====
                    ATTENDANCE[uid][month][day]["late_minutes"] = rec.get("late_minutes", 0)
                    ATTENDANCE[uid][month][day]["early_leave_minutes"] = rec.get("early_leave_minutes", 0)

                    # ===== HR 多 slot 打卡 (checkin_2/checkout_2, checkin_3/checkout_3...) =====
                    slot = 2
                    while True:
                        ck = f"checkin_{slot}"
                        co = f"checkout_{slot}"
                        if not rec.get(ck) and not rec.get(co):
                            break
                        if rec.get(ck):
                            ATTENDANCE[uid][month][day][ck] = datetime.fromisoformat(rec[ck])
                        if rec.get(co):
                            ATTENDANCE[uid][month][day][co] = datetime.fromisoformat(rec[co])
                        slot += 1

        print("✅ Attendance loaded from JSON")

    except Exception as e:
        print("❌ Failed to load attendance.json:", e)

def load_registered_users():
    global REGISTERED_USERS
    if not os.path.exists(REGISTER_FILE):
        print("📂 registered_users.json not found, starting fresh")
        return

    try:
        with open(REGISTER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            REGISTERED_USERS = set(map(int, data))
        print("✅ Registered users loaded")
    except Exception as e:
        print("❌ Failed to load registered users:", e)


def save_registered_users():
    try:
        with open(REGISTER_FILE, "w", encoding="utf-8") as f:
            json.dump(list(REGISTERED_USERS), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("❌ Failed to save registered users:", e)

def save_attendance():
    data = {}

    for uid, months in ATTENDANCE.items():
        data[str(uid)] = {}
        for month, days in months.items():
            data[str(uid)][month] = {}
            for day, rec in days.items():
                day_data = {
                    "checkin": rec.get("checkin").isoformat() if rec.get("checkin") else None,
                    "checkout": rec.get("checkout").isoformat() if rec.get("checkout") else None,

                    "morning_checkin": rec.get("morning_checkin").isoformat() if rec.get("morning_checkin") else None,
                    "morning_checkout": rec.get("morning_checkout").isoformat() if rec.get("morning_checkout") else None,
                    "night_checkin": rec.get("night_checkin").isoformat() if rec.get("night_checkin") else None,
                    "night_checkout": rec.get("night_checkout").isoformat() if rec.get("night_checkout") else None,

                    "late_minutes": rec.get("late_minutes", 0),
                    "early_leave_minutes": rec.get("early_leave_minutes", 0),
                }
                # 保存 HR 多 slot 打卡
                slot = 2
                while True:
                    ck_key = f"checkin_{slot}"
                    co_key = f"checkout_{slot}"
                    if not rec.get(ck_key) and not rec.get(co_key):
                        break
                    if rec.get(ck_key):
                        day_data[ck_key] = rec[ck_key].isoformat()
                    if rec.get(co_key):
                        day_data[co_key] = rec[co_key].isoformat()
                    slot += 1
                data[str(uid)][month][day] = day_data

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("❌ Failed to save attendance.json:", e)

# ===== Timezone =====
LOCAL_TZ = ZoneInfo("Asia/Yangon")  # 缅甸

def now():
    return datetime.now(LOCAL_TZ)

# ===== Load env =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
admin_ids_str = os.getenv("ADMIN_IDS", "6062973135,8530505686")
ADMIN_IDS = set(int(x.strip()) for x in admin_ids_str.split(",") if x.strip())
LATE_BOT_TOKEN = os.getenv("LATE_BOT_TOKEN")
LATE_GROUP_ID = int(os.getenv("LATE_GROUP_ID")) if os.getenv("LATE_GROUP_ID") else None

late_bot = None
if LATE_BOT_TOKEN and LATE_GROUP_ID:
    late_bot = telebot.TeleBot(LATE_BOT_TOKEN)

if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN is not set")

bot = telebot.TeleBot(BOT_TOKEN)

# ===== Config =====
ACTIVITY_TIMES = {
    "Eating": 30,
    "ToiletLarge": 15,
    "ToiletSmall": 10,
    "Smoking": 10,
    "Other": 15,
}

MAX_TIMES = {
    "Eating": 3,
    "ToiletLarge": 1,
    "ToiletSmall": 4,
    "Smoking": 4,
    "Other": 2,
}

ACTIVITY_LABELS = {
    "Eating": "Eat",
    "ToiletLarge": "Toilet",
    "ToiletSmall": "Pee",
    "Smoking": "Smoking",
    "Other": "Other",
}

def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1:'st', 2:'nd', 3:'rd'}.get(n % 10, 'th') }"

# ===== 用户配置 =====
HR_USERS = {6917597442, 7501352060, 6028186424}
FINDING_USERS = {7375446542, 6438074082,8349071207,8338442147,7756175751,7636774148}
CUSTOM_NIGHT_USERS = {6863315227,2018656742,7794920274,6635424294,2094656277,1625231530,7961174070,7995766218}

# ===== Memory =====
user_activity = {}
user_sessions = {}
CHECK_IN_STATUS = {}
user_logs = {}
activity_timeout = {}

# ===== Keyboard =====
def main_keyboard(uid=None):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏢 Check In", "🏠 Check Out")
    kb.row("🍽 Eat", "🚬 Smoking")
    kb.row("💧 Pee", "🚽 Toilet")
    kb.row("📝 Other", "↩ Return")
    if uid is not None and uid in ADMIN_IDS:
        kb.row("/set_month_shifts", "/batch_set_month_shifts")
    return kb

# ===== Stats =====
def stats_text(uid):
    user_sessions.setdefault(uid, {"Eating": 0, "ToiletLarge": 0, "ToiletSmall": 0, "Smoking": 0, "Other": 0})
    s = user_sessions[uid]
    return (
        f"👤 User ID: {uid}\n\n"
        f"🍽 Eat: {s['Eating']} / {MAX_TIMES['Eating']} TIME\n"
        f"💧 Pee: {s['ToiletSmall']} / {MAX_TIMES['ToiletSmall']} TIME\n"
        f"🚽 Toilet: {s['ToiletLarge']} / {MAX_TIMES['ToiletLarge']} TIME\n"
        f"🚬 Smoking: {s['Smoking']} / {MAX_TIMES['Smoking']} TIME\n"
        f"📝 Other: {s['Other']} / {MAX_TIMES['Other']} TIME"
    )

def get_attendance_summary(uid):
    if uid not in ATTENDANCE:
        return 0, 0
    now_dt = now()
    current_month = now_dt.strftime("%Y-%m")
    total_days = set()
    month_shifts = 0

    for month, days in ATTENDANCE[uid].items():
        # 不是当月则跳过，实现每月1号自动清零
        if month != current_month:
            continue
        for day, rec in days.items():
            full_date = f"{month}-{day[-2:]}"

            # 统一统计：遍历所有可能的打卡字段，不区分用户类型
            # 1. HR 多 slot: checkin, checkin_2, checkin_3...
            slot = 1
            while True:
                key = "checkin" if slot == 1 else f"checkin_{slot}"
                if rec.get(key):
                    total_days.add(full_date)
                    month_shifts += 1
                    slot += 1
                else:
                    break

            # 2. FINDING/PROMO: morning_checkin 和 night_checkin
            if rec.get("morning_checkin"):
                total_days.add(full_date)
                month_shifts += 1
            if rec.get("night_checkin"):
                total_days.add(full_date)
                month_shifts += 1

    return month_shifts, len(total_days)

def get_shift_standard(dt, uid):
    t = dt.time()
    if uid in HR_USERS:
        return {"role": "HR", "shift": "DAY", "start": time(9, 0), "end": time(19, 0)}
    if uid in FINDING_USERS:
        if time(7, 0) <= t <= time(12, 0):
            return {"role": "FINDING", "shift": "MORNING", "start": time(7, 0), "end": time(12, 0)}
        if t >= time(19, 0) or t < time(2, 0):
            return {"role": "FINDING", "shift": "NIGHT", "start": time(19, 0), "end": time(2, 0), "cross_day": True}
        return {"role": "FINDING", "shift": "MORNING", "start": time(7, 0), "end": time(12, 0)}
    return {"role": "PROMO", "shift": "NIGHT", "start": time(20, 30), "end": time(9, 30), "cross_day": True}

def get_attribution_date(checkin_logical_date, checkout_dt, uid, shift_info):
    """根据 checkout 时间决定这个班次最终归属哪一天（缅甸时间）"""
    checkout_date = checkout_dt.date()
    checkout_time = checkout_dt.time()

    # 同一天 checkout → 直接归 checkin 那天
    if checkout_date == checkin_logical_date:
        return checkin_logical_date

    # 跨天了 → 按截止时间判定
    if uid in HR_USERS:
        # HR: checkout 超过凌晨 0:00 → 归 checkout 当天
        return checkout_date

    elif uid in FINDING_USERS:
        if shift_info.get("shift") == "NIGHT":
            # 晚班: checkout 在凌晨 2:00 内 → 归 checkin 那天（前一天）
            if checkout_time < time(2, 0):
                return checkin_logical_date
            return checkout_date
        else:
            # 早班: checkout 在下午 5:00 内 → 归 checkin 那天
            if checkout_time < time(17, 0):
                return checkin_logical_date
            return checkout_date

    else:
        # CHATTING/PROMO: checkout 在中午 12:00 前 → 归 checkin 那天（前一天）
        if checkout_time < time(12, 0):
            return checkin_logical_date
        return checkout_date

# ===== Send functions =====
def send_group(msg, parse_mode=None):
    if not GROUP_CHAT_ID:
        return
    try:
        bot.send_message(GROUP_CHAT_ID, msg, parse_mode=parse_mode)
    except Exception as e:
        print("❌ send_group failed:", e)

def send_late_notice(msg, parse_mode=None):
    if late_bot and LATE_GROUP_ID:
        try:
            late_bot.send_message(LATE_GROUP_ID, msg, parse_mode=parse_mode)
        except Exception as e:
            print("❌ send_late_notice failed:", e)

# ===== 未打卡提醒 =====
MISSED_CHECK_SENT = set()

def check_missing_checkins():
    while True:
        try:
            now_dt = now()
            today = now_dt.date()
            all_staff = REGISTERED_USERS

            for uid in all_staff:
                month_key = today.strftime("%Y-%m")
                date_key = today.strftime("%Y-%m-%d")
                rec = ATTENDANCE.get(uid, {}).get(month_key, {}).get(date_key, {})

                if uid in HR_USERS:
                    limit_dt = datetime.combine(today, time(9, 4), tzinfo=LOCAL_TZ)
                    key = (uid, "HR_DAY", today)
                    if limit_dt <= now_dt < limit_dt + timedelta(seconds=60) and key not in MISSED_CHECK_SENT:
                        if not rec.get("checkin"):
                            send_late_notice_by_id(uid, "HR")
                            MISSED_CHECK_SENT.add(key)
                    continue

                if uid in FINDING_USERS:
                    m_limit = datetime.combine(today, time(7, 4), tzinfo=LOCAL_TZ)
                    key_m = (uid, "FINDING_M", today)
                    if m_limit <= now_dt < m_limit + timedelta(seconds=60) and key_m not in MISSED_CHECK_SENT:
                        if not rec.get("morning_checkin"):
                            send_late_notice_by_id(uid, "FINDING 早班")
                            MISSED_CHECK_SENT.add(key_m)
                    
                    n_limit = datetime.combine(today, time(19, 4), tzinfo=LOCAL_TZ)
                    key_n = (uid, "FINDING_N", today)
                    if n_limit <= now_dt < n_limit + timedelta(seconds=60) and key_n not in MISSED_CHECK_SENT:
                        if not rec.get("night_checkin"):
                            send_late_notice_by_id(uid, "FINDING 晚班")
                            MISSED_CHECK_SENT.add(key_n)
                    continue

                p_limit = datetime.combine(today, time(20, 34), tzinfo=LOCAL_TZ)
                key_p = (uid, "PROMO_NIGHT_NEW", today)
                if p_limit <= now_dt < p_limit + timedelta(seconds=60) and key_p not in MISSED_CHECK_SENT:
                    if not rec.get("checkin") and not rec.get("night_checkin"):
                        send_late_notice_by_id(uid, "推广/夜班(20:30)")
                        MISSED_CHECK_SENT.add(key_p)

        except Exception as e:
            print("❌ missing checkin loop error:", e)

        threading.Event().wait(30)

def send_late_notice_by_id(uid, role_name):
    try:
        chat = bot.get_chat(uid)
        name = chat.first_name or "User"
        # 🟢【未打卡】两群同步发送 HTML @通知
        notice = f"👤 <a href=\"tg://user?id={uid}\">{name}</a>💸+{uid} {role_name} 未打卡 ⚠️"
        send_late_notice(notice, parse_mode="HTML")
        send_group(notice, parse_mode="HTML") 
    except Exception as e:
        print(f"Notice error for {uid}: {e}")

# ===== Commands =====
@bot.message_handler(commands=["start"])
def start(message):
    if message.from_user.is_bot:
        return
    uid = message.from_user.id

    if uid not in REGISTERED_USERS:
        REGISTERED_USERS.add(uid)
        save_registered_users()

    if uid in CHECK_IN_STATUS:
        status_line = f"🟢 已上班：{CHECK_IN_STATUS[uid]['time'].strftime('%H:%M:%S')}"
    else:
        status_line = "🔴 未上班"

    panel_msg = (
        f"✅ 已注册\n"
        f"{status_line}\n\n"
        f"{stats_text(uid)}"
    )
    bot.send_message(message.chat.id, panel_msg, reply_markup=main_keyboard(uid))

@bot.message_handler(commands=["attendance"])
def attendance_report(message):
    bot.reply_to(message, "📊 考勤统计功能已关闭")

# ===== 管理员命令：修改员工考勤 =====
@bot.message_handler(commands=["modify_attendance"])
def modify_attendance(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        bot.reply_to(message, "❌ 仅管理员可操作")
        return
    
    args = message.text.split()
    if len(args) < 5:
        bot.reply_to(message, "用法: /modify_attendance <用户ID> <年月日> <checkin/checkout> <时间>\n例: /modify_attendance 6917597442 2024-06-02 checkin 09:00:00")
        return
    
    try:
        target_uid = int(args[1])
        date_str = args[2]
        action = args[3]
        time_str = args[4]
        
        # 解析日期时间
        dt_str = f"{date_str} {time_str}"
        new_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOCAL_TZ)
        
        # 确定月份和日期
        month_key = new_dt.strftime("%Y-%m")
        date_key = new_dt.strftime("%Y-%m-%d")
        
        # 确保数据结构存在
        ATTENDANCE[target_uid].setdefault(month_key, {})
        ATTENDANCE[target_uid][month_key].setdefault(date_key, {})
        day_rec = ATTENDANCE[target_uid][month_key][date_key]
        
        # 根据用户类型确定要修改的字段
        if target_uid in HR_USERS:
            # HR: 修改或添加 checkin 记录
            if action == "checkin":
                # 找到下一个可用 slot
                slot = 1
                while day_rec.get(f"checkin_{slot}" if slot > 1 else "checkin"):
                    slot += 1
                key = "checkin" if slot == 1 else f"checkin_{slot}"
                day_rec[key] = new_dt
            elif action == "checkout":
                # 找到对应的 checkin slot
                slot = 1
                while day_rec.get(f"checkin_{slot}" if slot > 1 else "checkin"):
                    slot += 1
                # 如果找到 checkin 记录，使用对应 slot
                if slot > 1:
                    key = "checkout" if slot-1 == 1 else f"checkout_{slot-1}"
                else:
                    key = "checkout"
                day_rec[key] = new_dt
        elif target_uid in FINDING_USERS:
            # FINDING: 根据时间判断早班/晚班
            t = new_dt.time()
            if time(7, 0) <= t <= time(12, 0):
                # 早班
                if action == "checkin":
                    day_rec["morning_checkin"] = new_dt
                elif action == "checkout":
                    day_rec["morning_checkout"] = new_dt
            else:
                # 晚班
                if action == "checkin":
                    day_rec["night_checkin"] = new_dt
                elif action == "checkout":
                    day_rec["night_checkout"] = new_dt
        else:
            # CHATTING/PROMO: 夜班
            if action == "checkin":
                day_rec["night_checkin"] = new_dt
            elif action == "checkout":
                day_rec["night_checkout"] = new_dt
        
        save_attendance()
        bot.reply_to(message, f"✅ 已修改 {target_uid} 的考勤记录\n日期: {date_str}\n操作: {action}\n时间: {time_str}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ 修改失败: {str(e)}")

# ===== 管理员命令：查看员工考勤 =====
@bot.message_handler(commands=["view_attendance"])
def view_attendance(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        bot.reply_to(message, "❌ 仅管理员可操作")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "用法: /view_attendance <用户ID>")
        return
    
    try:
        target_uid = int(args[1])
        if target_uid not in ATTENDANCE:
            bot.reply_to(message, f"用户 {target_uid} 无考勤记录")
            return
        
        response = f"📊 用户 {target_uid} 考勤记录:\n\n"
        for month, days in ATTENDANCE[target_uid].items():
            for day, rec in days.items():
                response += f"📅 {month}-{day[-2:]}:\n"
                
                # HR 记录
                if target_uid in HR_USERS:
                    slot = 1
                    while True:
                        ck_key = "checkin" if slot == 1 else f"checkin_{slot}"
                        co_key = "checkout" if slot == 1 else f"checkout_{slot}"
                        ck = rec.get(ck_key)
                        co = rec.get(co_key)
                        if not ck and not co:
                            break
                        if ck:
                            response += f"  {ck_key}: {ck.strftime('%H:%M:%S')}\n"
                        if co:
                            response += f"  {co_key}: {co.strftime('%H:%M:%S')}\n"
                        slot += 1
                
                # FINDING 记录
                if target_uid in FINDING_USERS:
                    if rec.get("morning_checkin"):
                        response += f"  早班上班: {rec['morning_checkin'].strftime('%H:%M:%S')}\n"
                    if rec.get("morning_checkout"):
                        response += f"  早班下班: {rec['morning_checkout'].strftime('%H:%M:%S')}\n"
                    if rec.get("night_checkin"):
                        response += f"  晚班上班: {rec['night_checkin'].strftime('%H:%M:%S')}\n"
                    if rec.get("night_checkout"):
                        response += f"  晚班下班: {rec['night_checkout'].strftime('%H:%M:%S')}\n"
                
                # CHATTING 记录
                if target_uid not in HR_USERS and target_uid not in FINDING_USERS:
                    if rec.get("night_checkin"):
                        response += f"  夜班上班: {rec['night_checkin'].strftime('%H:%M:%S')}\n"
                    if rec.get("night_checkout"):
                        response += f"  夜班下班: {rec['night_checkout'].strftime('%H:%M:%S')}\n"
                
                response += "\n"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"❌ 查看失败: {str(e)}")

# ===== Return (回座) =====
def back(message):
    uid = message.from_user.id
    name = message.from_user.first_name
    
    if uid not in user_activity:
        safe_pm(uid, "❌ 您当前没有进行中的 activity。")
        return

    act_data = user_activity.pop(uid)
    start_dt = act_data["start_dt"]
    end_dt = now()
    
    diff = end_dt - start_dt
    minutes = int(diff.total_seconds() // 60)
    seconds = int(diff.total_seconds() % 60)
    duration_str = f"{minutes}:{seconds:02d}"
    
    timeout_flag = minutes >= ACTIVITY_TIMES.get(act_data["act"], 0)
    warning = " ⚠️" if timeout_flag else ""
    s = user_sessions.get(uid, {})

    msg = (
        f"👤 {name}\n"
        f"🍽 {s.get('Eating',0)} / {MAX_TIMES['Eating']}  "
        f"💧 {s.get('ToiletSmall',0)} / {MAX_TIMES['ToiletSmall']}  "
        f"🚽 {s.get('ToiletLarge',0)} / {MAX_TIMES['ToiletLarge']}  "
        f"🚬 Smoking: {s.get('Smoking',0)} / {MAX_TIMES['Smoking']}  "
        f"📝 {s.get('Other',0)} / {MAX_TIMES['Other']}\n\n"
        f"↩️ Returned\n"
        f"{act_data['act']}\n"
        f"Start: {start_dt.strftime('%H:%M:%S')}\n"
        f"End: {end_dt.strftime('%H:%M:%S')}\n"
        f"Duration: {duration_str}{warning}"
    )

    send_group(msg)
    safe_pm(uid, f"✅ 已回座，耗时 {duration_str}", reply_markup=main_keyboard())

def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        safe_pm(uid, "❌ 您尚未上班打卡，无需下班。")
        return

    checkin_info = CHECK_IN_STATUS.pop(uid)
    in_time = checkin_info["time"]
    shift_info = checkin_info["shift"]
    checkin_logical_date = checkin_info["logical_date"]
    out_time = now()

    # 根据 checkout 时间重新判定归属日期
    attribution_date = get_attribution_date(checkin_logical_date, out_time, uid, shift_info)

    # 1. 动态计算班次结束时间（仍用 checkin 的 logical_date）
    shift_end_dt = datetime.combine(checkin_logical_date, shift_info["end"], tzinfo=LOCAL_TZ)
    if shift_info.get("cross_day"):
        shift_end_dt += timedelta(days=1)
    
    # 2. 计算时长
    diff = out_time - in_time
    hours = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)
    seconds = int(diff.total_seconds() % 60)
    duration_str = f"{hours} hours {minutes} minutes {seconds} seconds"
    
    status_msg = "✅ Checked out on time"
    
    # 3. 判定早退 (凌晨 00:00 - 02:00 豁免)
    is_night_finish = (shift_info.get("cross_day") and out_time.time() < time(2, 0))
    
    if not is_night_finish and out_time < shift_end_dt:
        early_leave = int((shift_end_dt - out_time).total_seconds() // 60)
        if early_leave > 5: 
            status_msg = f"⚠️ Early Leave: {early_leave} min"
            late_group_out_msg = f"👤 <a href=\"tg://user?id={uid}\">{name}</a>💸+{uid} 提前下班 ⚠️ Early Leave: {early_leave} min"
            send_late_notice(late_group_out_msg, parse_mode="HTML")

    # 4. 写入考勤记录（按 attribution_date 写入）
    month_key = attribution_date.strftime("%Y-%m")
    date_key = attribution_date.strftime("%Y-%m-%d")
    ATTENDANCE[uid].setdefault(month_key, {})
    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    day_rec = ATTENDANCE[uid][month_key][date_key]
    
    if shift_info["role"] in ("FINDING", "PROMO"):
        if shift_info["shift"] == "MORNING":
            day_rec["morning_checkout"] = out_time
        elif shift_info["shift"] == "NIGHT":
            day_rec["night_checkout"] = out_time
    else:
        # HR: 使用对应的 slot
        slot = checkin_info.get("_slot", 1)
        key_checkout = "checkout" if slot == 1 else f"checkout_{slot}"
        day_rec[key_checkout] = out_time
    
    save_attendance()
    
    # 5. 获取月度统计
    month_shifts, total_days = get_attendance_summary(uid)
    
    # 6. 发送通知
    msg = (
        f"👤 {name}💸+{uid}【Nexbit-Safe】\n"
        f"✅ Successfully checked out\n"
        f"📅 Check-in time: {in_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {out_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Working hours: {duration_str}\n"
        f"{status_msg}\n"
        f"📊 Attendance statistics:\n"
        f"🗓️ Worked normally this month: {total_days} days"
    )

    user_sessions.pop(uid, None) 
    send_group(msg)
    safe_pm(uid, f"🏠 下班成功！\n工作时长：{duration_str}", reply_markup=main_keyboard())
def safe_pm(uid, text, reply_markup=None):
    try:
        bot.send_message(uid, text, reply_markup=reply_markup)
    except Exception as e:
        print(f"❌ 无法私聊用户 {uid}: {e}")

# ===== Start Activity (开始活动) =====
def start_activity(uid, name, act):
    if uid not in REGISTERED_USERS:
        REGISTERED_USERS.add(uid)
        save_registered_users()

    user_sessions.setdefault(uid, {"Eating": 0, "ToiletLarge": 0, "ToiletSmall": 0, "Smoking": 0, "Other": 0})
    user_logs.setdefault(uid, [])

    if uid in user_activity:
        safe_pm(uid, "❌ Please finish your current activity first.")
        return

    if uid not in CHECK_IN_STATUS:
        safe_pm(uid, "❌ Please check in first.")
        return

    if user_sessions[uid][act] >= MAX_TIMES[act]:
        safe_pm(uid, f"❌ {ACTIVITY_LABELS[act]} limit reached.")
        return

    start_dt = now()
    user_sessions[uid][act] += 1

    user_activity[uid] = {
        "act": act,
        "start_dt": start_dt
    }
    activity_timeout[uid] = False

    display_name = f"{uid}+{name} 【Nexbit-Safe】"
    activity_name = ACTIVITY_LABELS[act]

    send_group(
        f"👤 {display_name}\n"
        f"📅 Time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"✅ Activity: {activity_name}\n"
        f"⚠️ This is your {ordinal(user_sessions[uid][act])} {activity_name}, "
        f"remaining {MAX_TIMES[act]-user_sessions[uid][act]} times this shift\n\n"
        f"👇 Please click [Return] after finishing the activity"
    )

    safe_pm(uid, f"✅ {activity_name} started")

    # ===== 独立闭包内部定时器 =====
    def countdown():
        if uid not in user_activity or user_activity[uid]["start_dt"] != start_dt:
            return
        # 🟢【离座超时】两群同步发送 HTML @通知
        timeout_msg = f"⏰ <a href=\"tg://user?id={uid}\">{name}</a>💸+{uid} 【Nexbit-Safe】 {activity_name} TIMEOUT ⚠️"
        send_group(timeout_msg, parse_mode="HTML")
        send_late_notice(timeout_msg, parse_mode="HTML")

    threading.Timer(ACTIVITY_TIMES[act] * 60, countdown).start()

# ===== Check In (上班) =====
def check_in(uid, name):
    now_dt = now()

    if uid in CHECK_IN_STATUS:
        safe_pm(uid, "❌ You are already checked in.")
        return

    shift_info = get_shift_standard(now_dt, uid)
    if not shift_info:
        safe_pm(uid, "⛔ 当前不在你的上班班次时间内")
        return

    if shift_info["role"] in ("FINDING", "PROMO", "CUSTOM"):
        night_start = time(19, 0)
        if shift_info["role"] == "CUSTOM":
            night_start = time(20, 30)
        if time(12, 0) <= now_dt.time() < night_start:
            shift_info = {
                "role": shift_info["role"],
                "shift": "NIGHT",
                "start": night_start,
                "end": time(10, 30) if shift_info["role"] == "CUSTOM" else time(2, 0),
                "cross_day": True
            }

    logical_date = now_dt.date()
    if (shift_info["role"] in ("FINDING", "PROMO", "CUSTOM")
        and shift_info.get("shift") == "NIGHT"
        and now_dt.time() < time(3, 0)):
        logical_date -= timedelta(days=1)

    shift_start_dt = datetime.combine(logical_date, shift_info["start"], tzinfo=LOCAL_TZ)
    
    late_minutes = 0
    if now_dt > shift_start_dt:
        late_minutes = int((now_dt - shift_start_dt).total_seconds() // 60)

    CHECK_IN_STATUS[uid] = {
        "time": now_dt,
        "logical_date": logical_date,
        "shift": shift_info
    }

    month_key = logical_date.strftime("%Y-%m")
    date_key = logical_date.strftime("%Y-%m-%d")
    ATTENDANCE[uid].setdefault(month_key, {})
    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    day_rec = ATTENDANCE[uid][month_key][date_key]

    if shift_info["role"] in ("FINDING", "PROMO"):
        if shift_info["shift"] == "MORNING":
            day_rec["morning_checkin"] = now_dt
        elif shift_info["shift"] == "NIGHT":
            day_rec["night_checkin"] = now_dt
    else:
        # HR: 找到下一个可用 slot，避免同一天多次打卡互相覆盖
        slot = 1
        while day_rec.get(f"checkin_{slot}" if slot > 1 else "checkin"):
            slot += 1
        key_checkin = "checkin" if slot == 1 else f"checkin_{slot}"
        day_rec[key_checkin] = now_dt
        CHECK_IN_STATUS[uid]["_slot"] = slot

    day_rec["late_minutes"] = max(day_rec.get("late_minutes", 0), late_minutes)

    msg = f"✅ {name} checked in at {now_dt.strftime('%H:%M:%S')}"
    if late_minutes > 0:
        msg += f" ⚠️ Late {late_minutes} min"
    send_group(msg)

    # 🟢【迟到】异常通知群 @提及
    if late_minutes > 0:
        shift_name = f"{shift_info['shift']}".lower() # 获取班次名 (morning / night)
        late_group_msg = f"👤 <a href=\"tg://user?id={uid}\">{name}</a>💸+{uid}{shift_name} ⚠️ late {late_minutes}min"
        send_late_notice(late_group_msg, parse_mode="HTML")

    save_attendance()

    bot_checkin_pm = (
        f"✅ 已上班 {name} checked in at {now_dt.strftime('%H:%M:%S')}\n"
        f"👔 班次：{shift_info['role']} {shift_info['shift']}\n"
        f"⏰ 迟到：{late_minutes} 分钟"
    )
    safe_pm(uid, bot_checkin_pm, reply_markup=main_keyboard())

# ===== Handler =====
@bot.message_handler(func=lambda m: True)
def handler(message):
    if message.from_user.is_bot:
        return

    uid = message.from_user.id
    name = message.from_user.first_name
    txt = message.text

    if "Eat" in txt:
        start_activity(uid, name, "Eating")
    elif "Smoking" in txt:
        start_activity(uid, name, "Smoking")
    elif "Pee" in txt:
        start_activity(uid, name, "ToiletSmall")
    elif "Toilet" in txt:
        start_activity(uid, name, "ToiletLarge")
    elif "Other" in txt:
        start_activity(uid, name, "Other")
    elif "Check In" in txt:
        check_in(uid, name)
    elif "Check Out" in txt:
        check_out(uid, name)
    elif "Return" in txt: 
        back(message)
          
# ===== Run =====
# ===== Persistent storage & patches =====
DATA_FILE = "/data/attendance.json"
REGISTER_FILE = "/data/registered_users.json"
ADMIN_OVERRIDES = {}

# Patch 1: load_attendance — strip & keep admin_overrides
_original_load_attendance = load_attendance
def load_attendance():
    global ADMIN_OVERRIDES
    ADMIN_OVERRIDES = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            overrides_raw = raw.pop("admin_overrides", {})
            for uid_str, months in overrides_raw.items():
                ADMIN_OVERRIDES[int(uid_str)] = months
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
            if ADMIN_OVERRIDES:
                print("✅ Admin overrides loaded:", len(ADMIN_OVERRIDES), "users")
        except Exception as e:
            print("❌ Failed to extract admin_overrides:", e)
    _original_load_attendance()

# Patch 2: save_attendance — re-add admin_overrides after write
_original_save_attendance = save_attendance
def save_attendance():
    _original_save_attendance()
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
        data["admin_overrides"] = {
            str(uid): months for uid, months in ADMIN_OVERRIDES.items()
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("❌ Failed to save admin_overrides:", e)

# Patch 3: get_attendance_summary — auto-calc only, no admin override
_original_get_attendance_summary = get_attendance_summary
def get_attendance_summary(uid):
    return _original_get_attendance_summary(uid)

# Patch 4: check_missing_checkins — skip admins and users not in group
_original_check_missing_checkins = check_missing_checkins
def check_missing_checkins():
    while True:
        try:
            now_dt = now()
            today = now_dt.date()
            for uid in list(REGISTERED_USERS):
                if uid in ADMIN_IDS:
                    continue
                try:
                    member = bot.get_chat_member(GROUP_CHAT_ID, uid)
                    if member.status in ("left", "kicked"):
                        continue
                except Exception:
                    continue

                month_key = today.strftime("%Y-%m")
                date_key = today.strftime("%Y-%m-%d")
                rec = ATTENDANCE.get(uid, {}).get(month_key, {}).get(date_key, {})

                if uid in HR_USERS:
                    limit_dt = datetime.combine(today, time(9, 4), tzinfo=LOCAL_TZ)
                    key = (uid, "HR_DAY", today)
                    if limit_dt <= now_dt < limit_dt + timedelta(seconds=60) and key not in MISSED_CHECK_SENT:
                        if not rec.get("checkin"):
                            send_late_notice_by_id(uid, "HR")
                            MISSED_CHECK_SENT.add(key)
                    continue

                if uid in FINDING_USERS:
                    m_limit = datetime.combine(today, time(7, 4), tzinfo=LOCAL_TZ)
                    key_m = (uid, "FINDING_M", today)
                    if m_limit <= now_dt < m_limit + timedelta(seconds=60) and key_m not in MISSED_CHECK_SENT:
                        if not rec.get("morning_checkin"):
                            send_late_notice_by_id(uid, "FINDING 早班")
                            MISSED_CHECK_SENT.add(key_m)

                    n_limit = datetime.combine(today, time(19, 4), tzinfo=LOCAL_TZ)
                    key_n = (uid, "FINDING_N", today)
                    if n_limit <= now_dt < n_limit + timedelta(seconds=60) and key_n not in MISSED_CHECK_SENT:
                        if not rec.get("night_checkin"):
                            send_late_notice_by_id(uid, "FINDING 晚班")
                            MISSED_CHECK_SENT.add(key_n)
                    continue

                p_limit = datetime.combine(today, time(20, 34), tzinfo=LOCAL_TZ)
                key_p = (uid, "PROMO_NIGHT_NEW", today)
                if p_limit <= now_dt < p_limit + timedelta(seconds=60) and key_p not in MISSED_CHECK_SENT:
                    if not rec.get("checkin") and not rec.get("night_checkin"):
                        send_late_notice_by_id(uid, "推广/夜班(20:30)")
                        MISSED_CHECK_SENT.add(key_p)

        except Exception as e:
            print("❌ missing checkin loop error:", e)

        threading.Event().wait(30)

# Patch 5: /set_month_shifts admin command
@bot.message_handler(commands=["set_month_shifts"])
def set_month_shifts(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        bot.reply_to(message, "❌ 仅管理员可操作")
        return

    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(
            message,
            "用法: /set_month_shifts <用户ID> <年月> <天数>\n"
            "例: /set_month_shifts 6917597442 2024-06 22"
        )
        return

    try:
        target_uid = int(args[1])
        month_key = args[2]
        override_days = int(args[3])

        ADMIN_OVERRIDES.setdefault(target_uid, {})
        ADMIN_OVERRIDES[target_uid][month_key] = override_days

        save_attendance()
        bot.reply_to(
            message,
            f"✅ 已设置用户 {target_uid} 在 {month_key} 的月度工作天数为 {override_days} 天"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ 设置失败: {str(e)}")

# Patch 6: /batch_set_month_shifts — bulk set work days
@bot.message_handler(commands=["batch_set_month_shifts"])
def batch_set_month_shifts(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        bot.reply_to(message, "❌ 仅管理员可操作")
        return

    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(
            message,
            "用法: /batch_set_month_shifts <年月> <天数> <用户ID1> <用户ID2> ...\n"
            "例: /batch_set_month_shifts 2026-06 5 6438074082 8349071207 8338442147"
        )
        return

    try:
        month_key = args[1]
        override_days = int(args[2])
        user_ids = args[3:]

        results = []
        for uid_str in user_ids:
            try:
                target_uid = int(uid_str)
                ADMIN_OVERRIDES.setdefault(target_uid, {})
                ADMIN_OVERRIDES[target_uid][month_key] = override_days
                results.append(f"✅ {target_uid}")
            except Exception:
                results.append(f"❌ {uid_str}")

        save_attendance()
        bot.reply_to(
            message,
            f"批量设置完成 ({month_key}, {override_days}天):\n" + "\n".join(results)
        )
    except Exception as e:
        bot.reply_to(message, f"❌ 批量设置失败: {str(e)}")

print("✅ All patches applied, data path: /data/")

if __name__ == "__main__":
    load_attendance()
    load_registered_users()

    # Reorder handlers: command handlers before catch-all
    try:
        hl = bot.message_handlers
        catch_idx = None
        cmd_handlers = []
        for i, h in enumerate(hl):
            fn = getattr(h.get('function'), '__name__', '')
            cmd = h.get('filters', {}).get('commands') if isinstance(h, dict) else None
            if cmd:
                cmd_handlers.append((i, h, fn))
            if fn == 'handler' and not cmd:
                catch_idx = i

        if catch_idx is not None and cmd_handlers:
            # Pop all command handlers that are after catch-all, then insert before catch-all
            moved = []
            for idx, h, fn in reversed(cmd_handlers):
                if idx > catch_idx:
                    moved.append((fn, hl.pop(idx)))
            moved.reverse()
            new_catch = next(i for i, h in enumerate(hl)
                if getattr(h.get('function'), '__name__', '') == 'handler'
                and not h.get('filters', {}).get('commands'))
            for fn, h in moved:
                hl.insert(new_catch, h)
                new_catch += 1
            moved_names = [n for n, _ in moved]
            print(f"✅ Handler order: {moved_names} before catch-all")
    except Exception as e:
        print("❌ Handler reorder failed:", e)

    threading.Thread(target=check_missing_checkins, daemon=True).start()

    print("🤖 Bot started (JSON persistence at /data/)")

    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )

