import sqlite3

DB_FILE = "/data/attendance.db"


def get_db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            uid INTEGER,
            work_date TEXT,
            role TEXT,
            shift TEXT,
            checkin TEXT,
            checkout TEXT,
            PRIMARY KEY (uid, work_date, shift)
        )
        """)

import os
import threading
import sqlite3
import re

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

import telebot
from telebot.types import ReplyKeyboardMarkup

from collections import defaultdict

ATTENDANCE = defaultdict(lambda: defaultdict(dict))
# （以后这个可以慢慢不用，但现在保留不冲突）

LOCAL_TZ = ZoneInfo("Asia/Yangon")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

# 结构：
# ATTENDANCE[uid][YYYY-MM][YYYY-MM-DD] = {
#   "checkin": datetime or None,
#   "checkout": datetime or None
# }

# ===== Timezone =====
LOCAL_TZ = ZoneInfo("Asia/Yangon")  # 缅甸
# 如果是中国用：ZoneInfo("Asia/Shanghai")

def now():
    print("USING LOCAL TZ:", LOCAL_TZ)
    return datetime.now(LOCAL_TZ)
# ===== Load env =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None


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
# ===== User Role =====
HR_USERS = {6725112018, 6478034136}   # 人事部 UID（你填）
PROMOTION_USERS = set()            # 推广用户（默认）

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

# ===== Memory =====
user_activity = {}
user_sessions = {}
CHECK_IN_STATUS = {}

# ✅【新增】永久注册用户
REGISTERED_USERS = set()

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

from datetime import time, timedelta

# ===== Shift Time Config =====

# HR（人事部：单班）
HR_START = time(9, 0)
HR_END   = time(19, 0)

# Promotion（推广：双班）
NIGHT_START = time(19, 0)
NIGHT_END   = time(23, 59)

MORNING_START = time(6, 0)
MORNING_END   = time(12, 0)


def get_user_role(uid):
    if uid in HR_USERS:
        return "HR"
    if uid in PROMOTION_USERS:
        return "PROMOTION"
    return "PROMOTION"



def get_shift_by_role(uid, dt):
    t = dt.time()
    role = get_user_role(uid)

    # ===== HR：单班 =====
    if role == "HR":
        if HR_START <= t <= HR_END:
            return "full", dt.date()
        return None, None

    # ===== PROMOTION：双班 =====
    # 晚班（当天）
    if NIGHT_START <= t <= NIGHT_END:
        return "night", dt.date()

    # 早班（当天）
    if MORNING_START <= t <= MORNING_END:
        return "morning", dt.date()

    return None, None



# ✅ 一定要在 build_month_report 之前
def calc_total_worked_days(uid):
    total = 0
    role = get_user_role(uid)

    for month_data in ATTENDANCE.get(uid, {}).values():
        for rec in month_data.values():

            if role == "HR":
                full = rec.get("full", {})
                if full.get("checkin") and full.get("checkout"):
                    total += 1
            else:
                night = rec.get("night", {})
                morning = rec.get("morning", {})
                if (
                    night.get("checkin") and night.get("checkout")
                    and
                    morning.get("checkin") and morning.get("checkout")
                ):
                    total += 1

    return total



def build_month_report(uid, now_dt):
    month_key = now_dt.strftime("%Y-%m")
    records = ATTENDANCE.get(uid, {}).get(month_key, {})
    role = get_user_role(uid)

    worked_days = 0

    for rec in records.values():
        if role == "HR":
            full = rec.get("full", {})
            if full.get("checkin") and full.get("checkout"):
                worked_days += 1
        else:
            night = rec.get("night", {})
            morning = rec.get("morning", {})
            if (
                night.get("checkin") and night.get("checkout")
                and
                morning.get("checkin") and morning.get("checkout")
            ):
                worked_days += 1

    return (
        "\n📊 本月统计：\n"
        f"🗓️ 本月已正常上班：{worked_days} 天\n"
        f"📊 累计正常上班：{calc_total_worked_days(uid)} 天\n"
    )


# ===== Send group =====
def send_group(msg):
    if not GROUP_CHAT_ID:
        return
    try:
        bot.send_message(GROUP_CHAT_ID, msg)
    except Exception as e:
        print("❌ send_group failed:", e)

def safe_pm(uid, text, reply_markup=None):
    try:
        bot.send_message(uid, text, reply_markup=reply_markup)
        return True
    except Exception as e:
        print(f"⚠️ PM failed for {uid}: {e}")
        return False

# ===== /start =====
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    name = message.from_user.first_name

    # ✅ 第一次注册
    if uid not in REGISTERED_USERS:
        REGISTERED_USERS.add(uid)

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
            f"🟢 已上班：{CHECK_IN_STATUS[uid].strftime('%H:%M:%S')}"
            if uid in CHECK_IN_STATUS else "🔴 未上班"
        )

        bot.send_message(
            message.chat.id,
            f"✅ 已注册\n{status}\n\n" + stats_text(uid),
            reply_markup=main_keyboard()
        )


# ===== Start Activity =====
def start_activity(uid, name, act):
    # ✅ 没点 /start 也能正常用（关键）
    if uid not in REGISTERED_USERS:
        REGISTERED_USERS.add(uid)

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

    # ===== 发送 ERA 风格群提示 =====
    send_group(
        f"👤 {display_name}\n"
        f"📅 Time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"✅ Activity: {activity_name}\n"
        f"⚠️ This is your {ordinal(used)} {activity_name}, "
        f"remaining {activity_name} times this shift: {remaining}\n\n"
        f"👇 Please click [Return] after finishing the activity"
    )

    safe_pm(uid, f"✅ {activity_name} started")

    def countdown():
        if uid not in user_activity:
            return
        elapsed = (now() - start_dt).total_seconds() / 60
        if elapsed >= ACTIVITY_TIMES[act]:
            activity_timeout[uid] = True
            send_group(f"⏰ {display_name} {activity_name} TIMEOUT ⚠️")
            return
        threading.Timer(60, countdown).start()

    countdown()
# ===== Check In / Out =====
def check_in(uid, name):
    if uid in CHECK_IN_STATUS:
        safe_pm(uid, "❌ You are already checked in.")
        return

    CHECK_IN_STATUS[uid] = now()
    now_dt = CHECK_IN_STATUS[uid]

    shift, work_date = get_shift_by_role(uid, now_dt)
    if not shift:
        safe_pm(uid, "❌ 当前时间不在你的上班时间范围内")
        del CHECK_IN_STATUS[uid]
        return

    month_key = work_date.strftime("%Y-%m")
    date_key = work_date.strftime("%Y-%m-%d")

    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    ATTENDANCE[uid][month_key][date_key].setdefault(shift, {})
    ATTENDANCE[uid][month_key][date_key][shift]["checkin"] = now_dt



    # ✅ 私聊状态更新（关键新增）
    safe_pm(
        uid,
        f"✅ Registered\n"
        f"🟢 Already at work：{check_time}\n\n"
        + stats_text(uid),
        reply_markup=main_keyboard()
    )

def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        safe_pm(uid, "❌ You must check in first.")
        return

    start = CHECK_IN_STATUS[uid]
    end = now()
    diff = end - start

    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    display_name = f"{name}+{uid}【Nexbit-Safe】"

    # ===== 关键：按角色 & 时间判断班次 =====
    shift, work_date = get_shift_by_role(uid, end)
    if not shift:
        safe_pm(uid, "❌ 当前时间不在你的下班时间范围内")
        return

    month_key = work_date.strftime("%Y-%m")
    date_key = work_date.strftime("%Y-%m-%d")

    # ===== 记录下班打卡（内存结构，先不动）=====
    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    ATTENDANCE[uid][month_key][date_key].setdefault(shift, {})
    ATTENDANCE[uid][month_key][date_key][shift]["checkout"] = end

    # ===== 群提示 =====
    send_group(
        f"👤 {display_name}\n"
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {start.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {end.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {hours}h {minutes}m {seconds}s"
        + build_month_report(uid, end)
    )

    # ===== 清除上班状态 =====
    del CHECK_IN_STATUS[uid]


# ===== Return =====
@bot.message_handler(func=lambda m: "Return" in m.text)
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
import re

# ===== 新增：导入群历史打卡 =====
def import_history_from_group(group_id, limit=1000):
    """
    从群消息抓历史打卡记录，导入 ATTENDANCE
    limit: 读取最近多少条消息
    """
    if not group_id:
        print("⚠️ GROUP_CHAT_ID 未设置，无法导入历史记录")
        return

    print(f"⏳ Importing last {limit} messages from group {group_id}...")

    try:
        messages = bot.get_chat_history(group_id, limit=limit)
    except Exception as e:
        print("❌ Failed to get chat history:", e)
        return

    # 名字 -> UID 映射，如果 bot 发送消息没有 UID，可以手动维护
    NAME_TO_UID = {}  # 例如 {"Alice": 123456789, "Bob": 987654321}

    for msg in messages:
        text = msg.text
        if not text:
            continue

        # ==== 上班打卡 ====
        m_checkin = re.match(r"✅ (.+?) checked in at (\d{2}:\d{2}:\d{2})", text)
        if m_checkin:
            name = m_checkin.group(1)
            time_str = m_checkin.group(2)
            uid = name  # 用名字代替 UID

            date = msg.date.astimezone(LOCAL_TZ)
            month_key = date.strftime("%Y-%m")
            date_key = date.strftime("%Y-%m-%d")

            ATTENDANCE[uid][month_key].setdefault(date_key, {})
            ATTENDANCE[uid][month_key][date_key]["checkin"] = datetime(
                date.year, date.month, date.day,
                int(time_str[:2]), int(time_str[3:5]), int(time_str[6:8]),
                tzinfo=LOCAL_TZ
            )
            continue

        # ==== 下班打卡 ====
        if "✅ Checked out successfully" in text:
            m_start = re.search(r"📅 Check-in time: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
            m_end   = re.search(r"📅 Check-out time: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", text)
            if m_start and m_end:
                start_dt = datetime.fromisoformat(m_start.group(1)).replace(tzinfo=LOCAL_TZ)
                end_dt   = datetime.fromisoformat(m_end.group(1)).replace(tzinfo=LOCAL_TZ)
                uid = msg.from_user.id  # 如果 bot 发的消息没有 UID，需要手动 NAME_TO_UID

                month_key = end_dt.strftime("%Y-%m")
                date_key = end_dt.strftime("%Y-%m-%d")

                ATTENDANCE[uid][month_key].setdefault(date_key, {})
                ATTENDANCE[uid][month_key][date_key]["checkin"] = start_dt
                ATTENDANCE[uid][month_key][date_key]["checkout"] = end_dt

    print("✅ History imported from group successfully")


# ===== Run =====
if __name__ == "__main__":
    init_db()   # ⭐⭐⭐ 关键
    print("🤖 Bot started")
    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )



