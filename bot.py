import os
import telebot
from telebot import types
from flask import Flask, request
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import csv
import io
import threading
import time
import requests
from io import BytesIO
import hmac
import hashlib

# ===== НАСТРОЙКИ =====
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
SUPPORT_USERNAME = "coo_vernost"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
CHANNEL_USERNAME = "@defferent_shop"
REF_BONUS = 5
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")
KRAB_API_KEY = os.environ.get("KRAB_API_KEY")
KRAB_WEBHOOK_SECRET = os.environ.get("KRAB_WEBHOOK_SECRET")
KRAB_API_URL = "https://api.krab.gg/v1"
DATABASE_URL = os.environ.get("DATABASE_URL")
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", 0))

IMG_START = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261012_231702_com_lemon_lvoverseas_EditActivity.jpg"
IMG_PROFILE = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261012_205847_com_lemon_lvoverseas_EditActivity.jpg"
IMG_PRICE = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261012_232337_com_lemon_lvoverseas_EditActivity.jpg"
IMG_HELP = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261012_232832_com_lemon_lvoverseas_EditActivity.jpg"
IMG_REF = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261013_024508_com_lemon_lvoverseas_EditActivity.jpg"
IMG_PROMO = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261013_015351_com_lemon_lvoverseas_EditActivity.jpg"
IMG_ADMIN = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261013_015539_com_lemon_lvoverseas_EditActivity.jpg"
IMG_PREMIUM = "https://raw.githubusercontent.com/pidorasgejvork-gif/Reposut/refs/heads/main/Screenshot_20261014_011702_com_lemon_lvoverseas_EditActivity.jpg"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

STAR_RATE = 1.4
PRICES = [
    (50, 50 * STAR_RATE), (100, 100 * STAR_RATE), (150, 150 * STAR_RATE), (250, 250 * STAR_RATE),
    (500, 500 * STAR_RATE), (1000, 1000 * STAR_RATE), (2500, 2500 * STAR_RATE), (5000, 5000 * STAR_RATE),
]
PREMIUM_PRICES = {"3": 1200, "6": 1600, "12": 2800}

FAQ_TEXT = (
    "📖 <b>Часто задаваемые вопросы</b>\n\n"
    "🕐 <b>1. Как быстро приходят звёзды?</b>\n"
    "Обычно в течение <b>1–10 минут</b> после оплаты. В редких случаях — до 30 минут (при высокой нагрузке на сеть Telegram).\n\n"
    "❓ <b>2. Что делать, если звёзды не пришли?</b>\n"
    "Подожди <b>10 минут</b>. Если звёзды не пришли — напиши в поддержку, указав <b>номер заказа</b> и юзернейм получателя. Мы разберёмся и выдадим повторно или вернём деньги.\n\n"
    "💳 <b>3. Какие способы оплаты доступны?</b>\n"
    "• <b>USDT</b> (криптовалюта)\n"
    "• <b>TON</b> (криптовалюта)\n"
    "• <b>СБП</b> (оплата по QR-коду в рублях)\n"
    "• <b>Баланс бота</b> (если уже пополнен)\n\n"
    "💰 <b>4. Как пополнить баланс бота?</b>\n"
    "Двумя способами:\n"
    "• <b>Через админа</b> — напиши в поддержку, он начислит вручную.\n"
    "• <b>Через автопополнение</b> — используй команду <code>/topup СУММА</code>.\n\n"
    "🛡 <b>5. Безопасно ли покупать у вас?</b>\n"
    "Да. Мы работаем через <b>проверенную платёжную систему</b> и дорожим репутацией. Все заказы автоматические, деньги защищены.\n\n"
    "↩️ <b>6. Что с гарантией и возвратом?</b>\n"
    "Если звёзды не пришли по нашей вине — <b>вернём деньги</b> или выдадим повторно. Если ты ошибся с юзернеймом — поможем решить вопрос через поддержку.\n\n"
    "❓ <b>Остались вопросы?</b>\n"
    "Напиши в техподдержку — ответим в течение 15 минут."
)

# ===== ЛОГИ =====
def log_to_channel(text):
    if LOG_CHANNEL_ID:
        try:
            bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка логов: {e}")

# ===== БАЗА ДАННЫХ (PostgreSQL) =====
def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            discount INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            total_purchases INTEGER DEFAULT 0,
            referrer_id BIGINT DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT, amount INTEGER, price REAL, status TEXT, created_at TEXT,
            krab_order_id TEXT, payment_status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS premium_orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT, recipient TEXT, months INTEGER, price REAL, status TEXT, created_at TEXT,
            krab_order_id TEXT, payment_status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, discount INTEGER, uses_left INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY, user_id BIGINT, text TEXT, created_at TEXT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def add_user(user_id, username):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, balance, created_at) VALUES (%s, %s, 0, %s)
        ON CONFLICT(user_id) DO UPDATE SET username = EXCLUDED.username
    """, (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    cursor.close()
    conn.close()

def get_user_data(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def add_balance(user_id, amount):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    cursor.close()
    conn.close()

def apply_promo(user_id, code):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT discount, uses_left FROM promos WHERE code = %s", (code,))
    row = cursor.fetchone()
    if row and row["uses_left"] > 0:
        cursor.execute("UPDATE promos SET uses_left = uses_left - 1 WHERE code = %s", (code,))
        cursor.execute("UPDATE users SET discount = %s WHERE user_id = %s", (row["discount"], user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return row["discount"]
    cursor.close()
    conn.close()
    return None

def get_all_users():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [r["user_id"] for r in rows]

def ban_user(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET banned = 1 WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def unban_user(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET banned = 0 WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def is_banned(user_id):
    user = get_user_data(user_id)
    return user["banned"] == 1 if user else False

def add_promo(code, discount, uses_left):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO promos (code, discount, uses_left) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET discount = EXCLUDED.discount, uses_left = EXCLUDED.uses_left", (code, discount, uses_left))
    conn.commit()
    cursor.close()
    conn.close()

def add_review(user_id, text):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reviews (user_id, text, created_at) VALUES (%s, %s, %s)", (user_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    cursor.close()
    conn.close()

# ===== CRYPTO PAY =====
def crypto_create_invoice(amount_usdt, description, payload, asset="USDT"):
    try:
        headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN, "Content-Type": "application/json"}
        data = {"asset": asset, "amount": str(amount_usdt), "description": description, "payload": payload}
        response = requests.post("https://pay.crypt.bot/api/createInvoice", headers=headers, json=data, timeout=10)
        if response.status_code == 200 and response.json().get("ok"):
            return response.json()["result"]["pay_url"]
        return None
    except:
        return None

# ===== KRAB.GG (С ЗАЩИТОЙ ОТ ТАЙМАУТА) =====
def krab_create_stars_order(username, quantity, local_order_id):
    try:
        headers = {"Authorization": f"Bearer {KRAB_API_KEY}", "Content-Type": "application/json"}
        payload = {"type": "stars", "qty": quantity, "username": username.replace("@", ""), "orderId": str(local_order_id)}
        response = requests.post(f"{KRAB_API_URL}/orders", json=payload, headers=headers, timeout=15)
        if response.status_code == 200: return response.json()
        return None
    except requests.exceptions.Timeout: return "TIMEOUT"
    except: return None

def krab_create_premium_order(username, months, local_order_id):
    try:
        headers = {"Authorization": f"Bearer {KRAB_API_KEY}", "Content-Type": "application/json"}
        payload = {"type": "premium", "months": months, "username": username.replace("@", ""), "orderId": str(local_order_id)}
        response = requests.post(f"{KRAB_API_URL}/orders", json=payload, headers=headers, timeout=15)
        if response.status_code == 200: return response.json()
        return None
    except requests.exceptions.Timeout: return "TIMEOUT"
    except: return None

# ===== ФОНОВАЯ ПРОВЕРКА ЗАВИСШИХ ЗАКАЗОВ =====
def check_order_status(order_id, krab_order_id, user_id, amount, price, order_type="stars"):
    time.sleep(300) # Ждём 5 минут
    conn = get_conn()
    cursor = conn.cursor()
    if order_type == "stars":
        cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
    else:
        cursor.execute("SELECT status FROM premium_orders WHERE id = %s", (order_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row and row["status"] != "выполнен":
        log_to_channel(f"⚠️ <b>ЗАВИСШИЙ ЗАКАЗ</b>\nID: {order_id}\nKRAB: {krab_order_id}\nЮзер: {user_id}")
        try: bot.send_message(user_id, f"⚠️ <b>Заказ задерживается.</b>\n\nМы уже проверяем статус у поставщика. Если звёзды не придут в течение 30 минут — напишите в поддержку.")
        except: pass

# ===== КЛАВИАТУРЫ =====
def get_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👤 Профиль"), types.KeyboardButton("❓ Помощь"))
    markup.add(types.KeyboardButton("⭐ Купить звёзды"), types.KeyboardButton("💎 Купить Premium"))
    markup.add(types.KeyboardButton("💰 Баланс"), types.KeyboardButton("🎁 Рефералы"))
    markup.add(types.KeyboardButton("🎟 Промокод"), types.KeyboardButton("⭐ Отзывы"))
    markup.add(types.KeyboardButton("📖 FAQ"), types.KeyboardButton("🛠 Тех поддержка"))
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📊 Статистика"), types.KeyboardButton("👥 Пользователи"))
    markup.add(types.KeyboardButton("🧾 Заказы"), types.KeyboardButton("📢 Рассылка"))
    markup.add(types.KeyboardButton("🎟 Создать промокод"), types.KeyboardButton("📤 Экспорт"))
    markup.add(types.KeyboardButton("🏠 В меню"))
    return markup

def get_support_inline():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}"))
    markup.add(types.InlineKeyboardButton("🏠 В меню", callback_data="menu_main"))
    return markup

def get_price_inline(user_id):
    user = get_user_data(user_id)
    discount = user["discount"] if user else 0
    markup = types.InlineKeyboardMarkup(row_width=2)
    for amount, price in PRICES:
        final_price = price * (1 - discount / 100)
        markup.add(types.InlineKeyboardButton(f"⭐ {amount} — {final_price:.0f}₽", callback_data=f"buy_{amount}"))
    markup.add(types.InlineKeyboardButton("🏠 В меню", callback_data="menu_main"))
    return markup

def get_start_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"), types.InlineKeyboardButton("❓ Помощь", callback_data="menu_help"))
    markup.add(types.InlineKeyboardButton("⭐ Купить звёзды", callback_data="menu_pay"), types.InlineKeyboardButton("💎 Купить Premium", callback_data="menu_premium"))
    markup.add(types.InlineKeyboardButton("💰 Баланс", callback_data="menu_balance"), types.InlineKeyboardButton("🎁 Рефералы", callback_data="menu_ref"))
    markup.add(types.InlineKeyboardButton("🎟 Промокод", callback_data="menu_promo"), types.InlineKeyboardButton("⭐ Отзывы", callback_data="menu_reviews"))
    markup.add(types.InlineKeyboardButton("📖 FAQ", callback_data="menu_faq"))
    markup.add(types.InlineKeyboardButton("🛠 Тех поддержка", url=f"https://t.me/{SUPPORT_USERNAME}"))
    return markup

def get_back_to_menu_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 В меню", callback_data="menu_main"))
    return markup

def get_sub_check_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
    markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
    return markup

def get_premium_recipient_inline():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🎁 Себе", callback_data="prem_self"))
    markup.add(types.InlineKeyboardButton("🎁 Другому пользователю", callback_data="prem_other"))
    markup.add(types.InlineKeyboardButton("🏠 В меню", callback_data="menu_main"))
    return markup

def get_premium_period_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("⭐ 3 месяца", callback_data="prem_3"))
    markup.add(types.InlineKeyboardButton("⭐ 6 месяцев", callback_data="prem_6"))
    markup.add(types.InlineKeyboardButton("⭐ 12 месяцев", callback_data="prem_12"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="prem_back"))
    return markup

def get_premium_pay_inline():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💎 USDT", callback_data="prem_pay_usdt"))
    markup.add(types.InlineKeyboardButton("💳 Списать с баланса", callback_data="prem_pay_balance"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="prem_back"))
    return markup

def get_stars_pay_inline(amount):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 Списать с баланса", callback_data=f"buy_pay_balance_{amount}"))
    markup.add(types.InlineKeyboardButton("💎 USDT", callback_data=f"buy_pay_usdt_{amount}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_pay"))
    return markup

def send_typing(chat_id):
    try: bot.send_chat_action(chat_id, "typing")
    except: pass

def send_photo_safe(chat_id, photo_url, caption, reply_markup=None):
    try:
        response = requests.get(photo_url, timeout=10)
        photo = BytesIO(response.content)
        photo.name = 'image.jpg'
        bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
    except:
        bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=reply_markup)

# ===== КОМАНДЫ =====
@bot.message_handler(commands=['start'])
def start(message):
    try:
        if is_banned(message.from_user.id):
            return bot.send_message(message.chat.id, "🚫 Вы забанены.")
        add_user(message.from_user.id, message.from_user.username or "без_ника")
        caption = "🌟 <b>Добро пожаловать в Different Shop!</b>\n\n⚡️ <b>У нас ты найдёшь Telegram Stars и Premium по лучшему курсу.</b>"
        send_photo_safe(message.chat.id, IMG_START, caption, get_start_inline())
        log_to_channel(f"👤 <b>Новый пользователь</b>\nID: <code>{message.from_user.id}</code>\n@{message.from_user.username or 'без_ника'}")
    except Exception as e: print(f"ОШИБКА start: {e}")

@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    send_photo_safe(message.chat.id, IMG_ADMIN, "🛠 <b>Админ-панель</b>", get_admin_keyboard())

@bot.message_handler(commands=['topup'])
def topup_cmd(message):
    try:
        _, amount_str = message.text.split()
        amount = float(amount_str)
        if amount < 100: return bot.send_message(message.chat.id, "Минимум 100₽.")
        amount_usdt = round(amount / 90, 2)
        pay_url = crypto_create_invoice(amount_usdt, f"Пополнение на {amount}₽", f"{message.from_user.id}:topup:{amount}")
        if pay_url:
            markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💎 Оплатить", url=pay_url))
            bot.send_message(message.chat.id, f"💳 <b>Пополнение</b>\nСумма: {amount}₽\nК оплате: {amount_usdt} USDT", parse_mode="HTML", reply_markup=markup)
    except: bot.send_message(message.chat.id, "Формат: /topup 500")

@bot.message_handler(commands=['promo'])
def promo_cmd(message):
    try:
        _, code = message.text.split()
        discount = apply_promo(message.from_user.id, code.upper())
        if discount: bot.send_message(message.chat.id, f"🎟 Промокод активирован! Скидка: {discount}%")
        else: bot.send_message(message.chat.id, "❌ Промокод не найден.")
    except: bot.send_message(message.chat.id, "Формат: /promo КОД")

@bot.message_handler(commands=['gift'])
def gift_cmd(message):
    try:
        _, username, amount_str = message.text.split()
        amount = int(amount_str)
        user = get_user_data(message.from_user.id)
        price = amount * STAR_RATE
        if user["balance"] < price: return bot.send_message(message.chat.id, "❌ Недостаточно средств.")
        add_balance(message.from_user.id, -price)
        bot.send_message(message.chat.id, f"🎁 Подарок отправлен @{username}!")
        log_to_channel(f"🎁 Подарок от {message.from_user.id} для @{username}.")
    except: bot.send_message(message.chat.id, "Формат: /gift @username 100")

@bot.message_handler(commands=['faq'])
def faq_cmd(message):
    bot.send_message(message.chat.id, FAQ_TEXT, parse_mode="HTML", reply_markup=get_back_to_menu_inline())

@bot.message_handler(commands=['give'])
def give_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, user_id, amount = message.text.split()
        add_balance(int(user_id), float(amount))
        bot.send_message(message.chat.id, f"✅ Начислено {amount}₽ пользователю {user_id}")
        log_to_channel(f"💰 Админ начислил {amount}₽ пользователю {user_id}")
    except: bot.send_message(message.chat.id, "Формат: /give ID СУММА")

@bot.message_handler(commands=['createpromo'])
def createpromo_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, code, discount, uses = message.text.split()
        add_promo(code.upper(), int(discount), int(uses))
        bot.send_message(message.chat.id, f"✅ Промокод {code.upper()} создан: -{discount}%, {uses} использований")
    except: bot.send_message(message.chat.id, "Формат: /createpromo КОД СКИДКА КОЛИЧЕСТВО")

# ===== INLINE МЕНЮ =====
@bot.callback_query_handler(func=lambda call: call.data in ["menu_main", "menu_profile", "menu_help", "menu_pay", "menu_premium", "menu_balance", "menu_ref", "menu_promo", "menu_reviews", "menu_faq", "check_sub"])
def inline_menu(call):
    try:
        if call.data == "menu_main":
            bot.edit_message_text("🌟 <b>Главное меню</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=get_start_inline())
        elif call.data == "menu_pay":
            bot.edit_message_text("Выберите количество звёзд:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_price_inline(call.from_user.id))
        elif call.data == "menu_profile":
            user = get_user_data(call.from_user.id)
            bot.edit_message_text(f"👤 <b>Профиль</b>\n💰 Баланс: {user['balance']:.2f}₽\n💸 Потрачено: {user['total_spent']:.2f}₽", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        elif call.data == "menu_faq":
            bot.edit_message_text(FAQ_TEXT, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        elif call.data == "menu_premium":
            bot.edit_message_text("💎 Выберите получателя Premium:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=get_premium_recipient_inline())
        bot.answer_callback_query(call.id)
    except Exception as e: print(f"ОШИБКА inline_menu: {e}")

# ===== ПОКУПКА ЗВЁЗД =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_") and not call.data.startswith("buy_pay_"))
def buy_callback(call):
    amount = int(call.data.split("_")[1])
    user = get_user_data(call.from_user.id)
    discount = user["discount"] if user else 0
    price = amount * STAR_RATE * (1 - discount / 100)
    
    text = f"⭐ <b>Покупка {amount} звёзд</b>\n\n"
    if discount > 0: text += f"🎟 Скидка: {discount}%\n"
    text += f"💵 К оплате: {price:.0f}₽\n\nВыберите способ оплаты:"
    
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=get_stars_pay_inline(amount))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_pay_balance_"))
def buy_pay_balance(call):
    amount = int(call.data.split("_")[3])
    user = get_user_data(call.from_user.id)
    discount = user["discount"] if user else 0
    price = amount * STAR_RATE * (1 - discount / 100)
    
    if user["balance"] < price:
        return bot.answer_callback_query(call.id, "❌ Недостаточно средств!", show_alert=True)
        
    add_balance(call.from_user.id, -price)
    conn = get_conn(); cursor = conn.cursor(); cursor.execute("UPDATE users SET discount = 0 WHERE user_id = %s", (call.from_user.id,)); conn.commit(); cursor.close(); conn.close()
    
    username = call.from_user.username or str(call.from_user.id)
    msg = bot.edit_message_text("⏳ Создаем заказ...", chat_id=call.message.chat.id, message_id=call.message.message_id)
    result = krab_create_stars_order(username, amount, int(time.time()))
    
    if result == "TIMEOUT":
        add_balance(call.from_user.id, price)
        bot.edit_message_text("⚠️ Поставщик не отвечает. Деньги возвращены.", chat_id=call.message.chat.id, message_id=msg.message_id)
        return
        
    if result:
        conn = get_conn(); cursor = conn.cursor()
        cursor.execute("INSERT INTO orders (user_id, amount, price, status, krab_order_id, payment_status, created_at) VALUES (%s,%s,%s,'создан',%s,'оплачен',%s)", (call.from_user.id, amount, price, str(result.get("orderId")), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); cursor.close(); conn.close()
        bot.edit_message_text(f"✅ <b>Заказ оплачен!</b>\n⭐ {amount} звёзд\n⏳ Ожидайте зачисления.", chat_id=call.message.chat.id, message_id=msg.message_id, parse_mode="HTML")
    else:
        add_balance(call.from_user.id, price)
        bot.edit_message_text("⚠️ Ошибка. Деньги возвращены.", chat_id=call.message.chat.id, message_id=msg.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_pay_usdt_"))
def buy_pay_usdt(call):
    amount = int(call.data.split("_")[3])
    user = get_user_data(call.from_user.id)
    discount = user["discount"] if user else 0
    price = amount * STAR_RATE * (1 - discount / 100)
    amount_usdt = round(price / 90, 2)
    pay_url = crypto_create_invoice(amount_usdt, f"{amount} звёзд", f"{call.from_user.id}:stars:{amount}:{price}")
    if pay_url:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💎 Оплатить", url=pay_url))
        bot.edit_message_text(f"💳 Счет на {amount_usdt} USDT создан.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка создания счета.", show_alert=True)

# ===== ВЕБХУКИ (FLASK) =====
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route("/", methods=["GET"])
def index(): return "Bot is running", 200

@app.route("/crypto/webhook", methods=["POST"])
def crypto_webhook():
    raw_body = request.get_data()
    signature = request.headers.get("crypto-pay-api-signature")
    secret = hashlib.sha256(CRYPTO_PAY_TOKEN.encode()).digest()
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected): return "Forbidden", 403
    
    update = request.get_json()
    if update.get("update_type") == "invoice_paid":
        payload = update["payload"].get("payload", "")
        parts = payload.split(":")
        if len(parts) >= 3 and parts[1] == "topup":
            add_balance(int(parts[0]), float(parts[2]))
            try: bot.send_message(int(parts[0]), f"✅ Баланс пополнен на {parts[2]}₽")
            except: pass
    return "OK", 200

@app.route("/krab/webhook", methods=["POST"])
def krab_webhook():
    raw_body = request.get_data()
    signature = request.headers.get("X-Signature") or request.headers.get("x-signature")
    expected = hmac.new(KRAB_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    if signature and not hmac.compare_digest(signature, expected): return "Forbidden", 403
    update = request.get_json()
    if not update: return "OK", 200
    
    order_id = str(update.get("orderId") or update.get("order_id"))
    if update.get("status") in ["completed", "success", "done"]:
        conn = get_conn(); cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount FROM orders WHERE krab_order_id = %s", (order_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE orders SET status = 'выполнен' WHERE krab_order_id = %s", (order_id,))
            conn.commit()
            try: bot.send_message(row["user_id"], f"🎉 Звёзды ({row['amount']}) зачислены!")
            except: pass
        cursor.close(); conn.close()
    return "OK", 200

# ===== ЗАПУСК =====
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8080))
    print("Бот запущен...")
    app.run(host="0.0.0.0", port=port)
