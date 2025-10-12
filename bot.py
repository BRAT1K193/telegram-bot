# 🔧 ИСПРАВЛЕННЫЙ КОД:

import logging
import random
import string
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = "8465329960:AAH1mWkb9EO1eERvTQbR4WD2eTL5JD9IWBk"
CHANNELS = ["@EasyScriptRBX"]
ADMIN_USERNAMES = ["@coobaalt"]

LINKS_CHANNEL_ID = "-1003192392842"
USERS_CHANNEL_ID = "-1003138750808"  
STATS_CHANNEL_ID = "-1003119775402"

MAX_LINKS_PER_MINUTE = 10
user_limits = {}

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

links = {}
users = set()
stats = {"total_links": 0, "total_clicks": 0}
last_cache_update = 0
CACHE_TIMEOUT = 900

async def load_all_data(context, force=False):
    global links, users, stats, last_cache_update
    
    if not force and time.time() - last_cache_update < CACHE_TIMEOUT:
        return
        
    print("🔄 Обновление кэша...")
    
    links = {}
    users = set()
    
    try:
        async for message in context.bot.get_chat_history(LINKS_CHANNEL_ID, limit=1000):
            if message.text and message.text.startswith("LINK|||"):
                parts = message.text.split("|||")
                if len(parts) == 3:
                    short_code, original_url = parts[1], parts[2]
                    links[short_code] = original_url
        
        async for message in context.bot.get_chat_history(USERS_CHANNEL_ID, limit=1000):
            if message.text and message.text.startswith("USER|||"):
                user_id = int(message.text.split("|||")[1])
                users.add(user_id)
        
        async for message in context.bot.get_chat_history(STATS_CHANNEL_ID, limit=100):
            if message.text and message.text.startswith("STATS|||"):
                parts = message.text.split("|||")
                if len(parts) == 3:
                    stats["total_links"] = int(parts[1])
                    stats["total_clicks"] = int(parts[2])
                    break
        
        print(f"✅ Загружено из каналов: {len(links)} ссылок, {len(users)} пользователей")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки из каналов: {e}")
        links = {}
        users = set()
        stats = {"total_links": 0, "total_clicks": 0}
    
    last_cache_update = time.time()

def check_rate_limit(user_id):
    now = time.time()
    if user_id not in user_limits:
        user_limits[user_id] = []
    
    user_limits[user_id] = [t for t in user_limits[user_id] if now - t < 60]
    
    if len(user_limits[user_id]) >= MAX_LINKS_PER_MINUTE:
        return False
    
    user_limits[user_id].append(now)
    return True

async def save_link_to_channel(context, short_code, original_url):
    try:
        await context.bot.send_message(
            chat_id=LINKS_CHANNEL_ID,
            text=f"LINK|||{short_code}|||{original_url}"
        )
        return True
    except Exception as e:
        print(f"Ошибка сохранения ссылки: {e}")
        return False

async def save_user_to_channel(context, user_id):
    try:
        await context.bot.send_message(
            chat_id=USERS_CHANNEL_ID,
            text=f"USER|||{user_id}"
        )
        return True
    except Exception as e:
        print(f"Ошибка сохранения пользователя: {e}")
        return False

async def save_stats_to_channel(context):
    try:
        await context.bot.send_message(
            chat_id=STATS_CHANNEL_ID,
            text=f"STATS|||{stats['total_links']}|||{stats['total_clicks']}"
        )
        return True
    except Exception as e:
        print(f"Ошибка сохранения статистики: {e}")
        return False

