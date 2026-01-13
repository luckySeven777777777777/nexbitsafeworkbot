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

                    # ===== ✅【就在这里加】迟到 / 早退 =====
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

# ===== FINDING 用户配置（Telegram user_id）=====
FINDING_USERS = {
    8525517116,   # finding 员工 1
    5545647021,
    5706894394,
    1791318040,
    6683820548, 
    7964956372,
    8437762768, 
    5251501400,
    8547596973,  # finding 员工 2
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


# ===== Attendance Statistics =====
def get_attendance_summary(uid):
    """
    返回：
    本月正常上班天数 X
    累计正常上班天数 Y
    """
    if uid not in ATTENDANCE:
        return 0, 0

    now_dt = now()
    current_month = now_dt.strftime("%Y-%m")

    total_days = set()
    month_days = set()

    for month, days in ATTENDANCE[uid].items():
        for day, rec in days.items():
            if rec.get("checkin") and rec.get("checkout"):
                total_days.add(day)
                if month == current_month:
                    month_days.add(day)

    return len(month_days), len(total_days)


    s = user_sessions[uid]
    return (
        f"👤 User ID: {uid}\n\n"
        f"🍽 Eat: {s['Eating']} / {MAX_TIMES['Eating']} TIME\n"
        f"💧 Pee: {s['ToiletSmall']} / {MAX_TIMES['ToiletSmall']} TIME\n"
        f"🚽 Toilet: {s['ToiletLarge']} / {MAX_TIMES['ToiletLarge']} TIME\n"
        f"🚬 Smoking: {s['Smoking']} / {MAX_TIMES['Smoking']} TIME\n"
        f"📝 Other: {s['Other']} / {MAX_TIMES['Other']} TIME\n"
    )

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
        if t >= time(19, 0) or t < time(6, 0):
            return {
                "role": "FINDING",
                "shift": "NIGHT",
                "start": time(19, 0),
                "end": time(6, 0),   # 次日 06:00
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

    if t >= time(19, 0) or t < time(6, 0):
        return {
            "role": "PROMO",
            "shift": "NIGHT",
            "start": time(19, 0),
            "end": time(6, 0),
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
    now_dt = now()

    if uid in CHECK_IN_STATUS:
        safe_pm(uid, "❌ You are already checked in.")
        return

    shift_info = get_shift_standard(now_dt, uid)
    if not shift_info:
        safe_pm(uid, "⛔ 当前不在你的上班班次时间内")
        return

    # ===== finding / promo 凌晨算前一天 =====
    logical_date = now_dt.date()
    if shift_info["role"] in ("FINDING", "PROMO") and now_dt.time() < time(6, 0):
        logical_date -= timedelta(days=1)

    # ===== 迟到 =====
    late_minutes = 0
    shift_start_dt = datetime.combine(
        logical_date,
        shift_info["start"],
        tzinfo=LOCAL_TZ
    )

    # ✅ FINDING / PROMO：上班时间之前打卡，不算迟到
    if shift_info["role"] in ("FINDING", "PROMO"):
        if now_dt > shift_start_dt:
            late_minutes = int((now_dt - shift_start_dt).total_seconds() // 60)
    else:
        # 其他岗位维持原规则
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
    ATTENDANCE[uid][month_key][date_key]["checkin"] = now_dt
    ATTENDANCE[uid][month_key][date_key]["late_minutes"] = late_minutes

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

    # ===== 早退 =====
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

    # ===== 其它班次（HR / 早班）=====
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

    # ===== 工时 =====
    diff = end_dt - start_dt
    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    # ===== 写回同一天 =====
    month_key = logical_date.strftime("%Y-%m")
    date_key = logical_date.strftime("%Y-%m-%d")

    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    ATTENDANCE[uid][month_key][date_key]["checkout"] = end_dt
    ATTENDANCE[uid][month_key][date_key]["early_leave_minutes"] = early_leave_minutes

    # ===== 保存 =====
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

    # ===== 私聊给本人（完整版）=====
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

    # ===== 群里（简版）=====
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

    # ===== 清状态（一定要在函数里、最后）=====
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
    load_registered_users()
    print("🤖 Bot started (JSON persistence)")
    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )
