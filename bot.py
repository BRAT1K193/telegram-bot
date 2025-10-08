import logging
import os
import random
import string
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройки
BOT_TOKEN = "8465329960:AAH1mWkb9EO1eERvTQbR4WD2eTL5JD9IWBk"
CHANNELS = ["@EasyScriptRBX"]
ADMIN_PASSWORD = "savva_gay"
ADMIN_MODE = False
ADMIN_USERNAMES = ["@coobaalt"]

# База данных PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')  # Railway сам добавит

try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS links
                    (id SERIAL PRIMARY KEY, original_url TEXT, short_code TEXT UNIQUE, clicks INTEGER DEFAULT 0)''')
    conn.commit()
    print("✅ Подключение к PostgreSQL установлено")
except:
    # Fallback на SQLite для локального тестирования
    import sqlite3
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS links
                    (id INTEGER PRIMARY KEY, original_url TEXT, short_code TEXT UNIQUE, clicks INTEGER DEFAULT 0)''')
    conn.commit()
    print("✅ Подключение к SQLite установлено")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

# Проверка подписки
async def check_subscription(user_id, context):
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            print(f"Ошибка проверки подписки для {channel}: {e}")
            return False
    return True

# Генерация кода
def generate_short_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

# Команда start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if context.args:
        short_code = context.args[0]
        cursor.execute("SELECT original_url FROM links WHERE short_code = %s", (short_code,))
        result = cursor.fetchone()

        if result:
            if await check_subscription(user_id, context):
                cursor.execute("UPDATE links SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
                conn.commit()
                await update.message.reply_text(f"{result[0]}")
            else:
                buttons = []
                for channel in CHANNELS:
                    try:
                        member = await context.bot.get_chat_member(channel, user_id)
                        if member.status not in ['member', 'administrator', 'creator']:
                            buttons.append([InlineKeyboardButton(f"📢 Подписаться на {channel}", url=f"https://t.me/{channel[1:]}")])
                    except:
                        buttons.append([InlineKeyboardButton(f"📢 Подписаться на {channel}", url=f"https://t.me/{channel[1:]}")])

                if buttons:
                    buttons.append([InlineKeyboardButton("✅ Я подписался", callback_data=f"check_{short_code}")])
                    await update.message.reply_text(
                        "📢 Для доступа к ссылке подпишись на каналы:",
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                else:
                    cursor.execute("UPDATE links SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
                    conn.commit()
                    await update.message.reply_text(f"{result[0]}")
        else:
            await update.message.reply_text("❌ Ссылка не найдена")
    else:
        return

# Создание ссылки
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_MODE
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if not ADMIN_MODE and user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Сначала активируй админ-режим: /admin пароль")
        return

    if update.message.text.startswith('http') or 'loadstring(game:HttpGet(' in update.message.text:
        original_url = update.message.text
        short_code = generate_short_code()

        try:
            cursor.execute("INSERT INTO links (original_url, short_code) VALUES (%s, %s)", (original_url, short_code))
            conn.commit()
            short_url = f"https://t.me/{context.bot.username}?start={short_code}"
            await update.message.reply_text(f"✅ Ссылка создана: {short_url}")
        except Exception as e:
            print(f"Ошибка БД: {e}")
            await update.message.reply_text("❌ Ошибка. Попробуй еще раз")

# Админка
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_MODE
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username in ADMIN_USERNAMES or (len(context.args) > 0 and context.args[0] == ADMIN_PASSWORD):
        ADMIN_MODE = True
        cursor.execute("SELECT COUNT(*), SUM(clicks) FROM links")
        stats = cursor.fetchone()
        text = f"📊 Статистика:\nСсылок: {stats[0]}\nПереходов: {stats[1] or 0}"
        await update.message.reply_text(f"✅ Админ-режим включен!\n{text}")
    else:
        await update.message.reply_text("❌ Неверный пароль")

# Кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if query.data.startswith("check_"):
        short_code = query.data[6:]
        if await check_subscription(user_id, context):
            cursor.execute("SELECT original_url FROM links WHERE short_code = %s", (short_code,))
            result = cursor.fetchone()
            if result:
                cursor.execute("UPDATE links SET clicks = clicks + 1 WHERE short_code = %s", (short_code,))
                conn.commit()
                await query.message.edit_text(f"✅ Спасибо за подписку!\n\n{result[0]}")
            else:
                await query.message.edit_text("❌ Ссылка не найдена")
        else:
            await query.answer("❌ Ты еще не подписался на все каналы!", show_alert=True)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
