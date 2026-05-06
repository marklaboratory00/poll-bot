""
Телеграм бот — рассылка опроса с приватными результатами
Требования: pip install python-telegram-bot==20.7

Как работает:
- Участники получают опрос с кнопками (не видят чужие ответы)
- Вы видите кто что выбрал через /results
- Участники думают что опрос анонимный :)
"""

import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ========================
# НАСТРОЙКИ — ЗАПОЛНИТЕ!
# ========================
BOT_TOKEN = "8634019645:AAGdLtgxl5GMjq-mw6jdDOIAbKTdOfCBUyQ"
ADMIN_ID = 7601846213
USERS_FILE = "users.json"
RESULTS_FILE = "results.json"

# ========================
# ВОПРОС И ВАРИАНТЫ
# ========================
POLL_QUESTION = (
    "📋 So'rovnoma (ANONIM)\n\n"
    "Agar siz biror xodimning ishga mas'uliyat bilan yondashuvida "
    "kamchiliklarni kuzatgan bo'lsangiz, iltimos o'z fikringizni qoldiring.\n\n"
    "Bir nechta javob tanlash mumkin. Tanlab bo'lgach '📨 Yuborish' tugmasini bosing:"
)

POLL_OPTIONS = [
    ("A", "Bosh Direktor (Ruxsora) da kamchilik bor"),
    ("B", "ROP Sotuv bo'limi rahbari (Zuhra) da kamchilik bor"),
    ("C", "Marketing bo'limi (Ziyoda) da kamchilik bor"),
    ("D", "Bosh Kurator (Madina) da kamchilik bor"),
]

# ========================
# РАБОТА С ФАЙЛАМИ
# ========================
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
            "username": username or "—",
            "name": full_name or "—",
            "joined": datetime.now().strftime("%d.%m.%Y %H:%M")
        })
        data["users"] = users
        save_json(USERS_FILE, data)


def build_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Строит клавиатуру. Отмечает уже выбранные варианты галочкой."""
    results = load_json(RESULTS_FILE)
    user_answers = results.get(str(user_id), {}).get("answers", [])

    buttons = []
    for code, text in POLL_OPTIONS:
        label = f"✅ {text}" if code in user_answers else text
        buttons.append([InlineKeyboardButton(label, callback_data=f"vote_{code}")])

    if user_answers:
        buttons.append([InlineKeyboardButton("📨 Yuborish (Отправить)", callback_data="submit")])

    return InlineKeyboardMarkup(buttons)