async def check_subscription(user_id, context):
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def generate_short_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    
    if user_username in ADMIN_USERNAMES:
        text = f"""🤖 Команды для админа:

🔗 Просто кинь ссылку - создам короткую
/start - начать работу  
/stats - статистика
/graph - график статистики
/stopbot - уведомить о тех.перерыве
/startbot - уведомить о возобновлении

📊 Лимиты:
- {MAX_LINKS_PER_MINUTE} ссылок в минуту
- Авто-кэш каждые 15 минут"""
    else:
        text = """🤖 Команды:

/start - начать работу
🔗 Перейди по короткой ссылке чтобы получить доступ"""

    await update.message.reply_text(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    await load_all_data(context)
    
    if user_id not in users:
        users.add(user_id)
        await save_user_to_channel(context, user_id)

    if context.args:
        short_code = context.args[0]
        original_url = links.get(short_code)
        
        if original_url:
            if await check_subscription(user_id, context):
                stats["total_clicks"] += 1
                await save_stats_to_channel(context)
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
                    await save_stats_to_channel(context)
                    await update.message.reply_text(f"{original_url}")
        else:
            await update.message.reply_text("❌ Ссылка не найдена")
    else:
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    user_id = update.effective_user.id
    
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может создавать ссылки")
        return

    if not check_rate_limit(user_id):
        await update.message.reply_text(f"❌ Слишком много запросов! Максимум {MAX_LINKS_PER_MINUTE} ссылок в минуту")
        return

    if update.message.text.startswith('http') or 'loadstring(game:HttpGet' in update.message.text:
        original_url = update.message.text
        
        short_code = generate_short_code()

        try:
            links[short_code] = original_url
            await save_link_to_channel(context, short_code, original_url)
            
            stats["total_links"] += 1
            await save_stats_to_channel(context)
            
            short_url = f"https://t.me/{context.bot.username}?start={short_code}"
            await update.message.reply_text(f"✅ Ссылка создана: {short_url}")
        except Exception as e:
            print(f"Ошибка: {e}")
            await update.message.reply_text("❌ Ошибка. Попробуй еще раз")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может смотреть статистику")
        return
        
    await load_all_data(context)
    
    links_bar = "🟢" * min(stats['total_links'], 20)
    clicks_bar = "🔵" * min(stats['total_clicks'] // 10, 20)
    
    text = f"""📊 **Статистика:**

🟢 Ссылок: {stats['total_links']}
{links_bar}

🔵 Переходов: {stats['total_clicks']}  
{clicks_bar}

👥 Пользователей: {len(users)}

⚡ Лимит: {MAX_LINKS_PER_MINUTE}/мин"""
    
    await update.message.reply_text(text)

async def graph_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может смотреть графики")
        return
        
    graph = f"""
📈 График активности:

Ссылки:     {'█' * min(stats['total_links'] // 10, 10)} {stats['total_links']}
Переходы:   {'█' * min(stats['total_clicks'] // 10, 10)} {stats['total_clicks']}

🟢 = 10 ссылок
🔵 = 10 переходов"""
    
    await update.message.reply_text(graph)

async def broadcast(context, message):
    """Рассылает сообщение всем пользователям"""
    success = 0
    fail = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            success += 1
            await asyncio.sleep(0.1)
        except:
            fail += 1
    
    return success, fail

async def stopbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может останавливать бота")
        return
    
    success, fail = await broadcast(context, "🔴 Бот уходит на технический перерыв. Скоро вернемся!")
    await update.message.reply_text(f"✅ Уведомление отправлено:\nУспешно: {success}\nНе удалось: {fail}")

async def startbot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может запускать бота")
        return
    
    success, fail = await broadcast(context, "🟢 Бот снова в сети! Технические работы завершены.")
    await update.message.reply_text(f"✅ Уведомление отправлено:\nУспешно: {success}\nНе удалось: {fail}")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        return
    
    await load_all_data(context, force=True)
    
    debug_info = f"""
🔍 **ДЕБАГ ИНФО:**

📊 Загружено ссылок: {len(links)}
👥 Загружено пользователей: {len(users)}
🕐 Последнее обновление кэша: {time.time() - last_cache_update:.0f} сек назад

📨 Примеры ссылок в памяти:
"""
    
    for i, (code, url) in enumerate(list(links.items())[:5]):
        debug_info += f"{i+1}. {code} → {url[:50]}...\n"
    
    await update.message.reply_text(debug_info)

async def migrate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        return
    
    await update.message.reply_text("ℹ️ Миграция больше не нужна - бот работает с каналами")

async def fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        return
    
    try:
        info = "🔧 **ПРОВЕРКА КАНАЛА:**\n\n"
        
        message_count = 0
        async for message in context.bot.get_chat_history(LINKS_CHANNEL_ID, limit=10):
            message_count += 1
            info += f"📨 {message.text}\n"
        
        info += f"\n📊 Всего сообщений в канале: {message_count}"
        info += f"\n🔗 ID канала: {LINKS_CHANNEL_ID}"
        
        await update.message.reply_text(info)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    short_code = query.data[6:]

    if await check_subscription(user_id, context):
        original_url = links.get(short_code)
        if original_url:
            stats["total_clicks"] += 1
            await save_stats_to_channel(context)
            await query.message.edit_text(f"✅ Спасибо за подписку!\n\n{original_url}")
        else:
            await query.message.edit_text("❌ Ссылка не найдена")
    else:
        await query.answer("❌ Ты еще не подписался на все каналы!", show_alert=True)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    async def post_init(application):
        await load_all_data(application, force=True)
    
    app.post_init = post_init
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("graph", graph_command))
    app.add_handler(CommandHandler("stopbot", stopbot_command))
    app.add_handler(CommandHandler("startbot", startbot_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CommandHandler("migrate", migrate_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущен и работает с каналами!")
    app.run_polling()

if __name__ == "__main__":
    main()
