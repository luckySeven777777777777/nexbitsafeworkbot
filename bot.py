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
# ✅【新增】永久注册用户
REGISTERED_USERS = set()

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

                    # ===== 早班/晚班上班时间 =====
                    if rec.get("morning_checkin"):
                        ATTENDANCE[uid][month][day]["morning_checkin"] = datetime.fromisoformat(rec["morning_checkin"])

                    if rec.get("morning_checkout"):
                        ATTENDANCE[uid][month][day]["morning_checkout"] = datetime.fromisoformat(rec["morning_checkout"])

                    if rec.get("night_checkin"):
                        ATTENDANCE[uid][month][day]["night_checkin"] = datetime.fromisoformat(rec["night_checkin"])

                    if rec.get("night_checkout"):
                        ATTENDANCE[uid][month][day]["night_checkout"] = datetime.fromisoformat(rec["night_checkout"])

                    # ===== 迟到 / 早退 =====
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

    "morning_checkin": rec.get("morning_checkin").isoformat() if rec.get("morning_checkin") else None,
    "morning_checkout": rec.get("morning_checkout").isoformat() if rec.get("morning_checkout") else None,
    "night_checkin": rec.get("night_checkin").isoformat() if rec.get("night_checkin") else None,
    "night_checkout": rec.get("night_checkout").isoformat() if rec.get("night_checkout") else None,

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
    return datetime.now(LOCAL_TZ)
# ===== Load env =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID")) if os.getenv("GROUP_CHAT_ID") else None
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None
LATE_BOT_TOKEN = os.getenv("LATE_BOT_TOKEN")
LATE_GROUP_ID = int(os.getenv("LATE_GROUP_ID")) if os.getenv("LATE_GROUP_ID") else None

late_bot = None
if LATE_BOT_TOKEN and LATE_GROUP_ID:
    late_bot = telebot.TeleBot(LATE_BOT_TOKEN)


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
    6917597442,
    7569556703,
    5186967624,
    8183357784,
    7501352060,
    6028186424,
    8750107307,
    6546169167,
    7978604802,
}
# ===== FINDING 用户配置（Telegram user_id）=====
FINDING_USERS = {
    7406648934,
    7300796372,
    7375446542,
    7450025463,
    8248857112,
    7773005580,
    7977677975,
    6438074082,
    6438074082,
    1966382979,# finding 员工 2
}
# ===== CUSTOM NIGHT 用户 =====
CUSTOM_NIGHT_USERS = {
    2055027475,
    8337820899,
    6863315227,
    2018656742,
    6635424294,
    7794920274,
    1625231530,
    7961174070,
    2094656277,
    8101295137,
    8101295137, # 推广员工 ID
}

