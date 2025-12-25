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
user_work_seconds = {}   # 实际工作秒（已扣除活动）
# ===== ERA Style Logs (NEW) =====
user_logs = {}
activity_timeout = {}

# ===== Keyboard =====
def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🍽 Eat", "🚬 Smoke")
    kb.row("💧 Pee", "🚽 Toilet")
    kb.row("📝 Other")
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
        f"🚬 Smoke: {s['Smoking']} / {MAX_TIMES['Smoking']} TIME\n"
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

    current = user_sessions[uid][act]
    remain = MAX_TIMES[act] - current

    # 👉 私聊提示 + 下发 Return 键盘
    bot.send_message(
        uid,
        f"👤 {name}\n"
        f"📅 Time：{start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"✅ 活动：{act}\n"
        f"⚠️ 这是您第 {current} 次，本班次剩余 {remain} 次\n"
        f"⏱ 最长 {ACTIVITY_TIMES[act]} 分钟\n\n"
        f"👇 活动完成后请点击【回座】",
        reply_markup=main_keyboard()
    )

    # 👉 群提示
    send_group(f"📢 {name} started {act} at {start_dt.strftime('%H:%M:%S')}")

    # 👉 超时检测
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
    user_work_seconds[uid] = 0

    send_group(f"✅ {name} checked in at {CHECK_IN_STATUS[uid].strftime('%H:%M:%S')}")


def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        bot.send_message(uid, "❌ You must check in first.")
        return

    # ✅ 补最后一段“坐在工位的时间”
    last_gap = (now() - CHECK_IN_STATUS[uid]).total_seconds()
    user_work_seconds[uid] += int(last_gap)

    total_seconds = user_work_seconds.get(uid, 0)

    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60

    send_group(
        f"🏠 {name} checked out\n"
        f"Work duration: {h:02d}:{m:02d}:{s:02d}"
    )

    del CHECK_IN_STATUS[uid]
    del user_work_seconds[uid]
# ===== Return =====
@bot.message_handler(func=lambda m: m.text in ["↩ Return", "回座", "Return"])
def back(message):
    uid = message.from_user.id
    name = message.from_user.first_name

    if uid not in user_activity:
        return

    act = user_activity[uid]["act"]
    start_dt = user_activity[uid]["start_dt"]
    end_dt = now()

    # 1️⃣ 累加“坐在工位的时间”
    work_gap = (start_dt - CHECK_IN_STATUS[uid]).total_seconds()
    user_work_seconds[uid] += int(work_gap)

    # 2️⃣ 更新当前坐席起点
    CHECK_IN_STATUS[uid] = end_dt

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
    elif "Smoke" in txt:
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

