import json
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

