import logging
import random
import string
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Настройки
BOT_TOKEN = "8465329960:AAH1mWkb9EO1eERvTQbR4WD2eTL5JD9IWBk"
CHANNELS = ["@EasyScriptRBX"]
ADMIN_USERNAMES = ["@coobaalt"]

# Файлы для хранения
LINKS_FILE = 'links.json'
STATS_FILE = 'stats.json'

# Загрузка данных
def load_links():
    try:
        if os.path.exists(LINKS_FILE):
            with open(LINKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def load_stats():
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"total_links": 0, "total_clicks": 0}

def save_links(links_dict):
    try:
        with open(LINKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(links_dict, f, ensure_ascii=False, indent=2)
    except:
        pass

def save_stats(stats_dict):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats_dict, f, ensure_ascii=False, indent=2)
    except:
        pass

# Загружаем данные
links = load_links()
stats = load_stats()

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

# Проверка подписки
async def check_subscription(user_id, context):
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
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
        original_url = links.get(short_code)
        
        if original_url:
            if await check_subscription(user_id, context):
                # Обновляем статистику переходов
                stats["total_clicks"] += 1
                save_stats(stats)
                await update.message.reply_text(f"{original_url}")
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
                    stats["total_clicks"] += 1
                    save_stats(stats)
                    await update.message.reply_text(f"{original_url}")
        else:
            await update.message.reply_text("❌ Ссылка не найдена")
    else:
        return

# Создание ссылки
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может создавать ссылки")
        return

    if update.message.text.startswith('http') or 'loadstring(game:HttpGet' in update.message.text:
        original_url = update.message.text
        
        short_code = generate_short_code()

        try:
            links[short_code] = original_url
            save_links(links)
            
            stats["total_links"] += 1
            save_stats(stats)
            
            short_url = f"https://t.me/{context.bot.username}?start={short_code}"
            await update.message.reply_text(f"✅ Ссылка создана: {short_url}")
        except Exception as e:
            print(f"Ошибка: {e}")
            await update.message.reply_text("❌ Ошибка. Попробуй еще раз")

# Статистика
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может смотреть статистику")
        return
        
    text = f"📊 Статистика:\nСсылок: {stats['total_links']}\nПереходов: {stats['total_clicks']}"
    await update.message.reply_text(text)

# Кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    short_code = query.data[6:]

    if await check_subscription(user_id, context):
        original_url = links.get(short_code)
        if original_url:
            stats["total_clicks"] += 1
            save_stats(stats)
            await query.message.edit_text(f"✅ Спасибо за подписку!\n\n{original_url}")
        else:
            await query.message.edit_text("❌ Ссылка не найдена")
    else:
        await query.answer("❌ Ты еще не подписался на все каналы!", show_alert=True)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
