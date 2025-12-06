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
    "ToiletLarge": 10,
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

WORK_START = "18:30"
WORK_END = "06:30"

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

# ===== Stats Panel =====
def stats_text(uid):
    if uid not in user_sessions:
        return "No record yet"

    s = user_sessions[uid]
    return (
        f"👤 User ID: {uid}\n\n"
        f"🍽 Eat: {s['Eating']} / {MAX_TIMES['Eating']}\n"
        f"💧 Pee: {s['ToiletSmall']} / {MAX_TIMES['ToiletSmall']}\n"
        f"🚽 Toilet: {s['ToiletLarge']} / {MAX_TIMES['ToiletLarge']}\n"
        f"📝 Other: {s['Other']} / {MAX_TIMES['Other']}\n"
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
    if uid not in user_sessions:
        user_sessions[uid] = {
            "Eating": 0, "ToiletLarge": 0,
            "ToiletSmall": 0, "Smoking": 0, "Other": 0
        }

    if user_sessions[uid][act] >= MAX_TIMES[act]:
        bot.send_message(uid, f"❌ {act} limit reached")
        return

    user_sessions[uid][act] += 1
    user_activity[uid] = {
        "active": act,
        "time": ACTIVITY_TIMES[act]
    }

    bot.send_message(uid, f"✅ {act} started")
    send_group(f"📢 {name} started {act}")

    def countdown():
        if uid not in user_activity:
            return

        if user_activity[uid]["time"] <= 0:
            send_group(f"⏰ {name}'s {act} timed out")
            return

        user_activity[uid]["time"] -= 1
        threading.Timer(60, countdown).start()

    countdown()

# ===== Check In / Out =====
def check_in(uid, name):
    now = datetime.now().strftime("%H:%M")
    if now >= WORK_START or now <= WORK_END:
        CHECK_IN_STATUS[uid] = True
        bot.send_message(uid, "✅ Check-in successful")
        send_group(f"✅ {name} checked in")
    else:
        bot.send_message(uid, "❌ Not within working time")

def check_out(uid, name):
    if uid in CHECK_IN_STATUS:
        del CHECK_IN_STATUS[uid]
        bot.send_message(uid, "✅ Check-out successful")
        send_group(f"🏠 {name} checked out")
    else:
        bot.send_message(uid, "❌ Please check in first")

# ===== Return =====
@bot.message_handler(func=lambda m: "Return" in m.text)
def back(message):
    uid = message.from_user.id
    name = message.from_user.first_name
    if uid in user_activity:
        act = user_activity[uid]["active"]
        del user_activity[uid]
        bot.send_message(uid, "✅ Returned to seat\n\n" + stats_text(uid))
        send_group(f"↩ {name} returned ({act} ended)")

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

# ===== Start =====
if __name__ == "__main__":
    print("✅ Bot running...")
    bot.infinity_polling()
