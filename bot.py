import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
import telebot
from telebot.types import ReplyKeyboardMarkup

# ===== Timezone =====
LOCAL_TZ = ZoneInfo("Asia/Yangon")  # 缅甸
# 如果是中国用：ZoneInfo("Asia/Shanghai")

def now():
    print("USING LOCAL TZ:", LOCAL_TZ)
    return datetime.now(LOCAL_TZ)
# ===== Load env =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

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

# ===== Send group =====
def send_group(msg):
    if GROUP_CHAT_ID:
        bot.send_message(GROUP_CHAT_ID, msg)

# ===== /start =====
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    if uid not in user_sessions:
        user_sessions[uid] = {
            "Eating": 0,
            "ToiletLarge": 0,
            "ToiletSmall": 0,
            "Smoking": 0,
            "Other": 0,
        }
    if uid not in user_logs:
        user_logs[uid] = []

    bot.send_message(
        message.chat.id,
        "✅ Panel activated\n\n" + stats_text(uid),
        reply_markup=main_keyboard()
    )

# ===== Start Activity =====
def start_activity(uid, name, act):
    if uid in user_activity:
        bot.send_message(uid, "❌ Please finish your current activity first.")
        return

    if uid not in CHECK_IN_STATUS:
        bot.send_message(uid, "❌ Please check in first.")
        return

    if user_sessions[uid][act] >= MAX_TIMES[act]:
        bot.send_message(uid, f"❌ {act} limit reached.")
        return

    start_dt = now()
    user_sessions[uid][act] += 1

    user_activity[uid] = {
        "act": act,
        "start_dt": start_dt
    }
    activity_timeout[uid] = False

    bot.send_message(uid, f"✅ {act} started at {start_dt.strftime('%H:%M:%S')}")
    send_group(f"📢 {name} started {act} at {start_dt.strftime('%H:%M:%S')}")

    def countdown():
        if uid not in user_activity:
            return
        elapsed = (now() - start_dt).total_seconds() / 60
        if elapsed >= ACTIVITY_TIMES[act]:
            activity_timeout[uid] = True
            send_group(f"⏰ {name} {act} TIMEOUT ⚠️")
            return
        threading.Timer(60, countdown).start()

    countdown()
# ===== Check In / Out =====
def check_in(uid, name):
    if uid in CHECK_IN_STATUS:
        bot.send_message(uid, "❌ You are already checked in.")
        return

    CHECK_IN_STATUS[uid] = now()
    send_group(f"✅ {name} checked in at {CHECK_IN_STATUS[uid].strftime('%H:%M:%S')}")
def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        bot.send_message(uid, "❌ You must check in first.")
        return

    start = CHECK_IN_STATUS[uid]
    end = now()
    diff = end - start

    total_seconds = int(diff.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    # 👉 这里可以自定义员工显示名
    display_name = f"{name}+{uid}【QQwin-39】"

    send_group(
        f"👤 {display_name}\n"
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {start.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {end.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {hours}h {minutes}m {seconds}s"
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

    bot.send_message(uid, "✅ Returned\n" + stats_text(uid))

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
    print("🤖 Bot started")
    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )

