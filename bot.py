import json

DATA_FILE = "attendance.json"
REGISTER_FILE = "registered_users.json"
import os
import threading
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import telebot
from telebot.types import ReplyKeyboardMarkup
from collections import defaultdict


ATTENDANCE = defaultdict(lambda: defaultdict(dict))
# ✅【新增】永久注册用户
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

# 结构：
# ATTENDANCE[uid][YYYY-MM][YYYY-MM-DD] = {
#   "checkin": datetime or None,
#   "checkout": datetime or None
# }

# ===== Timezone =====
LOCAL_TZ = ZoneInfo("Asia/Yangon")  # 缅甸
# 如果是中国用：ZoneInfo("Asia/Shanghai")

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
# ===== HR 用户配置（只填 HR 的 Telegram user_id）=====
HR_USERS = {
    8453417442,
    8285060003,
    7329147658,
    7569556703,
    8005614048,
    1934205054,
    6917597442,
}

# ===== FINDING 用户配置（Telegram user_id）=====
FINDING_USERS = {
    5545647021,
    5251501400,
    6683820548,
    1966382979,
    7406648934,
    7577730904,
    2115532359,
    7300796372,
    7292787852,
    8591427572,
    7375446542,
    5739622987,
    8504004122,
    1727971756,
    7620438477,
    5641863981,
    5169844690,
    6936108983, 
    7414850129, 
    5641863981, # finding 员工 2
}
SHIFT_RULES = {
    "HR": {
        "start": time(9, 0),
        "end": time(19, 0),
    },
    "FINDING": {
        "morning": (time(7, 0), time(12, 0)),
        "night": (time(19, 0), time(23, 59, 59)),
    },
    "PROMO": {
        "morning": (time(6, 0), time(12, 0)),
        "night": (time(19, 0), time(23, 59, 59)),
    }
}

# ===== Memory =====
user_activity = {}
user_sessions = {}
CHECK_IN_STATUS = {}



# ===== ERA Style Logs (NEW) =====
user_logs = {}
activity_timeout = {}

# ===== Keyboard =====
def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # 最上面：上下班
    kb.row("🏢 Check In", "🏠 Check Out")

    # 日常操作
    kb.row("🍽 Eat", "🚬 Smoking")
    kb.row("💧 Pee", "🚽 Toilet")

    # 放在一起：Other + Return
    kb.row("📝 Other", "↩ Return")

    return kb


# ===== Stats =====
def stats_text(uid):
    if uid not in user_sessions:
        return "No records"

    s = user_sessions[uid]
    return (
        f"👤 User ID: {uid}\n\n"
        f"🍽 Eat: {s['Eating']} / {MAX_TIMES['Eating']} TIME\n"
        f"💧 Pee: {s['ToiletSmall']} / {MAX_TIMES['ToiletSmall']} TIME\n"
        f"🚽 Toilet: {s['ToiletLarge']} / {MAX_TIMES['ToiletLarge']} TIME\n"
        f"🚬 Smoking: {s['Smoking']} / {MAX_TIMES['Smoking']} TIME\n"
        f"📝 Other: {s['Other']} / {MAX_TIMES['Other']} TIME\n"
    )


# ===== Attendance Statistics (修正版) =====
def get_attendance_summary(uid):
    if uid not in ATTENDANCE:
        return 0, 0

    now_dt = now()
    current_month = now_dt.strftime("%Y-%m")

    total_days = set()
    month_days = set()

    for month, days in ATTENDANCE[uid].items():
        for day, rec in days.items():
            # HR 逻辑
            if uid in HR_USERS:
                if rec.get("checkin") and rec.get("checkout"):
                    full_date = f"{month}-{day[-2:]}"
                    total_days.add(full_date)
                    if month == current_month:
                        month_days.add(full_date)

            # FINDING / PROMO 逻辑
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

    # ===== HR =====
    if uid in HR_USERS:
        return {
            "role": "HR",
            "shift": "DAY",
            "start": time(9, 0),
            "end": time(19, 0),
        }

    # ===== FINDING =====
    if uid in FINDING_USERS:
        # 早班
        if time(7, 0) <= t <= time(12, 0):
            return {
                "role": "FINDING",
                "shift": "MORNING",
                "start": time(7, 0),
                "end": time(12, 0),
            }

        # 晚班（跨天）
        if t >= time(19, 0) or t < time(2, 0):
            return {
                "role": "FINDING",
                "shift": "NIGHT",
                "start": time(19, 0),
                "end": time(2, 0),   # 次日 02:00
                "cross_day": True
            }

        # 提前打卡 → 默认早班
        return {
            "role": "FINDING",
            "shift": "MORNING",
            "start": time(7, 0),
            "end": time(12, 0),
        }

    # ===== PROMO =====
    if time(6, 0) <= t <= time(12, 0):
        return {
            "role": "PROMO",
            "shift": "MORNING",
            "start": time(6, 0),
            "end": time(12, 0),
        }

    if t >= time(19, 0) or t < time(2, 0):
        return {
            "role": "PROMO",
            "shift": "NIGHT",
            "start": time(19, 0),
            "end": time(2, 0),
            "cross_day": True
        }

    # 提前打卡 → 默认早班
    return {
        "role": "PROMO",
        "shift": "MORNING",
        "start": time(6, 0),
        "end": time(12, 0),
    }

# ===== Send group =====
def send_group(msg):
    if not GROUP_CHAT_ID:
        return
    try:
        bot.send_message(GROUP_CHAT_ID, msg)
    except Exception as e:
        print("❌ send_group failed:", e)
# ===== Send late notice =====
def send_late_notice(msg):
    if late_bot and LATE_GROUP_ID:
        try:
            late_bot.send_message(
                LATE_GROUP_ID,
                msg,
                parse_mode="HTML"
            )
        except Exception as e:
            print("❌ send_late_notice failed:", e)

# ===== 未打卡提醒（4分钟检测 - 全自动班次版）=====
MISSED_CHECK_SENT = set()

def check_missing_checkins():
    while True:
        try:
            now_dt = now()
            today = now_dt.date()

            # 所有注册用户
            all_staff = REGISTERED_USERS

            for uid in all_staff:

                month_key = today.strftime("%Y-%m")
                date_key = today.strftime("%Y-%m-%d")

                rec = ATTENDANCE.get(uid, {}).get(month_key, {}).get(date_key, {})

                # =========================
                # HR 检测
                # =========================
                if uid in HR_USERS:
                    shift_start = datetime.combine(today, time(9, 0), tzinfo=LOCAL_TZ)
                    limit_dt = shift_start + timedelta(minutes=4)
                    key = (uid, "HR_DAY", today)
                    window_end = limit_dt + timedelta(seconds=60)

                    if limit_dt <= now_dt < window_end and key not in MISSED_CHECK_SENT:
                        if not rec.get("checkin"):
                            try:
                                chat = bot.get_chat(uid)
                                name = chat.first_name or "User"
                                notice = f"<a href='tg://user?id={uid}'>{name}</a> HR 未打卡 ⚠️"
                                send_late_notice(notice)
                                MISSED_CHECK_SENT.add(key)
                            except Exception as e:
                                print("HR missing error:", e)
                    continue  # HR 检查完跳过后续

                # =========================
                # FINDING 检测
                # =========================
                if uid in FINDING_USERS:
                    # 早班
                    morning_start = datetime.combine(today, time(7, 0), tzinfo=LOCAL_TZ)
                    morning_limit = morning_start + timedelta(minutes=4)
                    key_m = (uid, "FINDING_MORNING", today)
                    if morning_limit <= now_dt < morning_limit + timedelta(seconds=60) and key_m not in MISSED_CHECK_SENT:
                        if not rec.get("morning_checkin"):
                            try:
                                chat = bot.get_chat(uid)
                                name = chat.first_name or "User"
                                notice = f"<a href='tg://user?id={uid}'>{name}</a> FINDING 早班未打卡 ⚠️"
                                send_late_notice(notice)
                                MISSED_CHECK_SENT.add(key_m)
                            except Exception as e:
                                print("FINDING morning error:", e)

                    # 晚班
                    night_start = datetime.combine(today, time(19, 0), tzinfo=LOCAL_TZ)
                    night_limit = night_start + timedelta(minutes=4)
                    key_n = (uid, "FINDING_NIGHT", today)
                    if night_limit <= now_dt < night_limit + timedelta(seconds=60) and key_n not in MISSED_CHECK_SENT:
                        if not rec.get("night_checkin"):
                            try:
                                chat = bot.get_chat(uid)
                                name = chat.first_name or "User"
                                notice = f"<a href='tg://user?id={uid}'>{name}</a> FINDING 晚班未打卡 ⚠️"
                                send_late_notice(notice)
                                MISSED_CHECK_SENT.add(key_n)
                            except Exception as e:
                                print("FINDING night error:", e)
                    continue  # FINDING 检查完跳过后续

                # =========================
                # PROMO 检测（默认：非 HR / FINDING 用户）
                # =========================
                # 早班 06:00
                promo_m_start = datetime.combine(today, time(6, 0), tzinfo=LOCAL_TZ)
                promo_m_limit = promo_m_start + timedelta(minutes=4)
                key_pm = (uid, "PROMO_MORNING", today)
                if promo_m_limit <= now_dt < promo_m_limit + timedelta(seconds=60) and key_pm not in MISSED_CHECK_SENT:
                    if not rec.get("morning_checkin"):
                        try:
                            chat = bot.get_chat(uid)
                            name = chat.first_name or "User"
                            notice = f"<a href='tg://user?id={uid}'>{name}</a> PROMO 早班未打卡 ⚠️"
                            send_late_notice(notice)
                            MISSED_CHECK_SENT.add(key_pm)
                        except Exception as e:
                            print("PROMO morning error:", e)

                # 晚班 19:00
                promo_n_start = datetime.combine(today, time(19, 0), tzinfo=LOCAL_TZ)
                promo_n_limit = promo_n_start + timedelta(minutes=4)
                key_pn = (uid, "PROMO_NIGHT", today)
                if promo_n_limit <= now_dt < promo_n_limit + timedelta(seconds=60) and key_pn not in MISSED_CHECK_SENT:
                    if not rec.get("night_checkin"):
                        try:
                            chat = bot.get_chat(uid)
                            name = chat.first_name or "User"
                            notice = f"<a href='tg://user?id={uid}'>{name}</a> PROMO 晚班未打卡 ⚠️"
                            send_late_notice(notice)
                            MISSED_CHECK_SENT.add(key_pn)
                        except Exception as e:
                            print("PROMO night error:", e)

        except Exception as e:
            print("❌ missing checkin loop error:", e)

        threading.Event().wait(30)# ===== Safe Private Message =====
def safe_pm(uid, text, reply_markup=None):
    try:
        chat = bot.get_chat(uid)

        if getattr(chat, "is_bot", False):
            print(f"🚫 Skipping bot user {uid}")
            return False

        bot.send_message(uid, text, reply_markup=reply_markup)
        return True

    except Exception as e:
        error_text = str(e)

        if "403" in error_text or "bot was blocked" in error_text:
            print(f"🚫 User {uid} blocked bot or is invalid.")
            return False

        print(f"⚠️ PM failed for {uid}: {e}")
        return False
# ===== /start =====
@bot.message_handler(commands=["start"])
def start(message):

    # 🚫 如果是机器人，直接忽略
    if message.from_user.is_bot:
        return

    uid = message.from_user.id
    name = message.from_user.first_name

    # ✅ 第一次注册
    if uid not in REGISTERED_USERS:
        REGISTERED_USERS.add(uid)
        save_registered_users()   # ✅ 必须加这个

        user_sessions.setdefault(uid, {
            "Eating": 0,
            "ToiletLarge": 0,
            "ToiletSmall": 0,
            "Smoking": 0,
            "Other": 0,
        })
        user_logs.setdefault(uid, [])

        bot.send_message(
            message.chat.id,
            "✅ Registration successful. No need to click again in the future. /start\n\n"
            + stats_text(uid),
            reply_markup=main_keyboard()
        )
    else:
        # ✅ 已注册，只提示 + 显示上班状态
        status = (
            f"🟢 已上班：{CHECK_IN_STATUS[uid]['time'].strftime('%H:%M:%S')}"
            if uid in CHECK_IN_STATUS else "🔴 未上班"
)


        bot.send_message(
            message.chat.id,
            f"✅ 已注册\n{status}\n\n" + stats_text(uid),
            reply_markup=main_keyboard()
        )

