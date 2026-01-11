import json

DATA_FILE = "attendance.json"

import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
import telebot
from telebot.types import ReplyKeyboardMarkup
from collections import defaultdict

ATTENDANCE = defaultdict(lambda: defaultdict(dict))
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
                    if rec.get("checkin"):
                        ATTENDANCE[uid][month][day]["checkin"] = datetime.fromisoformat(rec["checkin"])
                    if rec.get("checkout"):
                        ATTENDANCE[uid][month][day]["checkout"] = datetime.fromisoformat(rec["checkout"])

        print("✅ Attendance loaded from JSON")

    except Exception as e:
        print("❌ Failed to load attendance.json:", e)
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
    6725112018,
    6478034136,
}


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
from datetime import time

def get_shift(dt, uid):
    t = dt.time()

    # ===== HR：09:00–19:00 =====
    if uid in HR_USERS:
        if time(9, 0) <= t <= time(19, 0):
            return "HR"
        return None

    # ===== 推广（默认）=====
    if time(6, 0) <= t <= time(12, 0):
        return "PROMO_MORNING"
    if time(19, 0) <= t <= time(23, 59, 59):
        return "PROMO_NIGHT"

    return None



def is_within_same_shift(ci, co, uid):
    if not ci or not co:
        return False

    shift = get_shift(ci, uid)
    if not shift:
        return False

    ci_t = ci.time()
    co_t = co.time()

    if shift == "PROMO_MORNING":
        return time(6, 0) <= ci_t <= time(12, 0) and time(6, 0) <= co_t <= time(12, 0)

    if shift == "HR":
        return time(9, 0) <= ci_t <= time(19, 0) and time(9, 0) <= co_t <= time(19, 0)

    if shift == "PROMO_NIGHT":
        return time(19, 0) <= ci_t <= time(23, 59, 59) and time(19, 0) <= co_t <= time(23, 59, 59)

    return False



def build_month_report(uid, now_dt):
    month_key = now_dt.strftime("%Y-%m")

    worked_this_month = 0
    worked_total = 0

    miss_checkin = []
    miss_checkout = []

    user_records = ATTENDANCE.get(uid, {})

    for month, records in user_records.items():
        for date in sorted(records.keys()):
            rec = records[date]

            ci = rec.get("checkin")
            co = rec.get("checkout")

            # ✅ 正常上下班（同一班次）
            if ci and co and is_within_same_shift(ci, co, uid):
                worked_total += 1
                if month == month_key:
                    worked_this_month += 1
                continue

            # ⚠️ 只有下班（班次内）→ 缺上班
            if co and not ci:
                if month == month_key and get_shift(co, uid):
                    miss_checkin.append(
                        f"- {date} {co.strftime('%Y-%m-%d %H:%M:%S')} 未打卡上班"
                    )
                continue

            # ⚠️ 只有上班（班次内）→ 缺下班
            if ci and not co:
                if month == month_key and get_shift(ci, uid):
                    miss_checkout.append(
                        f"- {date} {ci.strftime('%Y-%m-%d %H:%M:%S')} 未打卡下班"
                    )
                continue

    text = "\n📊 考勤统计：\n"
    text += f"🗓️ 本月已正常上班：{worked_this_month} 天\n"
    text += f"📊 累计正常上班：{worked_total} 天\n"

    if miss_checkin:
        text += "⚠️ 未打卡上班记录：\n" + "\n".join(miss_checkin) + "\n"

    if miss_checkout:
        text += "⚠️ 未打卡下班记录：\n" + "\n".join(miss_checkout) + "\n"

    return text


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
    check_time = CHECK_IN_STATUS[uid].strftime('%H:%M:%S')

    # ✅ 群提示（保持你原来的）
    send_group(f"✅ {name} checked in at {check_time}")
    # ===== ✅【新增】记录上班打卡（唯一位置）=====
    now_dt = CHECK_IN_STATUS[uid]
    month_key = now_dt.strftime("%Y-%m")
    date_key = now_dt.strftime("%Y-%m-%d")

    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    ATTENDANCE[uid][month_key][date_key]["checkin"] = now_dt
    save_attendance()

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

    # 👉 员工显示名（必须在函数内）
    display_name = f"{name}+{uid}【Nexbit-Safe】"

    # ===== 记录下班打卡 =====
    now_dt = end
    month_key = now_dt.strftime("%Y-%m")
    date_key = now_dt.strftime("%Y-%m-%d")

    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    ATTENDANCE[uid][month_key][date_key]["checkout"] = now_dt
    save_attendance()

    # ===== 群消息（完整 & 缩进正确）=====
    send_group(
        f"👤 {display_name}\n"
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {start.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {end.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {hours}h {minutes}m {seconds}s\n"
        + build_month_report(uid, end)
    )

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


 
# ===== Run =====
if __name__ == "__main__":
    load_attendance()
    print("🤖 Bot started (JSON persistence)")
    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )




