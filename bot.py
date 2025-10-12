import logging
import random
import string
import asyncio
import time
import redis
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = "8465329960:AAH1mWkb9EO1eERvTQbR4WD2eTL5JD9IWBk"
CHANNELS = ["@EasyScriptRBX"]
ADMIN_USERNAMES = ["@coobaalt"]

# Проверяем переменные Redis
REDIS_URL = os.environ.get('REDIS_URL')

print(f"🔍 REDIS_URL: {REDIS_URL}")  # Для дебага

if not REDIS_URL:
    print("❌ REDIS_URL не найден! Используем память")
    USE_REDIS = False
else:
    try:
        r = redis.Redis.from_url(REDIS_URL)
        r.ping()  # Проверяем подключение
        print("✅ Redis подключен!")
        USE_REDIS = True
    except Exception as e:
        print(f"❌ Ошибка подключения к Redis: {e}")
        USE_REDIS = False

MAX_LINKS_PER_MINUTE = 10
user_limits = {}

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

def load_all_data():
    """Загружаем все данные из Redis или используем память"""
    if not USE_REDIS:
        print("💾 Используем оперативную память")
        return {}, set(), {'total_links': 0, 'total_clicks': 0}
    
    try:
        # Загружаем ссылки
        links_data = r.hgetall('links')
        links = {code.decode('utf-8'): url.decode('utf-8') for code, url in links_data.items()}
        
        # Загружаем пользователей
        users_data = r.smembers('users')
        users = {int(user_id.decode('utf-8')) for user_id in users_data}
        
        # Загружаем статистику
        total_links = r.get('total_links')
        total_clicks = r.get('total_clicks')
        
        stats = {
            'total_links': int(total_links) if total_links else 0,
            'total_clicks': int(total_clicks) if total_clicks else 0
        }
        
        print(f"✅ Загружено из Redis: {len(links)} ссылок, {len(users)} пользователей")
        return links, users, stats
        
    except Exception as e:
        print(f"❌ Ошибка загрузки из Redis: {e}")
        return {}, set(), {'total_links': 0, 'total_clicks': 0}

def save_link(short_code, original_url):
    """Сохраняем ссылку"""
    if USE_REDIS:
        try:
            r.hset('links', short_code, original_url)
            r.incr('total_links')
        except Exception as e:
            print(f"❌ Ошибка сохранения ссылки в Redis: {e}")

def save_user(user_id):
    """Сохраняем пользователя"""
    if USE_REDIS:
        try:
            r.sadd('users', user_id)
        except Exception as e:
            print(f"❌ Ошибка сохранения пользователя в Redis: {e}")

def save_click():
    """Сохраняем клик"""
    if USE_REDIS:
        try:
            r.incr('total_clicks')
        except Exception as e:
            print(f"❌ Ошибка сохранения клика в Redis: {e}")

# Загружаем данные при старте
links, users, stats = load_all_data()

def check_rate_limit(user_id):
    now = time.time()
    if user_id not in user_limits:
        user_limits[user_id] = []
    
    user_limits[user_id] = [t for t in user_limits[user_id] if now - t < 60]
    
    if len(user_limits[user_id]) >= MAX_LINKS_PER_MINUTE:
        return False
    
    user_limits[user_id].append(now)
    return True

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
        storage_type = "Redis" if USE_REDIS else "оперативную память"
        text = f"""🤖 Команды для админа:

🔗 Просто кинь ссылку - создам короткую
/start - начать работу  
/stats - статистика
/graph - график статистики
/stopbot - уведомить о тех.перерыве
/startbot - уведомить о возобновлении
/debug - отладочная информация

📊 Лимиты:
- {MAX_LINKS_PER_MINUTE} ссылок в минуту
- 💾 Данные в {storage_type}"""
    else:
        text = """🤖 Команды:

/start - начать работу
🔗 Перейди по короткой ссылке чтобы получить доступ"""

    await update.message.reply_text(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Регистрируем пользователя
    if user_id not in users:
        save_user(user_id)
        users.add(user_id)

    if context.args:
        short_code = context.args[0]
        original_url = links.get(short_code)
        
        if original_url:
            if await check_subscription(user_id, context):
                save_click()
                stats['total_clicks'] += 1
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
                    save_click()
                    stats['total_clicks'] += 1
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
            # Сохраняем в Redis и в память
            save_link(short_code, original_url)
            links[short_code] = original_url
            stats['total_links'] += 1
            
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
    
    # Обновляем данные
    global links, users, stats
    if USE_REDIS:
        links, users, stats = load_all_data()
    
    links_bar = "🟢" * min(stats['total_links'], 20)
    clicks_bar = "🔵" * min(stats['total_clicks'] // 10, 20)
    
    storage_type = "Redis" if USE_REDIS else "оперативной памяти"
    
    text = f"""📊 **Статистика:**

🟢 Ссылок: {stats['total_links']}
{links_bar}

🔵 Переходов: {stats['total_clicks']}  
{clicks_bar}

👥 Пользователей: {len(users)}

⚡ Лимит: {MAX_LINKS_PER_MINUTE}/мин
💾 Данные в {storage_type}"""
    
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
    
    # Обновляем данные
    global links, users, stats
    if USE_REDIS:
        links, users, stats = load_all_data()
    
    storage_type = "Redis" if USE_REDIS else "оперативной памяти"
    
    debug_info = f"""
🔍 **ДЕБАГ ИНФО:**

💾 Хранилище: {storage_type}
📊 Ссылок: {len(links)}
👥 Пользователей: {len(users)}
📈 Статистика: {stats}

📨 Примеры ссылок:
"""
    
    for i, (code, url) in enumerate(list(links.items())[:5]):
        debug_info += f"{i+1}. {code} → {url[:50]}...\n"
    
    await update.message.reply_text(debug_info)

async def restore_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        return
    
    old_links = {
        "test1": "https://google.com",
        "test2": "https://youtube.com", 
    }
    
    restored = 0
    for short_code, original_url in old_links.items():
        try:
            save_link(short_code, original_url)
            links[short_code] = original_url
            restored += 1
            print(f"✅ Восстановлена: {short_code} → {original_url}")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Ошибка восстановления {short_code}: {e}")
    
    stats['total_links'] = len(links)
    
    await update.message.reply_text(f"✅ Восстановлено {restored} старых ссылок! Теперь они должны работать.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    short_code = query.data[6:]

    if await check_subscription(user_id, context):
        original_url = links.get(short_code)
        if original_url:
            save_click()
            stats['total_clicks'] += 1
            await query.message.edit_text(f"✅ Спасибо за подписку!\n\n{original_url}")
        else:
            await query.message.edit_text("❌ Ссылка не найдена")
    else:
        await query.answer("❌ Ты еще не подписался на все каналы!", show_alert=True)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("graph", graph_command))
    app.add_handler(CommandHandler("stopbot", stopbot_command))
    app.add_handler(CommandHandler("startbot", startbot_command))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CommandHandler("restore", restore_links))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    storage_type = "Redis" if USE_REDIS else "оперативной памяти"
    print(f"🤖 Бот запущен! Данные сохраняются в {storage_type}")
    app.run_polling()

if __name__ == "__main__":
    main()
