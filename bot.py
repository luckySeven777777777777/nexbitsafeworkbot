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
                data[str(uid)][month][day] = {
                    "checkin": rec.get("checkin").isoformat() if rec.get("checkin") else None,
                    "checkout": rec.get("checkout").isoformat() if rec.get("checkout") else None,

                    "morning_checkin": rec.get("morning_checkin").isoformat() if rec.get("morning_checkin") else None,
                    "morning_checkout": rec.get("morning_checkout").isoformat() if rec.get("morning_checkout") else None,
                    "night_checkin": rec.get("night_checkin").isoformat() if rec.get("night_checkin") else None,
                    "night_checkout": rec.get("night_checkout").isoformat() if rec.get("night_checkout") else None,

                    "late_minutes": rec.get("late_minutes", 0),
                    "early_leave_minutes": rec.get("early_leave_minutes", 0),
                }

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
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None
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
HR_USERS = {6917597442, 7569556703, 5186967624, 8183357784, 7501352060, 6028186424}
FINDING_USERS = {7406648934, 7300796372, 7375446542, 7450025463, 8248857112, 7773005580, 7977677975, 6438074082, 1966382979,8349071207,6987104711}
CUSTOM_NIGHT_USERS = {2055027475, 8337820899, 6863315227, 2018656742, 6635424294, 7794920274, 1625231530, 7961174070, 2094656277, 8101295137}

# ===== Memory =====
user_activity = {}
user_sessions = {}
CHECK_IN_STATUS = {}
user_logs = {}
activity_timeout = {}

# ===== Keyboard =====
def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🏢 Check In", "🏠 Check Out")
    kb.row("🍽 Eat", "🚬 Smoking")
    kb.row("💧 Pee", "🚽 Toilet")
    kb.row("📝 Other", "↩ Return")
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
    month_days = set()

    for month, days in ATTENDANCE[uid].items():
        for day, rec in days.items():
            if uid in HR_USERS:
                if rec.get("checkin") and rec.get("checkout"):
                    full_date = f"{month}-{day[-2:]}"
                    total_days.add(full_date)
                    if month == current_month:
                        month_days.add(full_date)
            else:
                if (rec.get("morning_checkin") and rec.get("morning_checkout") and
                    rec.get("night_checkin") and rec.get("night_checkout")):
                    full_date = f"{month}-{day[-2:]}"
                    total_days.add(full_date)
                    if month == current_month:
                        month_days.add(full_date)
    return len(month_days), len(total_days)

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
    bot.send_message(message.chat.id, panel_msg, reply_markup=main_keyboard())

@bot.message_handler(commands=["attendance"])
def attendance_report(message):
    bot.reply_to(message, "📊 考勤统计功能已关闭")

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
    logical_date = checkin_info["logical_date"]
    out_time = now()
    
    # 1. 动态计算班次结束时间
    shift_end_dt = datetime.combine(logical_date, shift_info["end"], tzinfo=LOCAL_TZ)
    if shift_info.get("cross_day"):
        shift_end_dt += timedelta(days=1)
    
    # 2. 计算时长
    diff = out_time - in_time
    duration_str = f"{int(diff.total_seconds() // 3600)}h {int((diff.seconds % 3600) // 60)}m {diff.seconds % 60}s"
    
    status_msg = "✅ On time"
    
    # 3. 判定早退 (凌晨 00:00 - 02:00 豁免)
    is_night_finish = (shift_info.get("cross_day") and out_time.time() < time(2, 0))
    
    if not is_night_finish and out_time < shift_end_dt:
        early_leave = int((shift_end_dt - out_time).total_seconds() // 60)
        if early_leave > 5: 
            status_msg = f"⚠️ Early Leave: {early_leave} min"
            late_group_out_msg = f"👤 <a href=\"tg://user?id={uid}\">{name}</a>💸+{uid} 提前下班 ⚠️ Early Leave: {early_leave} min"
            send_late_notice(late_group_out_msg, parse_mode="HTML")

    # 4. 发送通知
    msg = (
        f"👤 {name}💸+{uid}【Nexbit-Safe】\n\n"
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {in_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {out_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {duration_str}\n"
        f"{status_msg}"
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
        day_rec["checkin"] = now_dt

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
if __name__ == "__main__":
    load_attendance()
    load_registered_users()

    threading.Thread(
        target=check_missing_checkins,
        daemon=True
    ).start()

    print("🤖 Bot started (JSON persistence)")

    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )
