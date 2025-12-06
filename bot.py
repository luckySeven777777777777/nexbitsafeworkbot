import os
import time
import threading
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# ===== 读取环境变量 =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN 环境变量未设置")

bot = telebot.TeleBot(BOT_TOKEN)

# ===== 内存存储 =====
user_activity = {}

ACTIVITY_TIMES = {
    "Eating": 30,
    "ToiletLarge": 10,
    "ToiletSmall": 10,
    "Smoking": 15,
    "Other": 15,
}

MAX_TIMES = {
    "Eating": 3,
    "ToiletLarge": 4,
    "ToiletSmall": 4,
    "Smoking": 4,
    "Other": 2,
}

WORK_START = "18:30"
WORK_END = "06:30"

CHECK_IN_STATUS = {}

# ===== UI 面板 =====
@bot.message_handler(commands=["start"])
def start(message):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("🍲 Eating Time", callback_data="Eating"),
        InlineKeyboardButton("🚾 Toilet (Large)", callback_data="ToiletLarge")
    )
    kb.row(
        InlineKeyboardButton("🚾 Toilet (Small)", callback_data="ToiletSmall"),
        InlineKeyboardButton("🚭 Smoking", callback_data="Smoking")
    )
    kb.row(InlineKeyboardButton("🌐 Other", callback_data="Other"))
    kb.row(
        InlineKeyboardButton("💻 Check-In", callback_data="CheckIn"),
        InlineKeyboardButton("🛏 Check-Out", callback_data="CheckOut")
    )
    bot.send_message(message.chat.id, "✅ Choose your activity:", reply_markup=kb)

# ===== 回调按钮 =====
@bot.callback_query_handler(func=lambda call: True)
def handle(call):
    user_id = call.from_user.id
    username = call.from_user.first_name
    data = call.data

    if data in ACTIVITY_TIMES:
        start_activity(user_id, username, data)
    elif data == "CheckIn":
        check_in(user_id, username)
    elif data == "CheckOut":
        check_out(user_id, username)

# ===== 活动逻辑 + 群通知 =====
def send_group(msg):
    if GROUP_CHAT_ID:
        try:
            bot.send_message(GROUP_CHAT_ID, msg)
        except:
            pass

def start_activity(user_id, username, activity):
    if user_id not in user_activity:
        user_activity[user_id] = {"count": {}, "active": None, "time": 0}

    count = user_activity[user_id]["count"].get(activity, 0)

    if count >= MAX_TIMES[activity]:
        bot.send_message(user_id, f"❌ {activity} limit reached")
        return

    user_activity[user_id]["count"][activity] = count + 1
    user_activity[user_id]["active"] = activity
    user_activity[user_id]["time"] = ACTIVITY_TIMES[activity]

    bot.send_message(user_id, f"⏳ {activity} started: {ACTIVITY_TIMES[activity]} minutes")
    send_group(f"📢 {username} started {activity}")

    def countdown():
        if user_activity[user_id]["active"] != activity:
            return

        if user_activity[user_id]["time"] <= 0:
            bot.send_message(user_id, f"⏰ {activity} time is over!")
            send_group(f"⏰ {username} {activity} timer ended")
            return

        user_activity[user_id]["time"] -= 1
        threading.Timer(60, countdown).start()

    countdown()

# ===== 打卡逻辑 + 群通知 =====
def check_in(user_id, username):
    now = datetime.now().strftime("%H:%M")

    if now >= WORK_START or now <= WORK_END:
        if user_id in CHECK_IN_STATUS:
            bot.send_message(user_id, "❌ Already checked in")
        else:
            CHECK_IN_STATUS[user_id] = True
            bot.send_message(user_id, "✅ Check-in success")
            send_group(f"✅ {username} checked in")
    else:
        bot.send_message(user_id, "❌ Only allowed between 18:30 - 06:30")

def check_out(user_id, username):
    if user_id in CHECK_IN_STATUS:
        del CHECK_IN_STATUS[user_id]
        bot.send_message(user_id, "✅ Check-out success")
        send_group(f"🛏 {username} checked out")
    else:
        bot.send_message(user_id, "❌ Not checked in")

# ===== 停止活动 =====
@bot.message_handler(commands=["back_to_seat"])
def back(message):
    user_id = message.from_user.id
    username = message.from_user.first_name

    if user_id in user_activity:
        act = user_activity[user_id]["active"]
        user_activity[user_id]["active"] = None
        bot.send_message(user_id, "✅ Activity stopped")
        send_group(f"↩️ {username} stopped {act}")
    else:
        bot.send_message(user_id, "❌ No activity running")

# ===== 管理员测试命令 =====
@bot.message_handler(commands=["test"])
def test(message):
    if str(message.from_user.id) == str(ADMIN_ID):
        send_group("✅ 群通知测试成功")

# ===== 启动 =====
if __name__ == "__main__":
    print("✅ Bot running...")
    bot.infinity_polling()
