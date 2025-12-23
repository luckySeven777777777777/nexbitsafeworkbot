import os
import threading
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup

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

# ===== Timeout repeat reminder =====
timeout_reminder_tasks = {}

# ===== ERA Style Logs (NEW) =====
user_logs = {}
activity_timeout = {}

# ===== Keyboard =====
def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🍽 Eat", "📝 Other")
    kb.row("💧 Pee", "🚽 Toilet")
    kb.row("🏢 Check In", "🏠 Check Out")
    kb.row("↩ Return")
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
        f"📝 Other: {s['Other']} / {MAX_TIMES['Other']} TIME\n"
    )

# ===== Send group =====
def send_group(msg):
    if GROUP_CHAT_ID:
        bot.send_message(GROUP_CHAT_ID, msg, parse_mode="HTML")

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

    start_dt = datetime.now()
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

        elapsed = (datetime.now() - start_dt).total_seconds() / 60

        if elapsed >= ACTIVITY_TIMES[act]:
            activity_timeout[uid] = True

            # 防止重复创建 5 分钟提醒
            if uid in timeout_reminder_tasks:
                return

            admin_tag = (
                f"<a href='tg://user?id={ADMIN_ID}'>@ADMIN</a>"
                if ADMIN_ID else "@ADMIN"
            )

            def repeat_reminder():
                if uid not in user_activity:
                    return

                send_group(
                    f"⏰ <b>TIMEOUT</b>\n"
                    f"👤 {name}\n"
                    f"📌 {act}\n"
                    f"{admin_tag}"
                )

                t = threading.Timer(300, repeat_reminder)
                timeout_reminder_tasks[uid] = t
                t.start()

            # 第一次超时立即提醒
            send_group(
                f"⏰ <b>TIMEOUT</b>\n"
                f"👤 {name}\n"
                f"📌 {act}\n"
                f"{admin_tag}"
            )

            t = threading.Timer(300, repeat_reminder)
            timeout_reminder_tasks[uid] = t
            t.start()
            return

        threading.Timer(60, countdown).start()

    countdown()
# ===== Check In / Out =====
def check_in(uid, name):
    if uid in CHECK_IN_STATUS:
        bot.send_message(uid, "❌ You are already checked in.")
        return

    CHECK_IN_STATUS[uid] = datetime.now()
    send_group(f"✅ {name} checked in at {CHECK_IN_STATUS[uid].strftime('%H:%M:%S')}")

def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        bot.send_message(uid, "❌ You must check in first.")
        return

    start = CHECK_IN_STATUS[uid]
    end = datetime.now()
    diff = end - start
    send_group(
        f"🏠 {name} checked out\n"
        f"Work duration: {int(diff.total_seconds()//60):02d}:{int(diff.total_seconds()%60):02d}"
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
    end_dt = datetime.now()

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
        f"📝 {user_sessions[uid]['Other']} / {MAX_TIMES['Other']}\n\n"
        f"↩ Returned\n"
        f"{act}\n"
        f"Start: {log['start']}\n"
        f"End: {log['end']}\n"
        f"Duration: {log['duration']}{' ⚠️' if timeout_flag else ''}"
    )
 # ✅ 停止超时重复提醒（必须在这里）
    if uid in timeout_reminder_tasks:
        timeout_reminder_tasks[uid].cancel()
        del timeout_reminder_tasks[uid]

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

