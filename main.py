import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = "8634019645:AAErehXl6uTTnw2IaoZ31afOkaZhO0xCLa4"
ADMIN_ID = 7601846213

USERS_FILE = "users.json"
RESULTS_FILE = "results.json"

POLL_OPTIONS = [
    ("A", "Bosh Direktor (Ruxsora) da kamchilik bor"),
    ("B", "ROP Sotuv bolimi rahbari (Zuhra) da kamchilik bor"),
    ("C", "Marketing bolimi (Ziyoda) da kamchilik bor"),
    ("D", "Bosh Kurator (Madina) da kamchilik bor"),
]

CHOOSING = 1
WRITING_COMMENT = 2
WRITING_REPEAT_REASON = 3
CHOOSING_NEW = 4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_users():
    data = load_json(USERS_FILE)
    return data.get("users", [])


def save_user(user_id, username, full_name):
    data = load_json(USERS_FILE)
    users = data.get("users", [])
    ids = [u["id"] for u in users]
    if user_id not in ids:
        users.append({
            "id": user_id,
            "username": username or "-",
            "name": full_name or "-",
            "joined": datetime.now().strftime("%d.%m.%Y %H:%M")
        })
        data["users"] = users
        save_json(USERS_FILE, data)


def get_user_info(user_id):
    users_list = load_users()
    info = next((u for u in users_list if u["id"] == user_id), {})
    return info.get("name", "-"), info.get("username", "-")


def build_poll_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data="vote_" + code)]
        for code, text in POLL_OPTIONS
    ])


def build_new_poll_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data="newvote_" + code)]
        for code, text in POLL_OPTIONS
    ])


def build_after_vote_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Izoh qoldirish (ixtiyoriy)", callback_data="add_comment")],
        [InlineKeyboardButton("Qayta ovoz berish", callback_data="request_revote")],
    ])


def build_stats_text():
    results_data = load_json(RESULTS_FILE)
    submitted = {uid: d for uid, d in results_data.items() if d.get("submitted")}
    total = len(submitted)
    if total == 0:
        return "Hali hech kim javob bermadi."
    counts = {code: 0 for code, _ in POLL_OPTIONS}
    for d in submitted.values():
        if d["choice"] in counts:
            counts[d["choice"]] += 1
    text = "Joriy natijalar (" + str(total) + " javob):\n\n"
    for code, option_text in POLL_OPTIONS:
        pct = round(counts[code] / total * 100) if total > 0 else 0
        bar = "=" * counts[code]
        text += option_text + "\n-> " + str(counts[code]) + " kishi (" + str(pct) + "%) " + bar + "\n\n"
    return text


def build_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Statistikani yangilash", callback_data="refresh_stats")],
        [InlineKeyboardButton("Batafsil javoblar", callback_data="detailed_results")],
    ])


def build_approve_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Ruxsat berish", callback_data="approve_" + str(user_id))],
        [InlineKeyboardButton("Rad etish", callback_data="reject_" + str(user_id))],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.full_name)
    results = load_json(RESULTS_FILE)
    user_data = results.get(str(user.id), {})

    if user_data.get("submitted"):
        choice_text = user_data.get("choice_text", "-")
        await update.message.reply_text(
            "Siz allaqachon ovoz berdingiz.\n\nTanlaganingiz:\n" + choice_text,
            reply_markup=build_after_vote_keyboard()
        )
        return WRITING_COMMENT

    await update.message.reply_text(
        "Assalomu alaykum!\n\nBu sorovnoma ANONIM.\n\nQuyidagi rahbarlarning qaysi birining ishida kamchilik bor, birini tanlang:",
        reply_markup=build_poll_keyboard()
    )
    return CHOOSING


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    code = query.data.replace("vote_", "")
    chosen_text = next((t for c, t in POLL_OPTIONS if c == code), "")

    results = load_json(RESULTS_FILE)
    results[str(user.id)] = {
        "choice": code,
        "choice_text": chosen_text,
        "comment": "-",
        "submitted": True,
        "can_revote": False,
        "submitted_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    save_json(RESULTS_FILE, results)

    await query.edit_message_text(
        "Siz tanladingiz:\n" + chosen_text + "\n\nRahmat! Agar javobingizni o'zgartirmoqchi bo'lsangiz pastdagi tugmani bosing.",
        reply_markup=build_after_vote_keyboard()
    )

    name, username = get_user_info(user.id)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="Yangi ovoz!\n\n" + name + " (@" + username + ")\nTanladi: " + chosen_text + "\n\n" + build_stats_text(),
            reply_markup=build_admin_keyboard()
        )
    except Exception as e:
        logger.error(e)

    return WRITING_COMMENT


async def handle_add_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Izohingizni yozing:")
    return WRITING_COMMENT


async def handle_comment_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    comment = update.message.text

    results = load_json(RESULTS_FILE)
    if str(user.id) in results:
        results[str(user.id)]["comment"] = comment
        save_json(RESULTS_FILE, results)

    choice_text = results[str(user.id)].get("choice_text", "-")
    await update.message.reply_text(
        "Izohingiz saqlandi!\n\nTanlaganingiz:\n" + choice_text,
        reply_markup=build_after_vote_keyboard()
    )

    name, username = get_user_info(user.id)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="Izoh qoldirildi!\n\n" + name + " (@" + username + ")\nIzohi: " + comment
        )
    except Exception as e:
        logger.error(e)

    return WRITING_COMMENT