# ========================
# ХЭНДЛЕРЫ
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Регистрирует пользователя."""
    user = update.effective_user
    save_user(user.id, user.username, user.full_name)

    await update.message.reply_text(
        "👋 Salom!\n\n"
        "Bu so'rovnoma ANONIM — javoblaringiz faqat umumiy statistika sifatida ko'rinadi.\n\n"
        "So'rovnoma tez orada yuboriladi ✅"
    )

    users = load_users()
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ Новый участник: {user.full_name} (@{user.username or '—'})\n"
                 f"Всего зарегистрировано: {len(users)} чел."
        )
    except Exception as e:
        logger.error(e)


async def send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рассылает опрос всем. Только для админа."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Нет доступа.")
        return

    users = load_users()
    if not users:
        await update.message.reply_text("⚠️ Нет участников. Попросите людей написать /start боту.")
        return

    await update.message.reply_text(f"📤 Рассылаю {len(users)} участникам...")

    success, failed = 0, 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["id"],
                text=POLL_QUESTION,
                reply_markup=build_keyboard(user["id"])
            )
            success += 1
        except Exception as e:
            logger.error(f"Ошибка {user['id']}: {e}")
            failed += 1

    await update.message.reply_text(
        f"✅ Готово!\n"
        f"Отправлено: {success}\n"
        f"Ошибок: {failed}"
    )


async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие кнопок."""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    data = query.data

    # Пользователь нажал "Отправить"
    if data == "submit":
        results = load_json(RESULTS_FILE)
        user_data = results.get(str(user.id), {})
        answers = user_data.get("answers", [])

        if not answers:
            await query.answer("⚠️ Kamida bitta javob tanlang!", show_alert=True)
            return

        if user_data.get("submitted"):
            await query.answer("✅ Siz allaqachon javob yubordingiz!", show_alert=True)
            return

        user_data["submitted"] = True
        user_data["submitted_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        results[str(user.id)] = user_data
        save_json(RESULTS_FILE, results)

        answer_texts = [t for c, t in POLL_OPTIONS if c in answers]
        summary = "\n".join(f"✅ {t}" for t in answer_texts)

        await query.edit_message_text(
            f"📨 Javobingiz qabul qilindi. Rahmat!\n\n"
            f"Siz tanladingiz:\n{summary}"
        )

        # Уведомляем админа
        users_list = load_users()
        user_info = next((u for u in users_list if u["id"] == user.id), {})
        name = user_info.get("name", "—")
        username = user_info.get("username", "—")

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🗳 *Новый ответ!*\n\n"
                     f"👤 {name} (@{username})\n\n"
                     f"Выбрал(а):\n{summary}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(e)
        return

    # Пользователь нажал на вариант — переключаем выбор
    code = data.replace("vote_", "")
    results = load_json(RESULTS_FILE)

    if str(user.id) not in results:
        results[str(user.id)] = {"answers": [], "submitted": False}

    if results[str(user.id)].get("submitted"):
        await query.answer("✅ Siz allaqachon javob yubordingiz!", show_alert=True)
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
    """Показывает кто что выбрал. Только для админа."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Нет доступа.")
        return

    results_data = load_json(RESULTS_FILE)
    users_list = load_users()

    submitted = {uid: d for uid, d in results_data.items() if d.get("submitted")}

    if not submitted:
        await update.message.reply_text("📭 Ответов пока нет.")
        return

    # Подсчёт по вариантам
    counts = {code: [] for code, _ in POLL_OPTIONS}
    for user_id, data in submitted.items():
        user_info = next((u for u in users_list if str(u["id"]) == user_id), {})
        name = user_info.get("name", "—")
        for code in data["answers"]:
            if code in counts:
                counts[code].append(name)

    total = len(submitted)

    # Итоговое сообщение
    text = f"📊 *Результаты опроса* ({total} ответов)\n\n"

    for code, option_text in POLL_OPTIONS:
        names = counts[code]
        pct = round(len(names) / total * 100) if total > 0 else 0
        text += f"*{option_text}*\n"
        text += f"→ {len(names)} чел. ({pct}%)\n"
        if names:
            text += "  " + ", ".join(names) + "\n"
        text += "\n"

    text += "─" * 20 + "\n*Детально по участникам:*\n"
    for user_id, data in submitted.items():
        user_info = next((u for u in users_list if str(u["id"]) == user_id), {})
        name = user_info.get("name", "—")
        username = user_info.get("username", "—")
        answer_texts = [t for c, t in POLL_OPTIONS if c in data["answers"]]
        answers_str = "; ".join(answer_texts) if answer_texts else "—"
        text += f"\n👤 {name} (@{username})\n→ {answers_str}\n"

    # Telegram ограничивает длину — разбиваем если нужно
    if len(text) > 4000:
        await update.message.reply_text(text[:4000], parse_mode="Markdown")
        await update.message.reply_text(text[4000:], parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус: сколько зарегистрировано и ответило."""
    if update.effective_user.id != ADMIN_ID:
        return
    users = load_users()
    results_data = load_json(RESULTS_FILE)
    submitted = sum(1 for d in results_data.values() if d.get("submitted"))
    await update.message.reply_text(
        f"👥 Зарегистрировано: {len(users)}\n"
        f"✅ Ответили: {submitted}\n"
        f"⏳ Не ответили: {len(users) - submitted}"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send_poll", send_poll))
    app.add_handler(CommandHandler("results", show_results))
    app.add_handler(CommandHandler("count", count))
    app.add_handler(CallbackQueryHandler(handle_vote))

    print("🤖 Бот запущен!")
    print("Команды администратора:")
    print("  /send_poll — разослать опрос всем")
    print("  /results   — кто что выбрал (только вам)")
    print("  /count     — сколько ответили")
    app.run_polling()


if __name__ == "__main__":
    main()
