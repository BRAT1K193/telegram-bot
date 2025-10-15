import logging
import random
import string
import asyncio
import time
import requests
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

BOT_TOKEN = "8465329960:AAH1mWkb9EO1eERvTQbR4WD2eTL5JD9IWBk"
CHANNELS = ["@EasyScriptRBX", "@trushobi", "@robloxs_Scriptik", "@robloxstrall"]
ADMIN_USERNAMES = ["@coobaalt"]

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

MAX_LINKS_PER_MINUTE = 10
user_limits = {}

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

# Глобальные переменные
links = {}
users = set()
stats = {"total_links": 0, "total_clicks": 0}

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def load_all_data():
    """Загружаем все данные из Supabase"""
    global links, users, stats
    
    try:
        # Загружаем ссылки
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/links?select=short_code,original_url",
            headers=supabase_headers()
        )
        if response.status_code == 200:
            links_data = response.json()
            links = {item['short_code']: item['original_url'] for item in links_data}
        else:
            links = {}
            print(f"❌ Ошибка загрузки ссылок: {response.status_code}")

        # Загружаем пользователей
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/users?select=user_id",
            headers=supabase_headers()
        )
        if response.status_code == 200:
            users_data = response.json()
            users = {item['user_id'] for item in users_data}
        else:
            users = set()
            print(f"❌ Ошибка загрузки пользователей: {response.status_code}")

        # Загружаем статистику
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/stats?select=total_links,total_clicks&order=id.desc&limit=1",
            headers=supabase_headers()
        )
        if response.status_code == 200 and response.json():
            stats_data = response.json()[0]
            stats.update({
                "total_links": stats_data.get('total_links', 0),
                "total_clicks": stats_data.get('total_clicks', 0)
            })
        else:
            stats.update({"total_links": 0, "total_clicks": 0})
            print(f"❌ Ошибка загрузки статистики: {response.status_code}")

        print(f"✅ Загружено из Supabase: {len(links)} ссылок, {len(users)} пользователей")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки из Supabase: {e}")
        links = {}
        users = set()
        stats = {"total_links": 0, "total_clicks": 0}

def update_stats_links():
    """Обновляем количество ссылок в Supabase"""
    try:
        # Сначала получаем текущую запись статистики
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/stats?select=id&order=id.desc&limit=1",
            headers=supabase_headers()
        )
        if response.status_code == 200 and response.json():
            stats_id = response.json()[0]['id']
            # Обновляем существующую запись
            data = {"total_links": stats["total_links"]}
            response = requests.patch(
                f"{SUPABASE_URL}/rest/v1/stats?id=eq.{stats_id}",
                json=data,
                headers=supabase_headers()
            )
            return response.status_code == 200
        else:
            # Создаем новую запись если нет существующей
            data = {
                "total_links": stats["total_links"],
                "total_clicks": stats["total_clicks"]
            }
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/stats",
                json=data,
                headers=supabase_headers()
            )
            return response.status_code == 201
    except Exception as e:
        print(f"❌ Ошибка обновления статистики ссылок: {e}")
        return False

def update_stats_clicks():
    """Обновляем количество кликов в Supabase"""
    try:
        # Сначала получаем текущую запись статистики
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/stats?select=id&order=id.desc&limit=1",
            headers=supabase_headers()
        )
        if response.status_code == 200 and response.json():
            stats_id = response.json()[0]['id']
            # Обновляем существующую запись
            data = {"total_clicks": stats["total_clicks"]}
            response = requests.patch(
                f"{SUPABASE_URL}/rest/v1/stats?id=eq.{stats_id}",
                json=data,
                headers=supabase_headers()
            )
            return response.status_code == 200
        else:
            # Создаем новую запись если нет существующей
            data = {
                "total_links": stats["total_links"],
                "total_clicks": stats["total_clicks"]
            }
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/stats",
                json=data,
                headers=supabase_headers()
            )
            return response.status_code == 201
    except Exception as e:
        print(f"❌ Ошибка обновления статистики кликов: {e}")
        return False

def save_link(short_code, original_url):
    """Сохраняем ссылку в Supabase и обновляем статистику"""
    try:
        # Сохраняем ссылку
        data = {
            "short_code": short_code,
            "original_url": original_url
        }
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/links",
            json=data,
            headers=supabase_headers()
        )
        
        if response.status_code == 201:
            print(f"✅ Ссылка сохранена в Supabase: {short_code}")
            
            # Обновляем статистику
            stats["total_links"] += 1
            update_stats_links()
            
            return True
        else:
            print(f"❌ Ошибка сохранения ссылки: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка сохранения ссылки: {e}")
        return False

def save_user(user_id):
    """Сохраняем пользователя в Supabase"""
    try:
        data = {"user_id": user_id}
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/users",
            json=data,
            headers=supabase_headers()
        )
        if response.status_code in [201, 409]:  # 409 = уже существует
            return True
        else:
            print(f"❌ Ошибка сохранения пользователя: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователя: {e}")
        return False