@bot.message_handler(commands=["attendance"])
def attendance_report(message):
    uid = message.from_user.id

    month_days, total_days = get_attendance_summary(uid)

    bot.reply_to(
        message,
        f"📊 考勤统计\n"
        f"🗓️ 本月已正常上班：{month_days} 天\n"
        f"📈 累计正常上班：{total_days} 天"
    )


# ===== Start Activity =====
def start_activity(uid, name, act):
    # ✅ 没点 /start 也能正常用（关键）
    if uid not in REGISTERED_USERS:
        REGISTERED_USERS.add(uid)
        save_registered_users()

    user_sessions.setdefault(uid, {
        "Eating": 0,
        "ToiletLarge": 0,
        "ToiletSmall": 0,
        "Smoking": 0,
        "Other": 0,
    })
    user_logs.setdefault(uid, [])

    # ===== 下面保持你原来的逻辑 =====
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

    # ===== 计算剩余次数 =====
    used = user_sessions[uid][act]
    max_times = MAX_TIMES[act]
    remaining = max_times - used

    display_name = f"{uid}+{name} 【Nexbit-Safe】"
    activity_name = ACTIVITY_LABELS[act]

    # ===== ERA 风格提示 =====
    send_group(
        f"👤 {display_name}\n"
        f"📅 Time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"✅ Activity: {activity_name}\n"
        f"⚠️ This is your {ordinal(user_sessions[uid][act])} {activity_name}, "
        f"remaining {MAX_TIMES[act]-user_sessions[uid][act]} times this shift\n\n"
        f"👇 Please click [Return] after finishing the activity"
    )

    safe_pm(uid, f"✅ {activity_name} started")

    # ===== countdown 定时器 =====
    def countdown():
        if uid not in user_activity:
            return
        activity_timeout[uid] = True
        send_group(f"⏰ {display_name} {activity_name} TIMEOUT ⚠️")

    threading.Timer(ACTIVITY_TIMES[act] * 60, countdown).start()