async def handle_request_revote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Agar xohlasangiz, sababini yozing.\nBu ixtiyoriy. \n\nSababingizni yozing yoki /skip tugmasini bosing:"
    )
    return WRITING_REPEAT_REASON


async def handle_repeat_reason_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reason = update.message.text
    if reason == "/skip":
        reason = "Sabab ko'rsatilmadi"
    await update.message.reply_text("Arizangiz yuborildi. Admin javob berguncha kuting.")
    await send_revote_request(context, user, reason)
    return ConversationHandler.END


async def send_revote_request(context, user, reason):
    name, username = get_user_info(user.id)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="Qayta ovoz berish talabi!\n\n" + name + " (@" + username + ")\nSababi: " + reason,
            reply_markup=build_approve_keyboard(user.id)
        )
    except Exception as e:
        logger.error(e)


async def handle_new_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    code = query.data.replace("newvote_", "")
    chosen_text = next((t for c, t in POLL_OPTIONS if c == code), "")

    results = load_json(RESULTS_FILE)
    results[str(user.id)] = {
        "choice": code,
        "choice_text": chosen_text,
        "comment": "-",
        "submitted": True,
        "can_revote": False,
        "submitted_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    save_json(RESULTS_FILE, results)

    await query.edit_message_text(
        "Yangi ovozingiz qabul qilindi!\n\nSiz tanladingiz:\n" + chosen_text + "\n\nRahmat!",
        reply_markup=build_after_vote_keyboard()
    )

    name, username = get_user_info(user.id)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="Ovoz o'zgartirildi!\n\n" + name + " (@" + username + ")\nYangi tanlovi: " + chosen_text + "\n\n" + build_stats_text(),
            reply_markup=build_admin_keyboard()
        )
    except Exception as e:
        logger.error(e)

    return WRITING_COMMENT


async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
    data = query.data

    if data == "refresh_stats":
        try:
            await query.edit_message_text(text=build_stats_text(), reply_markup=build_admin_keyboard())
        except Exception:
            pass

    elif data == "detailed_results":
        results_data = load_json(RESULTS_FILE)
        users_list = load_users()
        submitted = {uid: d for uid, d in results_data.items() if d.get("submitted")}
        if not submitted:
            await query.answer("Hali javoblar yoq.", show_alert=True)
            return
        text = "Batafsil javoblar:\n\n"
        for user_id, d in submitted.items():
            info = next((u for u in users_list if str(u["id"]) == user_id), {})
            text += info.get("name", "-") + " (@" + info.get("username", "-") + ")\n"
            text += "Tanladi: " + d["choice_text"] + "\n"
            text += "Izohi: " + d["comment"] + "\n"
            text += "Vaqt: " + d["submitted_at"] + "\n\n"
        if len(text) > 4000:
            await context.bot.send_message(chat_id=ADMIN_ID, text=text[:4000])
            await context.bot.send_message(chat_id=ADMIN_ID, text=text[4000:])
        else:
            await context.bot.send_message(chat_id=ADMIN_ID, text=text)

    elif data.startswith("approve_"):
        target_id = int(data.replace("approve_", ""))
        results = load_json(RESULTS_FILE)
        if str(target_id) in results:
            results[str(target_id)]["can_revote"] = True
            save_json(RESULTS_FILE, results)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="Admin qayta ovoz berishga ruxsat berdi!\n\nYangi javobingizni tanlang:",
                reply_markup=build_new_poll_keyboard()
            )
            await query.edit_message_text("Ruxsat berildi.")
        except Exception as e:
            logger.error(e)

    elif data.startswith("reject_"):
        target_id = int(data.replace("reject_", ""))
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="Afsuski, admin qayta ovoz berishga ruxsat bermadi."
            )
            await query.edit_message_text("Rad etildi.")
        except Exception as e:
            logger.error(e)


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(build_stats_text(), reply_markup=build_admin_keyboard())


async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = load_users()
    results_data = load_json(RESULTS_FILE)
    submitted = sum(1 for d in results_data.values() if d.get("submitted"))
    await update.message.reply_text(
        "Royxatdan otgan: " + str(len(users)) + "\nJavob berdi: " + str(submitted) + "\nJavob bermadi: " + str(len(users) - submitted)
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(handle_choice, pattern="^vote_"),
            ],
            WRITING_COMMENT: [
                CallbackQueryHandler(handle_add_comment, pattern="^add_comment$"),
                CallbackQueryHandler(handle_request_revote, pattern="^request_revote$"),
                CallbackQueryHandler(handle_new_choice, pattern="^newvote_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment_text),
            ],
            WRITING_REPEAT_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_repeat_reason_text),
                CommandHandler("skip", handle_repeat_reason_text),
            ],
            CHOOSING_NEW: [
                CallbackQueryHandler(handle_new_choice, pattern="^newvote_"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("results", show_results))
    app.add_handler(CommandHandler("count", count))
    app.add_handler(CallbackQueryHandler(handle_admin_buttons))

    print("Bot ishga tushdi!")
    app.run_polling()


if __name__ == "__main__":
    main()