# Загружаем данные при старте
load_all_data()

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
        text = f"""🤖 Команды для админа:

🔗 Просто кинь ссылку - создам короткую
/start - начать работу  
/stats - статистика
/graph - график статистики
/stopbot - уведомить о тех.перерыве
/startbot - уведомить о возобновлении
/debug - отладочная информация
/channels - управление каналами подписки

📊 Лимиты:
- {MAX_LINKS_PER_MINUTE} ссылок в минуту
- 💾 Данные в Supabase"""
    else:
        text = """🤖 Команды:

/start - начать работу
🔗 Перейди по короткой ссылке чтобы получить доступ"""

    await update.message.reply_text(text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Регистрируем пользователя только если его нет
    if user_id not in users:
        if save_user(user_id):
            users.add(user_id)
            print(f"✅ Новый пользователь: {user_id}")

    if context.args:
        short_code = context.args[0]
        original_url = links.get(short_code)
        
        if original_url:
            if await check_subscription(user_id, context):
                stats["total_clicks"] += 1
                update_stats_clicks()
                await update.message.reply_text(original_url)
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
                    update_stats_clicks()
                    await update.message.reply_text(original_url)
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
            # Сохраняем в Supabase и в память
            if save_link(short_code, original_url):
                links[short_code] = original_url
                
                short_url = f"https://t.me/{context.bot.username}?start={short_code}"
                await update.message.reply_text(f"✅ Ссылка создана: {short_url}")
            else:
                await update.message.reply_text("❌ Ошибка сохранения ссылки")
        except Exception as e:
            print(f"Ошибка: {e}")
            await update.message.reply_text("❌ Ошибка. Попробуй еще раз")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может смотреть статистику")
        return
    
    # Обновляем данные из Supabase
    load_all_data()
    
    links_bar = "🟢" * min(stats['total_links'], 20)
    clicks_bar = "🔵" * min(stats['total_clicks'] // 10, 20)
    
    text = f"""📊 **Статистика:**

🟢 Ссылок: {stats['total_links']}
{links_bar}

🔵 Переходов: {stats['total_clicks']}  
{clicks_bar}

👥 Пользователей: {len(users)}

⚡ Лимит: {MAX_LINKS_PER_MINUTE}/мин
💾 Данные в Supabase"""
    
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
    load_all_data()
    
    debug_info = f"""
🔍 **ДЕБАГ ИНФО:**

💾 Хранилище: Supabase
📊 Ссылок: {len(links)}
👥 Пользователей: {len(users)}
📈 Статистика: {stats}

📢 Каналы подписки: {CHANNELS}

🔗 Supabase URL: {SUPABASE_URL[:30]}...

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
            if save_link(short_code, original_url):
                links[short_code] = original_url
                restored += 1
                print(f"✅ Восстановлена: {short_code} → {original_url}")
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Ошибка восстановления {short_code}: {e}")
    
    await update.message.reply_text(f"✅ Восстановлено {restored} старых ссылок! Теперь они должны работать.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    short_code = query.data[6:]

    if await check_subscription(user_id, context):
        original_url = links.get(short_code)
        if original_url:
            stats["total_clicks"] += 1
            update_stats_clicks()
            await query.message.edit_text(f"Спасибо за подписку!\n\n{original_url}")
        else:
            await query.message.edit_text("❌ Ссылка не найдена")
    else:
        await query.answer("❌ Ты еще не подписался на все каналы!", show_alert=True)

# НОВЫЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ КАНАЛАМИ
async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущие каналы для подписки"""
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может управлять каналами")
        return
    
    if not CHANNELS:
        text = "📢 Список каналов для подписки пуст"
    else:
        text = "📢 **Текущие каналы для подписки:**\n\n"
        for i, channel in enumerate(CHANNELS, 1):
            text += f"{i}. {channel}\n"
    
    text += "\n🔧 **Команды:**\n"
    text += "/addchannel @username - добавить канал\n"
    text += "/removechannel @username - удалить канал\n"
    text += "💡 **Формат:** @username (например: @robloxs_Scriptik)"
    
    await update.message.reply_text(text)

async def addchannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить канал для подписки"""
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может добавлять каналы")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Укажи канал: /addchannel @username")
        return
    
    channel = context.args[0]
    
    # Проверяем формат канала
    if not channel.startswith('@'):
        await update.message.reply_text("❌ Неправильный формат! Используй: @username\nНапример: /addchannel @robloxs_Scriptik")
        return
    
    if channel in CHANNELS:
        await update.message.reply_text(f"❌ Канал {channel} уже в списке")
        return
    
    # Проверяем что бот админ в канале
    try:
        chat_member = await context.bot.get_chat_member(channel, context.bot.id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text(f"❌ Бот не является админом в канале {channel}")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки канала: {e}\nУбедись что бот добавлен как админ в канал!")
        return
    
    CHANNELS.append(channel)
    await update.message.reply_text(f"✅ Канал {channel} добавлен в список для подписки!")

async def removechannel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить канал из подписки"""
    user_username = f"@{update.effective_user.username}" if update.effective_user.username else ""
    if user_username not in ADMIN_USERNAMES:
        await update.message.reply_text("❌ Только админ может удалять каналы")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Укажи канал: /removechannel @username")
        return
    
    channel = context.args[0]
    
    if channel not in CHANNELS:
        await update.message.reply_text(f"❌ Канал {channel} не найден в списке")
        return
    
    CHANNELS.remove(channel)
    await update.message.reply_text(f"✅ Канал {channel} удален из списка для подписки!")

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
    app.add_handler(CommandHandler("channels", channels_command))
    app.add_handler(CommandHandler("addchannel", addchannel_command))
    app.add_handler(CommandHandler("removechannel", removechannel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущен! Данные сохраняются в Supabase")
    print(f"📢 Текущие каналы подписки: {CHANNELS}")
    app.run_polling()

if __name__ == "__main__":
    main()
