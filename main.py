import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8634019645:AAErehXl6uTTnw2IaoZ31afOkaZhO0xCLa4"
ADMIN_ID = 7601846213

USERS_FILE = "users.json"
RESULTS_FILE = "results.json"

POLL_QUESTION = (
    "Sovrovnoma (ANONIM)\n\n"
    "Agar siz biror xodimning ishga masuliyat bilan yondashuvida "
    "kamchiliklarni kuzatgan bolsangiz, iltimos oz fikringizni qoldiring.\n\n"
    "Bir nechta javob tanlash mumkin. Tanlab bolgach Yuborish tugmasini bosing:"
)

POLL_OPTIONS = [
    ("A", "Bosh Direktor (Ruxsora) da kamchilik bor"),
    ("B", "ROP Sotuv bolimi rahbari (Zuhra) da kamchilik bor"),
    ("C", "Marketing bolimi (Ziyoda) da kamchilik bor"),
    ("D", "Bosh Kurator (Madina) da kamchilik bor"),
]

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


def build_keyboard(user_id):
    results = load_json(RESULTS_FILE)
    user_answers = results.get(str(user_id), {}).get("answers", [])
    buttons = []
    for code, text in POLL_OPTIONS:
        label = "OK " + text if code in user_answers else text
        buttons.append([InlineKeyboardButton(label, callback_data="vote_" + code)])
    if user_answers:
        buttons.append([InlineKeyboardButton("Yuborish (Otpravit)", callback_data="submit")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.full_name)
    await update.message.reply_text(
        "Salom!\n\nBu sorovnoma ANONIM.\nJavoblaringiz faqat umumiy statistika sifatida korinadi."
    )
    await update.message.reply_text(
        POLL_QUESTION,
        reply_markup=build_keyboard(user.id)
    )
    users = load_users()
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text="Noviy uchastnik: " + str(user.full_name) + " (@" + str(user.username or "-") + ")\nVsego: " + str(len(users))
        )
    except Exception as e:
        logger.error(e)


async def send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Net dostupa.")
        return
    users = load_users()
    if not users:
        await update.message.reply_text("Net uchastnikov.")
        return
    await update.message.reply_text("Rassylayu " + str(len(users)) + " uchastnikam...")
    success = 0
    failed = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["id"],
                text=POLL_QUESTION,
                reply_markup=build_keyboard(user["id"])
            )
            success += 1
        except Exception as e:
            logger.error(e)
            failed += 1
    await update.message.reply_text("Gotovo! Otpravleno: " + str(success) + ", oshibok: " + str(failed))


async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "submit":
        results = load_json(RESULTS_FILE)
        user_data = results.get(str(user.id), {})
        answers = user_data.get("answers", [])
        if not answers:
            await query.answer("Kamida bitta javob tanlang!", show_alert=True)
            return
        if user_data.get("submitted"):
            await query.answer("Siz allaqachon javob yubordingiz!", show_alert=True)
            return
        user_data["submitted"] = True
        user_data["submitted_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        results[str(user.id)] = user_data
        save_json(RESULTS_FILE, results)
        answer_texts = [t for c, t in POLL_OPTIONS if c in answers]
        summary = "\n".join("- " + t for t in answer_texts)
        await query.edit_message_text("Javobingiz qabul qilindi. Rahmat!\n\nSiz tanladingiz:\n" + summary)
        users_list = load_users()
        user_info = next((u for u in users_list if u["id"] == user.id), {})
        name = user_info.get("name", "-")
        username = user_info.get("username", "-")
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text="Noviy otvet!\n\n" + name + " (@" + username + ")\n\nVybral:\n" + summary
            )
        except Exception as e:
            logger.error(e)
        return

    code = data.replace("vote_", "")
    results = load_json(RESULTS_FILE)
    if str(user.id) not in results:
        results[str(user.id)] = {"answers": [], "submitted": False}
    if results[str(user.id)].get("submitted"):
        await query.answer("Siz allaqachon javob yubordingiz!", show_alert=True)
        return
    answers = results[str(user.id)]["answers"]
    if code in answers:
        answers.remove(code)
    else:
        answers.append(code)
    results[str(user.id)]["answers"] = answers
    save_json(RESULTS_FILE, results)
    await query.edit_message_reply_markup(reply_markup=build_keyboard(user.id))


async def show_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Net dostupa.")
        return
    results_data = load_json(RESULTS_FILE)
    users_list = load_users()
    submitted = {uid: d for uid, d in results_data.items() if d.get("submitted")}
    if not submitted:
        await update.message.reply_text("Otvetov poka net.")
        return
    counts = {code: [] for code, _ in POLL_OPTIONS}
    for user_id, d in submitted.items():
        user_info = next((u for u in users_list if str(u["id"]) == user_id), {})
        name = user_info.get("name", "-")
        for code in d["answers"]:
            if code in counts:
                counts[code].append(name)
    total = len(submitted)
    text = "Rezultaty oprosa (" + str(total) + " otvetov)\n\n"
    for code, option_text in POLL_OPTIONS:
        names = counts[code]
        pct = round(len(names) / total * 100) if total > 0 else 0
        text += option_text + "\n"
        text += "-> " + str(len(names)) + " chel. (" + str(pct) + "%)\n"
        if names:
            text += "  " + ", ".join(names) + "\n"
        text += "\n"
    text += "---\nDetalno:\n"
    for user_id, d in submitted.items():
        user_info = next((u for u in users_list if str(u["id"]) == user_id), {})
        name = user_info.get("name", "-")
        username = user_info.get("username", "-")
        answer_texts = [t for c, t in POLL_OPTIONS if c in d["answers"]]
        text += "\n" + name + " (@" + username + ")\n-> " + "; ".join(answer_texts) + "\n"
    await update.message.reply_text(text)


async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = load_users()
    results_data = load_json(RESULTS_FILE)
    submitted = sum(1 for d in results_data.values() if d.get("submitted"))
    await update.message.reply_text(
        "Zaregistrirovano: " + str(len(users)) + "\nOtvetili: " + str(submitted) + "\nNe otvetili: " + str(len(users) - submitted)
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send_poll", send_poll))
    app.add_handler(CommandHandler("results", show_results))
    app.add_handler(CommandHandler("count", count))
    app.add_handler(CallbackQueryHandler(handle_vote))
    print("Bot zapushchen!")
    app.run_polling()


if __name__ == "__main__":
    main()