SHIFT_RULES = {
    "HR": {
        "start": time(9, 0),
        "end": time(19, 0),
    },
    "FINDING": {
        "morning": (time(7, 0), time(12, 0)),
        "night": (time(19, 0), time(2, 0)), # 原有的保持不变
    },
    "PROMO_NIGHT_NEW": { # 统一定义新的夜班时间
        "start": time(20, 30),
        "end": time(9, 30),
    }
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


# ===== Attendance Statistics (修正版) =====
def get_attendance_summary(uid):
    if uid not in ATTENDANCE:
        return 0, 0

    now_dt = now()
    current_month = now_dt.strftime("%Y-%m")

    total_days = set()
    month_days = set()

    for month, days in ATTENDANCE[uid].items():
        for day, rec in days.items():
            # HR 逻辑
            if uid in HR_USERS:
                if rec.get("checkin") and rec.get("checkout"):
                    full_date = f"{month}-{day[-2:]}"
                    total_days.add(full_date)
                    if month == current_month:
                        month_days.add(full_date)

            # FINDING / PROMO 逻辑
            else:
                if (rec.get("morning_checkin") and rec.get("morning_checkout") and
                    rec.get("night_checkin") and rec.get("night_checkout")):
                    full_date = f"{month}-{day[-2:]}"
                    total_days.add(full_date)
                    if month == current_month:
                        month_days.add(full_date)

    return len(month_days), len(total_days)


def get_shift_standard(dt, uid):
    t = dt.time()

    # ===== 1. HR 用户 (09:00 - 19:00) =====
    if uid in HR_USERS:
        return {
            "role": "HR",
            "shift": "DAY",
            "start": time(9, 0),
            "end": time(19, 0),
        }

    # ===== 2. FINDING 用户 (早/晚两班) =====
    if uid in FINDING_USERS:
        if time(7, 0) <= t <= time(12, 0):
            return {"role": "FINDING", "shift": "MORNING", "start": time(7, 0), "end": time(12, 0)}
        if t >= time(19, 0) or t < time(2, 0):
            return {"role": "FINDING", "shift": "NIGHT", "start": time(19, 0), "end": time(2, 0), "cross_day": True}
        # 默认早班
        return {"role": "FINDING", "shift": "MORNING", "start": time(7, 0), "end": time(12, 0)}

    # ===== 3. PROMO & CUSTOM 用户 (统一 20:30 - 09:30) =====
    return {
        "role": "PROMO",
        "shift": "NIGHT",
        "start": time(20, 30),   # 晚上 8:30
        "end": time(9, 30),      # 次日 9:30
        "cross_day": True
    }

# ===== Send group =====
def send_group(msg):
    if not GROUP_CHAT_ID:
        return
    try:
        bot.send_message(GROUP_CHAT_ID, msg)
    except Exception as e:
        print("❌ send_group failed:", e)
# ===== Send late notice =====
def send_late_notice(msg):
    if late_bot and LATE_GROUP_ID:
        try:
            late_bot.send_message(
                LATE_GROUP_ID,
                msg,
                parse_mode="HTML"
            )
        except Exception as e:
            print("❌ send_late_notice failed:", e)
# ===== 未打卡提醒（4分钟检测 - 全自动班次版）=====
MISSED_CHECK_SENT = set()
# ===== 【新增】用于记录已发送警告的用户，防止重复艾特 =====
# 格式: { (uid, date): True }
WARNED_USERS = {}

# ===== 1. 修复：迟到监控（只检测已注册 ID，双群艾特） =====
def check_missing_checkins():
    global WARNED_USERS
    while True:
        try:
            now_dt = now()
            
            # 核心要求：只遍历 REGISTERED_USERS 列表内的 ID
            for uid in list(REGISTERED_USERS):
                # 如果已经打过卡了，跳过
                if uid in CHECK_IN_STATUS:
                    continue
                
                shift = get_shift_standard(now_dt, uid)
                if not shift:
                    continue
                
                # 确定逻辑日期（处理跨天）
                logical_date = now_dt.date()
                if shift.get("cross_day") and now_dt.time() < time(4, 0):
                    logical_date -= timedelta(days=1)
                
                # 如果该用户今天这个班次已经艾特过了，跳过
                if (uid, logical_date) in WARNED_USERS:
                    continue

                shift_start_dt = datetime.combine(logical_date, shift["start"], tzinfo=LOCAL_TZ)
                
                # 【判定】超过上班时间 5 分钟
                if now_dt > (shift_start_dt + timedelta(minutes=5)):
                    # 格式化艾特消息
                    mention_text = (
                        f"⏰ [Nexbit-Safe 迟到预警]\n\n"
                        f"👤 人员：[{uid}](tg://user?id={uid})\n"
                        f"👔 班次：{shift['role']} ({shift['start'].strftime('%H:%M')})\n"
                        f"⚠️ 状态：迟到已超过 5 分钟，尚未打卡！"
                    )
                    
                    # 同步发送到两个群
                    for chat_id in [GROUP_ID, ADMIN_GROUP_ID]:
                        if chat_id:
                            try:
                                bot.send_message(chat_id, mention_text, parse_mode="Markdown")
                            except: pass
                    
                    # 标记已通知
                    WARNED_USERS[(uid, logical_date)] = True
                        
        except Exception as e:
            print(f"Monitor Error: {e}")
        
        time.sleep(30)

# ===== 2. 修复：下班功能（找回详细统计格式） =====
def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        safe_pm(uid, "❌ 您尚未上班打卡。")
        return

    # 提取上班信息并移除状态
    checkin_info = CHECK_IN_STATUS.pop(uid)
    in_time = checkin_info["time"]
    shift_info = checkin_info["shift"]
    out_time = now()
    
    # 计算精确工作时长
    diff = out_time - in_time
    h, rem = divmod(int(diff.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    duration_str = f"{h}h {m}m {s}s"

    # 判定准时/早退
    shift_end_dt = datetime.combine(out_time.date(), shift_info["end"], tzinfo=LOCAL_TZ)
    if shift_info.get("cross_day") and out_time.time() > time(12, 0):
        shift_end_dt += timedelta(days=1)
    
    status_msg = "✅ On time"
    if out_time < shift_end_dt:
        early_min = int((shift_end_dt - out_time).total_seconds() // 60)
        status_msg = f"⚠️ Early Leave: {early_min} min"

    # 组装你要求的详细通知格式
    msg = (
        f"👤 {name}💸+{uid}【Nexbit-Safe】\n\n"
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {in_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {out_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {duration_str}\n"
        f"{status_msg}"
    )

    user_sessions.pop(uid, None) # 重置次数
    send_group(msg)
    safe_pm(uid, f"🏠 下班成功！\n工作时长：{duration_str}", reply_markup=main_keyboard())

# ===== 3. 修改：Return 回座（确保带次数统计和超时 ⚠️） =====
def back(message):
    uid = message.from_user.id
    name = message.from_user.first_name
    if uid not in user_activity:
        safe_pm(uid, "❌ 您当前没有进行中的活动。")
        return

    act_data = user_activity.pop(uid)
    start_dt = act_data["start_dt"]
    end_dt = now()
    
    diff = end_dt - start_dt
    m, s = divmod(int(diff.total_seconds()), 60)
    duration_str = f"{m}:{s:02d}"
    
    # 检查超时
    timeout_limit = ACTIVITY_TIMES.get(act_data["act"], 0)
    warning = " ⚠️" if m >= timeout_limit else ""

    s = user_sessions.get(uid, {})
    msg = (
        f"👤 {name}\n"
        f"🍽 {s.get('Eating',0)} / {MAX_TIMES['Eating']}  "
        f"💧 {s.get('ToiletSmall',0)} / {MAX_TIMES['ToiletSmall']}  "
        f"🚽 {s.get('ToiletLarge',0)} / {MAX_TIMES['ToiletLarge']}  "
        f"🚬 Smoking: {s.get('Smoking',0)} / {MAX_TIMES['Smoking']}  "
        f"📝 {s.get('Other',0)} / {MAX_TIMES['Other']}\n\n"
        f"↩️ Returned\n"
        f"{act_data['act']}\n"
        f"Start: {start_dt.strftime('%H:%M:%S')}\n"
        f"End: {end_dt.strftime('%H:%M:%S')}\n"
        f"Duration: {duration_str}{warning}"
    )
    send_group(msg)
    safe_pm(uid, f"✅ 已回座，耗时 {duration_str}", reply_markup=main_keyboard())
      
# ===== 修复后的 [Check Out] 下班功能 =====
def check_out(uid, name):
    if uid not in CHECK_IN_STATUS:
        safe_pm(uid, "❌ 您尚未上班打卡，无需下班。")
        return

    # 获取上班信息并从状态中移除
    checkin_info = CHECK_IN_STATUS.pop(uid)
    in_time = checkin_info["time"]
    shift_info = checkin_info["shift"]
    out_time = now()
    
    # --- 计算工作时长 ---
    diff = out_time - in_time
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    seconds = diff.seconds % 60
    duration_str = f"{hours}h {minutes}m {seconds}s"

    # --- 判定准时状态 ---
    shift_end_dt = datetime.combine(out_time.date(), shift_info["end"], tzinfo=LOCAL_TZ)
    if shift_info.get("cross_day") and out_time.time() > time(12, 0):
        shift_end_dt += timedelta(days=1)
    
    status_msg = "✅ On time"
    if out_time < shift_end_dt:
        early_leave = int((shift_end_dt - out_time).total_seconds() // 60)
        status_msg = f"⚠️ Early Leave: {early_leave} min"

    # ===== 组装您要求的详细通知格式 =====
    # 格式：👤 名字💸+ID【Nexbit-Safe】
    msg = (
        f"👤 {name}💸+{uid}【Nexbit-Safe】\n\n"
        f"✅ Checked out successfully\n"
        f"📅 Check-in time: {in_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📅 Check-out time: {out_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"⏰ Work duration: {duration_str}\n"
        f"{status_msg}"
    )

    # 重置当日活动次数
    user_sessions.pop(uid, None) 

    # 发送群组和私聊通知
    send_group(msg)
    safe_pm(uid, f"🏠 下班成功！\n工作时长：{duration_str}", reply_markup=main_keyboard())

# ===== 补充缺失的辅助发送函数 =====
def safe_pm(uid, text, reply_markup=None):
    try:
        bot.send_message(uid, text, reply_markup=reply_markup)
    except Exception as e:
        print(f"❌ 无法私聊用户 {uid}: {e}")
@bot.message_handler(commands=["attendance"])
def attendance_report(message):
    uid = message.from_user.id

    month_days, total_days = get_attendance_summary(uid)

    bot.reply_to(
    message,
    "📊 考勤统计功能已关闭"
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

    # ===== ERA 风格提示 =====
    send_group(
        f"👤 {display_name}\n"
        f"📅 Time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"✅ Activity: {activity_name}\n"
        f"⚠️ This is your {ordinal(user_sessions[uid][act])} {activity_name}, "
        f"remaining {MAX_TIMES[act]-user_sessions[uid][act]} times this shift\n\n"
        f"👇 Please click [Return] after finishing the activity"
    )

    safe_pm(uid, f"✅ {activity_name} started")

    # ===== countdown 定时器 =====
# 在 start_activity 函数内部：
    def countdown():
        if uid not in user_activity or user_activity[uid]["start_dt"] != start_dt:
            return
        # 按照要求格式提示：⏰ ID+名字 【项目名】 动作 TIMEOUT ⚠️
        send_group(f"⏰ {uid}+{name} 【Nexbit-Safe】 {activity_name} TIMEOUT ⚠️")

    threading.Timer(ACTIVITY_TIMES[act] * 60, countdown).start()

# ===== 修复后的 Check In 函数 =====
def check_in(uid, name):
    now_dt = now()

    if uid in CHECK_IN_STATUS:
        safe_pm(uid, "❌ You are already checked in.")
        return

    shift_info = get_shift_standard(now_dt, uid)
    if not shift_info:
        safe_pm(uid, "⛔ 当前不在你的上班班次时间内")
        return

    # ===== 班次逻辑处理 (保持不变) =====
    if shift_info["role"] in ("FINDING", "PROMO", "CUSTOM"):
        night_start = time(19, 0)
        if shift_info["role"] == "CUSTOM":
            night_start = time(20, 30)
        if time(12, 0) <= now_dt.time() < night_start:
            shift_info = {
                "role": shift_info["role"],
                "shift": "NIGHT",
                "start": night_start,
                "end": time(10, 30) if shift_info["role"] == "CUSTOM" else time(2, 0),
                "cross_day": True
            }

    logical_date = now_dt.date()
    if (shift_info["role"] in ("FINDING", "PROMO", "CUSTOM")
        and shift_info.get("shift") == "NIGHT"
        and now_dt.time() < time(3, 0)):
        logical_date -= timedelta(days=1)

    shift_start_dt = datetime.combine(logical_date, shift_info["start"], tzinfo=LOCAL_TZ)
    
    # 计算迟到
    late_minutes = 0
    if now_dt > shift_start_dt:
        late_minutes = int((now_dt - shift_start_dt).total_seconds() // 60)

    # ===== 记录状态 =====
    CHECK_IN_STATUS[uid] = {
        "time": now_dt,
        "logical_date": logical_date,
        "shift": shift_info
    }

    # 准备考勤数据
    month_key = logical_date.strftime("%Y-%m")
    date_key = logical_date.strftime("%Y-%m-%d")
    ATTENDANCE[uid].setdefault(month_key, {})
    ATTENDANCE[uid][month_key].setdefault(date_key, {})
    day_rec = ATTENDANCE[uid][month_key][date_key]

    if shift_info["role"] in ("FINDING", "PROMO"):
        if shift_info["shift"] == "MORNING":
            day_rec["morning_checkin"] = now_dt
        elif shift_info["shift"] == "NIGHT":
            day_rec["night_checkin"] = now_dt
    else:
        day_rec["checkin"] = now_dt

    day_rec["late_minutes"] = max(day_rec.get("late_minutes", 0), late_minutes)

    # ===== 发送群通知 (修复格式) =====
    # 按照要求显示：✅ {name} checked in at {time}
    msg = f"✅ {name} checked in at {now_dt.strftime('%H:%M:%S')}"
    if late_minutes > 0:
        msg += f" ⚠️ Late {late_minutes} min"
    send_group(msg)

    # 保存数据
    save_attendance()

    # 私聊确认
    safe_pm(
        uid,
        f"🟢 已上班：{now_dt.strftime('%H:%M:%S')}\n"
        f"👔 班次：{shift_info['role']} {shift_info['shift']}\n"
        f"⏰ 迟到：{late_minutes} 分钟",
        reply_markup=main_keyboard()
    )

# ===== 修复后的 Handler (确保 Return 正常触发) =====
@bot.message_handler(func=lambda m: True)
def handler(message):
    if message.from_user.is_bot:
        return

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
    elif "Return" in txt: # 👈 确保这里能捕获到 Return 按钮
        back(message)
          
# ===== Run =====
if __name__ == "__main__":
    load_attendance()
    load_registered_users()

    # ✅ 启动未打卡检测线程
    threading.Thread(
        target=check_missing_checkins,
        daemon=True
    ).start()

    print("🤖 Bot started (JSON persistence)")

    bot.infinity_polling(
        skip_pending=True,
        timeout=20,
        long_polling_timeout=20
    )