# ===== Check In / Out =====
def check_in(uid, name):
    now_dt = now()

    if uid in CHECK_IN_STATUS:
        safe_pm(uid, "❌ You are already checked in.")
        return

    shift_info = get_shift_standard(now_dt, uid)
    if not shift_info:
        safe_pm(uid, "⛔ 当前不在你的上班班次时间内")
        return

    # ===== ✅ 夜班提前打卡修复 =====
    if shift_info["role"] in ("FINDING", "PROMO"):
        night_start = time(19, 0)
        if time(12, 0) <= now_dt.time() < night_start:
            shift_info = {
                "role": shift_info["role"],
                "shift": "NIGHT",
                "start": night_start,
                "end": time(2, 0),
                "cross_day": True
            }

    # ===== finding / promo 凌晨算前一天 =====
    logical_date = now_dt.date()
    if shift_info["role"] in ("FINDING", "PROMO") and now_dt.time() < time(2, 0):
        logical_date -= timedelta(days=1)

    # ===== 迟到计算 =====
    late_minutes = 0
    shift_start_dt = datetime.combine(
        logical_date,
        shift_info["start"],
        tzinfo=LOCAL_TZ
    )

    if shift_info["role"] in ("FINDING", "PROMO"):
        if now_dt.time() < shift_info["start"]:
            late_minutes = 0
        elif now_dt > shift_start_dt:
            late_minutes = int((now_dt - shift_start_dt).total_seconds() // 60)
    else:
        if now_dt > shift_start_dt:
            late_minutes = int((now_dt - shift_start_dt).total_seconds() // 60)

    CHECK_IN_STATUS[uid] = {
        "time": now_dt,
        "logical_date": logical_date,
        "shift": shift_info
    }

    month_key = logical_date.strftime("%Y-%m")
    date_key = logical_date.strftime("%Y-%m-%d")

    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    day_rec = ATTENDANCE[uid][month_key][date_key]

    # ===== FINDING / PROMO：区分早班 / 晚班 =====
    if shift_info["role"] in ("FINDING", "PROMO"):
        if shift_info["shift"] == "MORNING":
            day_rec["morning_checkin"] = now_dt
        elif shift_info["shift"] == "NIGHT":
            day_rec["night_checkin"] = now_dt
    else:
        # ===== HR =====
        day_rec["checkin"] = now_dt

    # ✅【关键修复】迟到只增不减（⚠️ 必须在 if/else 外）
    old_late = day_rec.get("late_minutes", 0)
    day_rec["late_minutes"] = max(old_late, late_minutes)

    # ===== 🚨 迟到 ≥5 分钟 → 发送到通知群 =====
    if late_minutes >= 5:
        day = logical_date.day

        # HR 不管白天晚上，固定 day
        if shift_info["role"] == "HR":
            period = "day"
        else:
            period = "morning" if shift_info["shift"] == "MORNING" else "night"

        # 自动艾特（用 tg://user?id=UID）
        notice = f"<a href='tg://user?id={uid}'>{name}</a> {day}day {period} ⚠️ late {late_minutes}min"
        send_late_notice(notice)

    save_attendance()

    msg = f"✅ {name} checked in at {now_dt.strftime('%H:%M:%S')}"
    if late_minutes > 0:
        msg += f" ⚠️ Late {late_minutes} min"
    send_group(msg)

    safe_pm(
        uid,
        f"🟢 已上班：{now_dt.strftime('%H:%M:%S')}\n"
        f"👔 班次：{shift_info['role']} {shift_info['shift']}\n"
        f"⏰ 迟到：{late_minutes} 分钟",
        reply_markup=main_keyboard()
    )


def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        safe_pm(uid, "❌ You must check in first.")
        return

    record = CHECK_IN_STATUS[uid]
    start_dt = record["time"]
    logical_date = record["logical_date"]
    shift_info = record["shift"]

    end_dt = now()
 
    # ===== 夜班跨天：凌晨算前一天 =====
    if shift_info["role"] in ("FINDING", "PROMO") and shift_info.get("shift") == "NIGHT":
        if end_dt.time() < time(2, 0):
            logical_date -= timedelta(days=1)

    # ===== 早退计算 =====
    early_leave_minutes = 0

    # ===== 夜班特殊规则（FINDING / PROMO）=====
    if shift_info.get("cross_day") and shift_info["role"] in ("FINDING", "PROMO"):

        # 👉 只在 19:00–23:59 之间下班才算早退
        if time(19, 0) <= end_dt.time() <= time(23, 59, 59):
            shift_end_dt = datetime.combine(
                logical_date,
                time(23, 59, 59),
                tzinfo=LOCAL_TZ
            )
            if end_dt < shift_end_dt:
                early_leave_minutes = int(
                    (shift_end_dt - end_dt).total_seconds() // 60
                )
        else:
            # 00:00–06:00 下班 → 不算早退
            early_leave_minutes = 0

    else:
        if shift_info.get("cross_day"):
            shift_end_dt = datetime.combine(
                logical_date + timedelta(days=1),
                shift_info["end"],
                tzinfo=LOCAL_TZ
            )
        else:
            shift_end_dt = datetime.combine(
                logical_date,
                shift_info["end"],
                tzinfo=LOCAL_TZ
            )

        if end_dt < shift_end_dt:
            early_leave_minutes = int(
                (shift_end_dt - end_dt).total_seconds() // 60
            )

    # ===== 计算工时 =====
    diff = end_dt - start_dt
    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    month_key = logical_date.strftime("%Y-%m")
    date_key = logical_date.strftime("%Y-%m-%d")

    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    day_rec = ATTENDANCE[uid][month_key][date_key]

    # ===== FINDING / PROMO：区分早班 / 晚班 =====
    if shift_info["role"] in ("FINDING", "PROMO"):
        if shift_info["shift"] == "MORNING":
            day_rec["morning_checkout"] = end_dt
        elif shift_info["shift"] == "NIGHT":
            day_rec["night_checkout"] = end_dt
    else:
        # ===== HR =====
        day_rec["checkout"] = end_dt

    day_rec["early_leave_minutes"] = early_leave_minutes

    save_attendance()

    # ===== 统计 =====
    month_days, total_days = get_attendance_summary(uid)
    late_minutes = ATTENDANCE[uid][month_key][date_key].get("late_minutes", 0)

    # ===== 状态文案 =====
    status_line = []
    if late_minutes > 0:
        status_line.append(f"⚠️ Late: {late_minutes} min")
    if early_leave_minutes > 0:
        status_line.append(f"⚠️ Early leave: {early_leave_minutes} min")

    status_text = " / ".join(status_line) if status_line else "✅ On time"

    # ===== 私聊给本人 =====
    msg = (
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {hours}h {minutes}m {seconds}s\n"
        f"{status_text}\n\n"
        f"📊 考勤统计：\n"
        f"🗓️ 本月已正常上班：{month_days} 天\n"
        f"📊 累计正常上班：{total_days} 天"
    )

    safe_pm(uid, msg, reply_markup=main_keyboard())

    # ===== 群里通知 =====
    send_group(
        f"👤 {name}+{uid}【Nexbit-Safe】\n\n"
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {hours}h {minutes}m {seconds}s\n"
        f"{status_text}\n\n"
        f"📊 考勤统计：\n"
        f"🗓️ 本月已正常上班：{month_days} 天\n"
        f"📊 累计正常上班：{total_days} 天"
    )

    # ===== 清除状态 =====
    del CHECK_IN_STATUS[uid]


# ===== Return =====
@bot.message_handler(func=lambda m: m.text and "Return" in m.text)
def back(message):
    uid = message.from_user.id
    name = message.from_user.first_name

    if uid not in user_activity:
        return

    act = user_activity[uid]["act"]
    start_dt = user_activity[uid]["start_dt"]
    end_dt = now()

    duration = end_dt - start_dt
    timeout_flag = activity_timeout.get(uid, False)


    log = {
        "act": act,
        "start": start_dt.strftime("%H:%M:%S"),
        "end": end_dt.strftime("%H:%M:%S"),
        "duration": f"{int(duration.total_seconds()//60):02d}:{int(duration.total_seconds()%60):02d}",
        "timeout": timeout_flag
    }

    user_logs.setdefault(uid, []).append(log)

    safe_pm(uid, "✅ Returned\n" + stats_text(uid))

    send_group(
        f"👤 {name}\n"
        f"🍽 {user_sessions[uid]['Eating']} / {MAX_TIMES['Eating']}  "
        f"💧 {user_sessions[uid]['ToiletSmall']} / {MAX_TIMES['ToiletSmall']}  "
        f"🚽 {user_sessions[uid]['ToiletLarge']} / {MAX_TIMES['ToiletLarge']}  "
        f"🚬 Smoking: {user_sessions[uid]['Smoking']} / {MAX_TIMES['Smoking']} "
        f"📝 {user_sessions[uid]['Other']} / {MAX_TIMES['Other']}\n\n"
        f"↩ Returned\n"
        f"{act}\n"
        f"Start: {log['start']}\n"
        f"End: {log['end']}\n"
        f"Duration: {log['duration']}{' ⚠️' if timeout_flag else ''}"
    )

    del user_activity[uid]
    del activity_timeout[uid]

# ===== Button handler =====
@bot.message_handler(func=lambda m: True)
def handler(message):

    # 🚫 如果是机器人，直接忽略
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


 
# ===== Run =====
if __name__ == "__main__":
    load_attendance()
    load_registered_users()

    # ✅ 启动未打卡检测线程
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



