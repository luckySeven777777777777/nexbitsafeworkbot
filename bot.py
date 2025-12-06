import os
import time
import threading
from datetime import datetime
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = TeleBot(BOT_TOKEN)

# 存储每个用户的活动状态
user_activity = {}

# 定义活动的时间（分钟）
ACTIVITY_TIMES = {
    "Eating": 30,  # 30分钟
    "ToiletLarge": 10,  # 10分钟
    "ToiletSmall": 10,  # 10分钟
    "Smoking": 15,  # 15分钟
    "Other": 15,  # 15分钟
}

# 最大次数
MAX_TIMES = {
    "Eating": 3,
    "ToiletLarge": 4,
    "ToiletSmall": 4,
    "Smoking": 4,
    "Other": 2,
}

# 上班时间段
WORK_START = "18:30"
WORK_END = "06:30"

# Check-In 和 Check-Out 时间标志
CHECK_IN_STATUS = {}
CHECK_OUT_STATUS = {}

# 按钮回调函数
def create_timer_callback(activity, user_id):
    def callback(_):
        start_timer(activity, user_id)
    return callback

# 启动计时器
def start_timer(activity, user_id):
    if user_id in user_activity and user_activity[user_id]['activity'] == activity:
        remaining_time = user_activity[user_id]['remaining_time']
        if remaining_time > 0:
            bot.send_message(user_id, f"🔔 {activity} is ongoing. Remaining time: {remaining_time} minutes.")
        else:
            bot.send_message(user_id, f"❗ {activity} time exceeded. You need to click 'Back to seat' to stop.")
    else:
        # 创建新活动
        user_activity[user_id] = {
            "activity": activity,
            "remaining_time": ACTIVITY_TIMES[activity],
            "count": 0,
            "timer": None
        }
        bot.send_message(user_id, f"⏳ Started {activity}. You have {ACTIVITY_TIMES[activity]} minutes.")

        # 开始倒计时
        def countdown():
            if user_activity[user_id]["remaining_time"] > 0:
                user_activity[user_id]["remaining_time"] -= 1
                bot.send_message(user_id, f"Remaining {activity} time: {user_activity[user_id]['remaining_time']} minutes.")
                threading.Timer(60, countdown).start()
            else:
                bot.send_message(user_id, f"⏰ {activity} time is over! Please click 'Back to seat' to stop the timer.")

        # 启动计时器
        countdown()

# 用户点击活动按钮
@bot.message_handler(commands=["start"])
def send_welcome(message):
    keyboard = InlineKeyboardMarkup()

    keyboard.row(
        InlineKeyboardButton("🍲 Eating Time", callback_data="Eating"),
        InlineKeyboardButton("🚾 Toilet (Large)", callback_data="ToiletLarge"),
    )

    keyboard.row(
        InlineKeyboardButton("🚾 Toilet (Small)", callback_data="ToiletSmall"),
        InlineKeyboardButton("🚭 Smoking", callback_data="Smoking"),
    )

    keyboard.row(
        InlineKeyboardButton("🌐 Other Activities", callback_data="Other"),
    )
    keyboard.row(
        InlineKeyboardButton("💻 Check-In", callback_data="CheckIn"),
        InlineKeyboardButton("🛏 Check-Out", callback_data="CheckOut"),
    )

    bot.send_message(message.chat.id, "Choose your activity:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: True)
def handle_activity(call):
    user_id = call.from_user.id
    activity = call.data

    if activity in ACTIVITY_TIMES:
        if user_id not in user_activity:
            user_activity[user_id] = {"activity": None, "remaining_time": 0, "count": 0}

        # 限制用户选择次数
        if user_activity[user_id]["count"] < MAX_TIMES[activity]:
            user_activity[user_id]["count"] += 1
            create_timer_callback(activity, user_id)(call)
        else:
            bot.send_message(user_id, f"❌ You have already completed {MAX_TIMES[activity]} {activity} sessions.")
    elif activity == "CheckIn":
        check_in(user_id)
    elif activity == "CheckOut":
        check_out(user_id)

# Check-In 逻辑
def check_in(user_id):
    current_time = datetime.now().strftime("%H:%M")
    if current_time >= WORK_START or current_time <= WORK_END:
        if user_id not in CHECK_IN_STATUS:
            CHECK_IN_STATUS[user_id] = "checked in"
            bot.send_message(user_id, "✅ You have successfully checked in!")
        else:
            bot.send_message(user_id, "❌ You have already checked in today.")
    else:
        bot.send_message(user_id, "❌ You can only check in between 6:30 PM and 6:30 AM.")

# Check-Out 逻辑
def check_out(user_id):
    current_time = datetime.now().strftime("%H:%M")
    if current_time >= WORK_START or current_time <= WORK_END:
        if user_id in CHECK_IN_STATUS:
            del CHECK_IN_STATUS[user_id]
            bot.send_message(user_id, "✅ You have successfully checked out!")
        else:
            bot.send_message(user_id, "❌ You need to check in before checking out.")
    else:
        bot.send_message(user_id, "❌ You can only check out between 6:30 PM and 6:30 AM.")

# 用户点击“回座”按钮
@bot.message_handler(commands=["back_to_seat"])
def back_to_seat(message):
    user_id = message.from_user.id
    if user_id in user_activity and user_activity[user_id]["activity"] is not None:
        bot.send_message(user_id, f"✅ {user_activity[user_id]['activity']} stopped. You can start a new activity.")
        user_activity[user_id] = {"activity": None, "remaining_time": 0, "count": user_activity[user_id]["count"]}
    else:
        bot.send_message(user_id, "No active activity to stop.")

# 启动Bot
if __name__ == "__main__":
    bot.polling()
