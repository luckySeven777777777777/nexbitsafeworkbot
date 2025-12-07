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
    "ToiletLarge": 15,  # 修改为15分钟
    "ToiletSmall": 10,
    "Smoking": 15,
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
        try:
            bot.send_message(GROUP_CHAT_ID, msg)
        except:
            pass

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

    bot.send_message(
        message.chat.id,
        "✅ Panel activated\n\n" + stats_text(uid),
        reply_markup=main_keyboard()
    )

# ===== Start Activity =====
def start_activity(uid, name, act):
    if uid not in CHECK_IN_STATUS or not CHECK_IN_STATUS.get(uid, False):
        bot.send_message(uid, "❌ Please check in first before starting activities.")
        return

    if user_sessions[uid][act] >= MAX_TIMES[act]:
        bot.send_message(uid, f"❌ {act} limit reached.")
        return

    start_dt = datetime.now()
    start_time = start_dt.strftime("%H:%M:%S")

    user_sessions[uid][act] += 1
    user_activity[uid] = {
        "active": act,
        "time": ACTIVITY_TIMES[act],
        "start_time": start_time,
        "start_dt": start_dt
    }

    bot.send_message(uid, f"✅ {act} started at {start_time}")
    send_group(f"📢 {name} started {act} at {start_time}")

    def countdown():
        if uid not in user_activity:
            return

        if user_activity[uid]["time"] <= 0:
            send_group(f"⏰ {name}'s {act} timeout")
            return

        user_activity[uid]["time"] -= 1
        threading.Timer(60, countdown).start()

    countdown()

# ===== Check In / Out =====
def check_in(uid, name):
    # Check if already checked in
    if uid in CHECK_IN_STATUS and CHECK_IN_STATUS[uid]:
        bot.send_message(uid, "❌ You are already checked in.")
        return

    now = datetime.now().strftime("%H:%M:%S")
    CHECK_IN_STATUS[uid] = True  # Set check-in status to True
    CHECK_IN_STATUS['start_time'] = datetime.now()  # Record check-in time
    bot.send_message(uid, f"✅ Check-in successful at {now}")
    send_group(f"✅ {name} checked in at {now}")

def check_out(uid, name):
    # Check if user has checked in
    if uid not in CHECK_IN_STATUS or not CHECK_IN_STATUS[uid]:
        bot.send_message(uid, "❌ You must check in first.")
        return

    now = datetime.now().strftime("%H:%M:%S")
    check_in_time = CHECK_IN_STATUS.get('start_time')
    if check_in_time:
        # Calculate time spent from check-in to check-out
        diff = datetime.now() - check_in_time
        total_seconds = int(diff.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        duration = f"{minutes:02d}:{seconds:02d}"
        bot.send_message(uid, f"✅ Check-out successful at {now}\nTotal work duration: {duration}")
        send_group(f"🏠 {name} checked out at {now}\nWork duration: {duration}")
    
    del CHECK_IN_STATUS[uid]  # Remove check-in status
    del CHECK_IN_STATUS['start_time']  # Clear check-in time

# ===== Return =====
@bot.message_handler(func=lambda m: "Return" in m.text)
def back(message):
    uid = message.from_user.id
    name = message.from_user.first_name

    if uid in user_activity:
        act = user_activity[uid]["active"]
        start_t = user_activity[uid]["start_time"]
        start_dt = user_activity[uid]["start_dt"]

        end_dt = datetime.now()
        end_t = end_dt.strftime("%H:%M:%S")

        diff = end_dt - start_dt
        total_seconds = int(diff.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        duration = f"{minutes:02d}:{seconds:02d}"

        del user_activity[uid]

        bot.send_message(
            uid,
            f"✅ Returned\n"
            f"Activity: {act}\n"
            f"Start: {start_t}\n"
            f"End: {end_t}\n"
            f"Duration: {duration}\n\n"
            + stats_text(uid)
        )

        send_group(
            f"↩ {name} returned\n"
            f"{act}\n"
            f"Start: {start_t}\n"
            f"End: {end_t}\n"
            f"Duration: {duration}"
        )

# ===== Button handler =====
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    txt = message.text
    uid = message.from_user.id
    name = message.from_user.first_name

    if "Eat" in txt:
        start_activity(uid, name, "Eating")
        bot.send_message(uid, stats_text(uid))

    elif "Pee" in txt:
        start_activity(uid, name, "ToiletSmall")
        bot.send_message(uid, stats_text(uid))

    elif "Toilet" in txt:
        start_activity(uid, name, "ToiletLarge")
        bot.send_message(uid, stats_text(uid))

    elif "Other" in txt:
        start_activity(uid, name, "Other")
        bot.send_message(uid, stats_text(uid))

    elif "Check In" in txt:
        check_in(uid, name)

    elif "Check Out" in txt:
        check_out(uid, name)

# ===== Admin test =====
@bot.message_handler(commands=["test"])
def test(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        send_group("✅ Group notification test successful")

# ===== Run with long polling =====
if __name__ == "__main__":
    print("✅ Bot running...")
    bot.infinity_polling()  # This will keep the bot running using long polling
