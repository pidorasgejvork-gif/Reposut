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

# ===== ЛОГИ =====
def log_to_channel(text):
    if LOG_CHANNEL_ID:
        try:
            bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка логов: {e}")

# ===== БАЗА (PostgreSQL) =====
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
            user_id BIGINT,
            amount INTEGER,
            price REAL,
            status TEXT,
            created_at TEXT,
            krab_order_id TEXT,
            payment_status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY,
            discount INTEGER,
            uses_left INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            text TEXT,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS premium_orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            recipient TEXT,
            months INTEGER,
            price REAL,
            status TEXT,
            created_at TEXT,
            krab_order_id TEXT,
            payment_status TEXT
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

def get_balance(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row["balance"] if row else 0

def get_profile(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT balance, total_spent, total_purchases, ref_count FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return row["balance"], row["total_spent"], row["total_purchases"], row["ref_count"]
    return 0, 0, 0, 0

def add_balance(user_id, amount):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, balance, created_at) VALUES (%s, %s, %s, %s)
        ON CONFLICT(user_id) DO UPDATE SET balance = users.balance + %s
    """, (user_id, "без_ника", amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), amount))
    conn.commit()
    cursor.close()
    conn.close()

def add_order(user_id, amount, price, status="новый", krab_order_id=None, payment_status="ожидает оплаты"):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, amount, price, status, created_at, krab_order_id, payment_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (user_id, amount, price, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), krab_order_id, payment_status))
    order_id = cursor.fetchone()["id"]
    conn.commit()
    cursor.close()
    conn.close()
    return order_id

def add_premium_order(user_id, recipient, months, price, status="новый", krab_order_id=None, payment_status="ожидает оплаты"):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO premium_orders (user_id, recipient, months, price, status, created_at, krab_order_id, payment_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (user_id, recipient, months, price, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), krab_order_id, payment_status))
    order_id = cursor.fetchone()["id"]
    conn.commit()
    cursor.close()
    conn.close()
    return order_id

def update_order_status(user_id, krab_order_id, payment_status, status):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders SET payment_status = %s, status = %s 
        WHERE user_id = %s AND krab_order_id = %s
    """, (payment_status, status, user_id, krab_order_id))
    conn.commit()
    cursor.close()
    conn.close()

def update_premium_status(user_id, krab_order_id, payment_status, status):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE premium_orders SET payment_status = %s, status = %s 
        WHERE user_id = %s AND krab_order_id = %s
    """, (payment_status, status, user_id, krab_order_id))
    conn.commit()
    cursor.close()
    conn.close()

def get_order_by_krab_id(krab_order_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, price FROM orders WHERE krab_order_id = %s", (krab_order_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return row["user_id"], row["amount"], row["price"]
    return None

def get_premium_by_krab_id(krab_order_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, recipient, months, price FROM premium_orders WHERE krab_order_id = %s", (krab_order_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return row["user_id"], row["recipient"], row["months"], row["price"]
    return None

def get_order_by_local_id(order_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, price, status, krab_order_id, payment_status FROM orders WHERE id = %s", (order_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def get_stats():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as c FROM users")
    users_count = cursor.fetchone()["c"]
    cursor.execute("SELECT COUNT(*) as c FROM orders")
    orders_count = cursor.fetchone()["c"]
    cursor.execute("SELECT COALESCE(SUM(amount), 0) as s FROM orders")
    stars_sold = cursor.fetchone()["s"]
    cursor.execute("SELECT COALESCE(SUM(price), 0) as s FROM orders")
    total_money = cursor.fetchone()["s"]
    cursor.close()
    conn.close()
    return users_count, orders_count, stars_sold, total_money

def set_referrer(user_id, referrer_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    if row and row["referrer_id"] == 0 and user_id != referrer_id:
        cursor.execute("UPDATE users SET referrer_id = %s WHERE user_id = %s", (referrer_id, user_id))
        cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = %s", (referrer_id,))
        cursor.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (REF_BONUS, referrer_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    cursor.close()
    conn.close()
    return False

def get_user_by_username(username):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

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
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT banned FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row["banned"] == 1 if row else False

def get_all_users():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [r["user_id"] for r in rows]

def add_promo(code, discount, uses_left):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO promos (code, discount, uses_left) VALUES (%s, %s, %s) ON CONFLICT (code) DO UPDATE SET discount = EXCLUDED.discount, uses_left = EXCLUDED.uses_left", (code, discount, uses_left))
    conn.commit()
    cursor.close()
    conn.close()

def use_promo(code):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT discount, uses_left FROM promos WHERE code = %s", (code,))
    row = cursor.fetchone()
    if row and row["uses_left"] > 0:
        cursor.execute("UPDATE promos SET uses_left = uses_left - 1 WHERE code = %s", (code,))
        conn.commit()
        cursor.close()
        conn.close()
        return row["discount"]
    cursor.close()
    conn.close()
    return None

def add_review(user_id, text):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reviews (user_id, text, created_at) VALUES (%s, %s, %s)", (user_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    cursor.close()
    conn.close()

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===== CRYPTO PAY =====
def crypto_create_invoice(amount_usdt, description, payload, asset="USDT"):
    try:
        headers = {
            "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
            "Content-Type": "application/json"
        }
        data = {
            "asset": asset,
            "amount": str(amount_usdt),
            "description": description,
            "payload": payload
        }
        response = requests.post("https://pay.crypt.bot/api/createInvoice", headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                return result["result"]["pay_url"]
        print(f"CryptoBot ошибка: {response.status_code} {response.text}")
        return None
    except Exception as e:
        print(f"Ошибка CryptoBot: {e}")
        return None

# ===== KRAB.GG API =====
def krab_create_stars_order(username, quantity, local_order_id):
    try:
        headers = {"Authorization": f"Bearer {KRAB_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "type": "stars",
            "qty": quantity,
            "username": username.replace("@", ""),
            "orderId": str(local_order_id)
        }
        response = requests.post(f"{KRAB_API_URL}/orders", json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        print(f"KRAB stars ошибка: {response.status_code} {response.text}")
        return None
    except Exception as e:
        print(f"Ошибка KRAB stars: {e}")
        return None

def krab_create_premium_order(username, months, local_order_id):
    try:
        headers = {"Authorization": f"Bearer {KRAB_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "type": "premium",
            "months": months,
            "username": username.replace("@", ""),
            "orderId": str(local_order_id)
        }
        response = requests.post(f"{KRAB_API_URL}/orders", json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        print(f"KRAB premium ошибка: {response.status_code} {response.text}")
        return None
    except Exception as e:
        print(f"Ошибка KRAB premium: {e}")
        return None

# ===== ОБРАБОТКА НЕУДАЧНЫХ ЗАКАЗОВ =====
def process_failed_order(user_id, amount, price, order_type="stars", recipient=None, months=None):
    log_to_channel(
        f"⚠️ <b>НЕУДАЧНЫЙ ЗАКАЗ</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"⭐ Звёзд: {amount}\n"
        f"💸 Сумма: {price:.0f}₽\n"
        f"📅 KRAB не создал заказ\n"
        f"🔁 Используй /retry для повтора"
    )
    try:
        bot.send_message(
            ADMIN_ID,
            f"⚠️ <b>ЗАКАЗ НЕ СОЗДАН В KRAB!</b>\n\n"
            f"👤 ID: <code>{user_id}</code>\n"
            f"⭐ Звёзд: {amount}\n"
            f"💸 Сумма: {price:.0f}₽\n\n"
            f"<b>Деньги списаны, но звёзды не выданы!</b>"
        )
    except:
        pass

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

def get_price_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    for amount, price in PRICES:
        markup.add(types.InlineKeyboardButton(f"⭐ {amount} — {price:.0f}₽", callback_data=f"buy_{amount}"))
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
    markup.add(types.InlineKeyboardButton("💎 TON", callback_data="prem_pay_ton"))
    markup.add(types.InlineKeyboardButton("💳 Списать с баланса", callback_data="prem_pay_balance"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="prem_back"))
    return markup

def get_stars_pay_inline():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💎 USDT", callback_data="buy_pay_usdt"))
    markup.add(types.InlineKeyboardButton("💎 TON", callback_data="buy_pay_ton"))
    markup.add(types.InlineKeyboardButton("💳 Списать с баланса", callback_data="buy_pay_balance"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="menu_pay"))
    return markup

def send_typing(chat_id):
    try:
        bot.send_chat_action(chat_id, "typing")
    except:
        pass

def send_photo_safe(chat_id, photo_url, caption, reply_markup=None):
    try:
        response = requests.get(photo_url, timeout=10)
        photo = BytesIO(response.content)
        photo.name = 'image.jpg'
        bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")
        bot.send_message(chat_id, caption, parse_mode="HTML", reply_markup=reply_markup)

# ===== FAQ =====
FAQ_TEXT = (
    "📖 <b>Часто задаваемые вопросы</b>\n\n"
    "<b>1. Как быстро приходят звёзды?</b>\n"
    "Обычно в течение 1–5 минут после оплаты. В редких случаях до 30 минут.\n\n"
    "<b>2. Что делать, если звёзды не пришли?</b>\n"
    "Подожди 30 минут. Если не пришли — напиши в поддержку с номером заказа.\n\n"
    "<b>3. Как оплатить?</b>\n"
    "USDT, TON или спиши с баланса бота.\n\n"
    "<b>4. Можно ли оплатить картой?</b>\n"
    "Пока нет. Работаем над этим.\n\n"
    "<b>5. Как пополнить баланс?</b>\n"
    "Пока только через админа. Скоро добавим автопополнение.\n\n"
    "<b>6. Безопасно ли это?</b>\n"
    "Да. Работаем через проверенного поставщика KRAB.GG.\n\n"
    "<b>7. Что с гарантией?</b>\n"
    "Если звёзды не пришли — возвращаем деньги или выдаём повторно.\n\n"
    "❓ Остались вопросы — напиши в поддержку."
)

# ===== КОМАНДЫ =====
@bot.message_handler(commands=['start'])
def start(message):
    try:
        if is_banned(message.from_user.id):
            bot.send_message(message.chat.id, "🚫 <b>Вы забанены.</b>", parse_mode="HTML")
            return
        args = message.text.split()
        add_user(message.from_user.id, message.from_user.username or "без_ника")
        if len(args) > 1:
            try:
                referrer_id = int(args[1])
                if set_referrer(message.from_user.id, referrer_id):
                    try:
                        bot.send_message(referrer_id, f"🎉 <b>По вашей ссылке пришёл новый пользователь!</b>\n+{REF_BONUS}₽ на баланс.", parse_mode="HTML")
                    except:
                        pass
            except:
                pass
        caption = (
            "🌟 <b>Добро пожаловать в Defferent Shop!</b>\n\n"
            "⚡️ <b>У нас ты найдёшь Telegram Stars, Premium-подписки, а также аренду NFT-подарков, юзернеймов и анонимных номеров.</b>\n\n"
            "💎 <b>Мы не просто говорим, что мы лучшие — это подтверждают наши клиенты:</b>\n"
            "— Лучшие цены на рынке\n"
            "— Мгновенная выдача товара\n"
            "— Более 5000 довольных покупателей\n"
            "— Автоматическая доставка 24/7\n\n"
            "🛒 <b>Выбирай, что нужно, и получай сразу!</b>"
        )
        send_typing(message.chat.id)
        send_photo_safe(message.chat.id, IMG_START, caption, get_start_inline())
        log_to_channel(f"👤 <b>Новый пользователь</b>\nID: <code>{message.from_user.id}</code>\n@{message.from_user.username or 'без_ника'}")
    except Exception as e:
        print(f"ОШИБКА start: {e}")
        bot.send_message(message.chat.id, f"⚠️ <b>Ошибка:</b> {e}", parse_mode="HTML")

@bot.message_handler(commands=['help'])
def help_command(message):
    try:
        send_typing(message.chat.id)
        caption = (
            "📖 <b>Помощь</b>\n\n"
            "👤 <b>Профиль</b> — ваш профиль и статистика\n"
            "💎 <b>Прайс</b> — цены на звёзды\n"
            "⭐ <b>Купить звёзды</b> — оформить покупку\n"
            "💎 <b>Купить Premium</b> — оформить подписку\n"
            "💰 <b>Баланс</b> — проверить счёт\n"
            "🎁 <b>Рефералы</b> — пригласить друзей\n"
            "🎟 <b>Промокод</b> — активировать скидку\n"
            "📖 <b>FAQ</b> — частые вопросы\n"
            "🛠 <b>Тех поддержка</b> — связаться с нами"
        )
        send_photo_safe(message.chat.id, IMG_HELP, caption, get_back_to_menu_inline())
    except Exception as e:
        print(f"ОШИБКА help: {e}")

@bot.message_handler(commands=['faq'])
def faq_cmd(message):
    try:
        send_typing(message.chat.id)
        bot.send_message(message.chat.id, FAQ_TEXT, parse_mode="HTML", reply_markup=get_back_to_menu_inline())
    except Exception as e:
        print(f"ОШИБКА faq: {e}")

@bot.message_handler(commands=['price'])
def price_cmd(message):
    try:
        send_typing(message.chat.id)
        text = "💎 <b>Прайс-лист:</b>\n\n"
        for amount, price in PRICES:
            text += f"⭐ <b>{amount} звёзд</b> — {price:.0f}₽\n"
        text += "\n<b>Выберите количество для покупки:</b>"
        send_photo_safe(message.chat.id, IMG_PRICE, text, get_price_inline())
    except Exception as e:
        print(f"ОШИБКА price: {e}")

@bot.message_handler(commands=['pay'])
def pay(message):
    price_cmd(message)

@bot.message_handler(commands=['premium'])
def premium_cmd(message):
    try:
        send_typing(message.chat.id)
        caption = (
            "💎 <b>Покупка Telegram Premium</b>\n\n"
            "⚠️ <b>Получить премиум на аккаунт могут только пользователи без активной подписки</b> ⚠️\n\n"
            "<i>Выберите получателя премиума:</i>"
        )
        send_photo_safe(message.chat.id, IMG_PREMIUM, caption, get_premium_recipient_inline())
    except Exception as e:
        print(f"ОШИБКА premium: {e}")

@bot.message_handler(commands=['balance'])
def balance(message):
    try:
        send_typing(message.chat.id)
        bal = get_balance(message.from_user.id)
        bot.send_message(message.chat.id, f"💰 <b>Ваш баланс:</b> {bal:.2f}₽.", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
    except Exception as e:
        print(f"ОШИБКА balance: {e}")

@bot.message_handler(commands=['tp'])
def tp(message):
    try:
        bot.send_message(message.chat.id, "🛠 <b>Тех поддержка</b>\nНажми кнопку ниже:", parse_mode="HTML", reply_markup=get_support_inline())
    except Exception as e:
        print(f"ОШИБКА tp: {e}")

@bot.message_handler(commands=['profile'])
def profile(message):
    try:
        user_id = message.from_user.id
        add_user(user_id, message.from_user.username or "без_ника")
        balance, total_spent, total_purchases, ref_count = get_profile(user_id)
        caption = (
            f"👤 <b>Профиль</b>\n\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
            f"💰 <b>Баланс:</b> {balance:.2f}₽\n"
            f"💸 <b>Сумма покупок:</b> {total_spent:.2f}₽\n"
            f"🛒 <b>Количество покупок:</b> {total_purchases}\n"
            f"🎁 <b>Приглашено:</b> {ref_count}"
        )
        send_typing(message.chat.id)
        send_photo_safe(message.chat.id, IMG_PROFILE, caption, get_back_to_menu_inline())
    except Exception as e:
        print(f"ОШИБКА profile: {e}")

@bot.message_handler(commands=['ref'])
def ref_cmd(message):
    try:
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={message.from_user.id}"
        _, _, _, ref_count = get_profile(message.from_user.id)
        caption = (
            f"🎁 <b>Реферальная система</b>\n\n"
            f"<b>Приглашай друзей и получай {REF_BONUS}₽ за каждого!</b>\n\n"
            f"👥 <b>Приглашено:</b> {ref_count}\n\n"
            f"🔗 <b>Ваша ссылка:</b>\n<code>{link}</code>"
        )
        send_typing(message.chat.id)
        send_photo_safe(message.chat.id, IMG_REF, caption, get_back_to_menu_inline())
    except Exception as e:
        print(f"ОШИБКА ref: {e}")

@bot.message_handler(commands=['promo'])
def promo_cmd(message):
    try:
        send_typing(message.chat.id)
        send_photo_safe(message.chat.id, IMG_PROMO, "🎟 <b>Введите промокод:</b>\n\nНапример: <code>/promo SALE10</code>", get_back_to_menu_inline())
    except Exception as e:
        print(f"ОШИБКА promo: {e}")

@bot.message_handler(commands=['myorders'])
def myorders_cmd(message):
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, amount, price, status, created_at FROM orders WHERE user_id = %s ORDER BY id DESC LIMIT 10", (message.from_user.id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "🧾 <b>У вас пока нет заказов.</b>", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
            return
        text = "🧾 <b>Ваши последние заказы:</b>\n\n"
        for row in rows:
            text += f"#{row['id']} | {row['amount']}⭐ | {row['price']}₽ | {row['status']} | {row['created_at']}\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=get_back_to_menu_inline())
    except Exception as e:
        print(f"ОШИБКА myorders: {e}")

@bot.message_handler(commands=['retry'])
def retry_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, order_id = message.text.split()
        order = get_order_by_local_id(int(order_id))
        if not order:
            bot.send_message(message.chat.id, "❌ Заказ не найден.")
            return
        user_id = order["user_id"]
        amount = order["amount"]
        price = order["price"]
        krab_order_id = order["krab_order_id"]

        if krab_order_id and order["status"] == "выполнен":
            bot.send_message(message.chat.id, "✅ Заказ уже выполнен.")
            return

        username = str(user_id)
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row and row["username"]:
                username = row["username"]
        except:
            pass

        local_order_id = int(time.time())
        result = krab_create_stars_order(username, amount, local_order_id)
        if result:
            new_krab_id = result.get("orderId") or result.get("order_id")
            update_order_status(user_id, krab_order_id, "ожидает оплаты в KRAB", "создан в KRAB (retry)")
            bot.send_message(message.chat.id, f"✅ Заказ #{order_id} повторно создан в KRAB.\n🆔 Новый ID: {new_krab_id}")
            log_to_channel(f"🔁 <b>RETRY заказа #{order_id}</b>\n👤 ID: <code>{user_id}</code>\n⭐ {amount} звёзд")
        else:
            bot.send_message(message.chat.id, "❌ Не удалось создать заказ в KRAB. Проверь логи.")
    except:
        bot.send_message(message.chat.id, "Формат: /retry ID")

# ===== АДМИН =====
@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        send_photo_safe(message.chat.id, IMG_ADMIN, "🛠 <b>Админ-панель</b>", get_admin_keyboard())
    except Exception as e:
        print(f"ОШИБКА admin: {e}")

@bot.message_handler(commands=['give'])
def give(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, user_id, amount = message.text.split()
        add_balance(int(user_id), float(amount))
        bot.send_message(message.chat.id, f"✅ Начислено {amount}₽ пользователю {user_id}")
        try:
            bot.send_message(int(user_id), f"🎉 <b>Вам начислено {amount}₽!</b>", parse_mode="HTML")
        except:
            pass
        log_to_channel(f"💰 <b>Начисление</b>\n👤 ID: <code>{user_id}</code>\n💸 {amount}₽")
    except:
        bot.send_message(message.chat.id, "Формат: /give ID СУММА")

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        users_count, orders_count, stars_sold, total_money = get_stats()
        bot.send_message(message.chat.id, f"📊 <b>Статистика:</b>\n\n👥 Пользователей: {users_count}\n🧾 Заказов: {orders_count}\n⭐ Продано звёзд: {stars_sold}\n💰 Заработано: {total_money:.2f}₽", parse_mode="HTML")
    except Exception as e:
        print(f"ОШИБКА stats: {e}")

@bot.message_handler(commands=['users'])
def users_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, balance, total_spent FROM users ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "Пользователей нет.")
            return
        text = "👥 <b>Последние 50 пользователей:</b>\n\n"
        for row in rows:
            text += f"ID: <code>{row['user_id']}</code> | @{row['username']} | {row['balance']:.2f}₽ | куплено: {row['total_spent']:.2f}₽\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    except Exception as e:
        print(f"ОШИБКА users: {e}")

@bot.message_handler(commands=['find'])
def find_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, username = message.text.split()
        username = username.replace("@", "")
        row = get_user_by_username(username)
        if row:
            bot.send_message(message.chat.id, f"ID: <code>{row['user_id']}</code>\nНик: @{row['username']}\nБаланс: {row['balance']:.2f}₽", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "Не найден.")
    except:
        bot.send_message(message.chat.id, "Формат: /find @username")

@bot.message_handler(commands=['ban'])
def ban_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, user_id = message.text.split()
        ban_user(int(user_id))
        bot.send_message(message.chat.id, f"✅ Забанен {user_id}")
    except:
        bot.send_message(message.chat.id, "Формат: /ban ID")

@bot.message_handler(commands=['unban'])
def unban_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, user_id = message.text.split()
        unban_user(int(user_id))
        bot.send_message(message.chat.id, f"✅ Разбанен {user_id}")
    except:
        bot.send_message(message.chat.id, "Формат: /unban ID")

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        text = message.text.replace("/broadcast", "").strip()
        if not text:
            bot.send_message(message.chat.id, "Формат: /broadcast текст")
            return
        users = get_all_users()
        sent = 0
        for uid in users:
            try:
                bot.send_message(uid, text, parse_mode="HTML")
                sent += 1
                time.sleep(0.05)
            except:
                pass
        bot.send_message(message.chat.id, f"✅ Отправлено {sent} из {len(users)}")
    except Exception as e:
        print(f"ОШИБКА broadcast: {e}")

@bot.message_handler(commands=['export'])
def export_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, balance, total_spent, total_purchases, ref_count FROM users")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["user_id", "username", "balance", "total_spent", "total_purchases", "ref_count"])
        for row in rows:
            writer.writerow([row["user_id"], row["username"], row["balance"], row["total_spent"], row["total_purchases"], row["ref_count"]])
        output.seek(0)
        bot.send_document(message.chat.id, ("users.csv", output.getvalue().encode("utf-8")))
    except Exception as e:
        print(f"ОШИБКА export: {e}")

@bot.message_handler(commands=['orders'])
def orders_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, amount, price, status, created_at FROM orders ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "Заказов нет.")
            return
        text = "🧾 <b>Последние 20 заказов:</b>\n\n"
        for row in rows:
            text += f"#{row['id']} | {row['user_id']} | {row['amount']}⭐ | {row['price']}₽ | {row['status']} | {row['created_at']}\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    except Exception as e:
        print(f"ОШИБКА orders: {e}")

@bot.message_handler(commands=['createpromo'])
def createpromo_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, code, discount, uses = message.text.split()
        add_promo(code.upper(), int(discount), int(uses))
        bot.send_message(message.chat.id, f"✅ Промокод {code.upper()} создан: -{discount}%, {uses} использований")
    except:
        bot.send_message(message.chat.id, "Формат: /createpromo КОД СКИДКА КОЛИЧЕСТВО")

# ===== БЭКАП =====
def backup_loop():
    while True:
        time.sleep(86400)
        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, balance, total_spent, total_purchases, ref_count FROM users")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["user_id", "username", "balance", "total_spent", "total_purchases", "ref_count"])
            for row in rows:
                writer.writerow([row["user_id"], row["username"], row["balance"], row["total_spent"], row["total_purchases"], row["ref_count"]])
            output.seek(0)
            bot.send_document(ADMIN_ID, ("backup_users.csv", output.getvalue().encode("utf-8")))
        except Exception as e:
            print(f"Backup error: {e}")

threading.Thread(target=backup_loop, daemon=True).start()

# ===== ОБРАБОТКА КНОПОК =====
@bot.message_handler(content_types=['text'])
def handle_buttons(message):
    try:
        text = message.text
        add_user(message.from_user.id, message.from_user.username or "без_ника")

        if text.startswith("/promo"):
            try:
                code = text.split()[1].upper()
                discount = use_promo(code)
                if discount:
                    bot.send_message(message.chat.id, f"🎟 <b>Промокод активирован!</b>\nСкидка: {discount}%", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
                else:
                    bot.send_message(message.chat.id, "❌ <b>Промокод не найден или закончился.</b>", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
            except:
                bot.send_message(message.chat.id, "Формат: /promo КОД", reply_markup=get_back_to_menu_inline())
            return

        if message.from_user.id == ADMIN_ID:
            if text == "📊 Статистика":
                stats(message); return
            elif text == "👥 Пользователи":
                users_cmd(message); return
            elif text == "🧾 Заказы":
                orders_cmd(message); return
            elif text == "📢 Рассылка":
                bot.send_message(message.chat.id, "Напиши: /broadcast текст"); return
            elif text == "🎟 Создать промокод":
                bot.send_message(message.chat.id, "Формат: /createpromo КОД СКИДКА КОЛИЧЕСТВО"); return
            elif text == "📤 Экспорт":
                export_cmd(message); return
            elif text == "🏠 В меню":
                bot.send_message(message.chat.id, "🏠 <b>Главное меню</b>", parse_mode="HTML", reply_markup=get_keyboard()); return

        if text == "👤 Профиль":
            profile(message)
        elif text == "❓ Помощь":
            help_command(message)
        elif text == "⭐ Купить звёзды":
            pay(message)
        elif text == "💎 Купить Premium":
            premium_cmd(message)
        elif text == "💰 Баланс":
            balance(message)
        elif text == "🎁 Рефералы":
            ref_cmd(message)
        elif text == "🎟 Промокод":
            promo_cmd(message)
        elif text == "⭐ Отзывы":
            bot.send_message(message.chat.id, "⭐ <b>Оставьте отзыв:</b>\n\nНапишите текст отзыва в чат.", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
        elif text == "📖 FAQ":
            faq_cmd(message)
        elif text == "🛠 Тех поддержка":
            tp(message)
        else:
            if len(text) > 10 and not text.startswith("/"):
                add_review(message.from_user.id, text)
                bot.send_message(message.chat.id, "⭐ <b>Спасибо за отзыв!</b>", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
                log_to_channel(f"⭐ <b>Новый отзыв</b>\n👤 ID: <code>{message.from_user.id}</code>\n{text}")
            else:
                bot.send_message(message.chat.id, f"Не знаю такой команды: {text}\nВоспользуйся кнопками ниже.", reply_markup=get_keyboard())

    except Exception as e:
        print(f"ОШИБКА handle_buttons: {e}")
        bot.send_message(message.chat.id, f"⚠️ <b>Ошибка:</b> {e}", parse_mode="HTML")

# ===== ПОКУПКИ ЗВЁЗД =====
pending_stars_orders = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_") and not call.data.startswith("buy_pay_"))
def buy_callback(call):
    try:
        if not check_subscription(call.from_user.id):
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, f"👋 <b>Для покупки подпишитесь на канал:</b>\n{CHANNEL_USERNAME}", parse_mode="HTML", reply_markup=get_sub_check_inline())
            return
        amount = int(call.data.split("_")[1])
        price = amount * STAR_RATE
        pending_stars_orders[call.from_user.id] = {"amount": amount, "price": price}
        caption = (
            f"⭐ <b>Покупка звёзд</b>\n\n"
            f"💫 Количество: {amount} звёзд\n"
            f"💵 Стоимость: {price:.0f}₽\n\n"
            f"👇 <b>Выберите способ оплаты:</b>"
        )
        bot.send_message(call.message.chat.id, caption, parse_mode="HTML", reply_markup=get_stars_pay_inline())
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"ОШИБКА buy: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "buy_pay_balance")
def buy_pay_balance(call):
    try:
        data = pending_stars_orders.get(call.from_user.id, {})
        amount = data.get("amount", 50)
        price = data.get("price", 70)
        balance = get_balance(call.from_user.id)
        if balance < price:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств на балансе!", show_alert=True)
            return
        add_balance(call.from_user.id, -price)
        order_id = add_order(call.from_user.id, amount, price, status="оплачен с баланса", payment_status="оплачен")
        username = call.from_user.username or str(call.from_user.id)
        local_order_id = int(time.time())
        result = krab_create_stars_order(username, amount, local_order_id)
        if result:
            krab_order_id = result.get("orderId") or result.get("order_id")
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET krab_order_id = %s, status = %s, payment_status = %s WHERE id = %s", (str(krab_order_id), "создан в KRAB", "ожидает оплаты в KRAB", order_id))
            conn.commit()
            cursor.close()
            conn.close()
            bot.send_message(call.message.chat.id, f"✅ <b>Заказ оплачен с баланса!</b>\n\n⭐ Звёзд: {amount}\n💸 Сумма: {price:.0f}₽\n\n<b>Заказ создан в KRAB, ожидайте зачисления.</b>", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
            log_to_channel(f"🔔 <b>Заказ звёзд (с баланса)</b>\n👤 @{username}\n⭐ {amount}\n💸 {price:.0f}₽\n🆔 KRAB: {krab_order_id}")
        else:
            process_failed_order(call.from_user.id, amount, price)
            bot.send_message(call.message.chat.id, "⚠️ <b>Не удалось создать заказ в KRAB.</b>\n\nСредства списаны, свяжитесь с поддержкой.", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"ОШИБКА buy_pay_balance: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ["buy_pay_usdt", "buy_pay_ton"])
def buy_pay_crypto(call):
    try:
        data = pending_stars_orders.get(call.from_user.id, {})
        amount = data.get("amount", 50)
        price_rub = data.get("price", 70)
        amount_usdt = round(price_rub / 90, 2)
        asset = "USDT" if call.data == "buy_pay_usdt" else "TON"
        pay_url = crypto_create_invoice(amount_usdt, f"Звёзды {amount} шт.", f"{call.from_user.id}:stars:{amount}:{price_rub}", asset=asset)
        if pay_url:
            add_order(call.from_user.id, amount, price_rub, status="ожидает оплаты", payment_status="ожидает оплаты")
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton(f"💎 Оплатить {asset}", url=pay_url))
            markup.add(types.InlineKeyboardButton("🏠 В меню", callback_data="menu_main"))
            bot.send_message(call.message.chat.id, f"🧾 <b>Заказ звёзд создан!</b>\n\n⭐ Звёзд: {amount}\n💸 Сумма: {price_rub:.0f}₽ (~{amount_usdt} USDT)\n💎 Валюта: {asset}\n\n<b>Нажми кнопку ниже для оплаты.</b>", parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "⚠️ Не удалось создать счёт. Попробуйте позже или спишите с баланса.", reply_markup=get_back_to_menu_inline())
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"ОШИБКА buy_pay_crypto: {e}")

# ===== PREMIUM =====
premium_data = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("prem_"))
def premium_callback(call):
    try:
        if call.data == "prem_self":
            bot.answer_callback_query(call.id)
            if not check_subscription(call.from_user.id):
                bot.send_message(call.message.chat.id, f"👋 <b>Для покупки подпишитесь на канал:</b>\n{CHANNEL_USERNAME}", parse_mode="HTML", reply_markup=get_sub_check_inline())
                return
            premium_data[call.from_user.id] = {"recipient": f"@{call.from_user.username or call.from_user.id}"}
            send_photo_safe(call.message.chat.id, IMG_PREMIUM, "💎 <b>Покупка Premium</b>\n\n📅 <b>Выберите срок действия премиума:</b>", get_premium_period_inline())
        elif call.data == "prem_other":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(call.message.chat.id, "💎 <b>Покупка Premium</b>\n\n👤 <b>Введите юзернейм получателя</b> (например, <code>@username</code>):", parse_mode="HTML")
            bot.register_next_step_handler(msg, process_premium_recipient)
        elif call.data == "prem_back":
            bot.answer_callback_query(call.id)
            premium_cmd(call.message)
        elif call.data.startswith("prem_") and call.data[5:].isdigit():
            months = int(call.data[5:])
            price = PREMIUM_PRICES[str(months)]
            if call.from_user.id not in premium_data:
                premium_data[call.from_user.id] = {"recipient": f"@{call.from_user.username or call.from_user.id}"}
            premium_data[call.from_user.id]["months"] = months
            premium_data[call.from_user.id]["price"] = price
            balance = get_balance(call.from_user.id)
            caption = (
                f"💎 <b>Покупка Premium</b>\n\n"
                f"👤 <b>Получатель:</b> {premium_data[call.from_user.id]['recipient']}\n\n"
                f"💵 <b>Стоимость покупки:</b> {price}₽\n"
                f"💰 <b>Текущий баланс:</b> {balance:.2f}₽\n\n"
                f"👇 <b>Выберите способ оплаты:</b>"
            )
            bot.send_message(call.message.chat.id, caption, parse_mode="HTML", reply_markup=get_premium_pay_inline())
            bot.answer_callback_query(call.id)
        elif call.data == "prem_pay_balance":
            data = premium_data.get(call.from_user.id, {})
            months = data.get("months", 3)
            price = data.get("price", PREMIUM_PRICES.get(str(months), 1200))
            recipient = data.get("recipient", f"@{call.from_user.username or call.from_user.id}")
            balance = get_balance(call.from_user.id)
            if balance < price:
                bot.answer_callback_query(call.id, "❌ Недостаточно средств на балансе!", show_alert=True)
                return
            add_balance(call.from_user.id, -price)
            order_id = add_premium_order(call.from_user.id, recipient, months, price, status="оплачен с баланса", payment_status="оплачен")
            local_order_id = int(time.time())
            result = krab_create_premium_order(recipient, months, local_order_id)
            if result:
                krab_order_id = result.get("orderId") or result.get("order_id")
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("UPDATE premium_orders SET krab_order_id = %s, status = %s, payment_status = %s WHERE id = %s", (str(krab_order_id), "создан в KRAB", "ожидает оплаты в KRAB", order_id))
                conn.commit()
                cursor.close()
                conn.close()
                bot.send_message(call.message.chat.id, f"✅ <b>Premium оплачен с баланса!</b>\n\n👤 Получатель: {recipient}\n📅 Срок: {months} мес.\n💸 Сумма: {price}₽\n\n<b>Заказ создан в KRAB, ожидайте зачисления.</b>", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
                log_to_channel(f"🔔 <b>Premium (с баланса)</b>\n👤 @{call.from_user.username or call.from_user.id}\n📅 {months} мес.\n💸 {price}₽\n🎁 {recipient}\n🆔 KRAB: {krab_order_id}")
            else:
                process_failed_order(call.from_user.id, 0, price, order_type="premium", recipient=recipient, months=months)
                bot.send_message(call.message.chat.id, "⚠️ <b>Не удалось создать заказ в KRAB.</b>\n\nСредства списаны, свяжитесь с поддержкой.", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
            bot.answer_callback_query(call.id)
        elif call.data in ["prem_pay_usdt", "prem_pay_ton"]:
            data = premium_data.get(call.from_user.id, {})
            months = data.get("months", 3)
            price_rub = data.get("price", PREMIUM_PRICES.get(str(months), 1200))
            recipient = data.get("recipient", f"@{call.from_user.username or call.from_user.id}")
            amount_usdt = round(price_rub / 90, 2)
            asset = "USDT" if call.data == "prem_pay_usdt" else "TON"
            pay_url = crypto_create_invoice(amount_usdt, f"Premium {months} мес. для {recipient}", f"{call.from_user.id}:premium:{months}:{price_rub}", asset=asset)
            if pay_url:
                add_premium_order(call.from_user.id, recipient, months, price_rub, status="ожидает оплаты", payment_status="ожидает оплаты")
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(types.InlineKeyboardButton(f"💎 Оплатить {asset}", url=pay_url))
                markup.add(types.InlineKeyboardButton("🏠 В меню", callback_data="menu_main"))
                bot.send_message(call.message.chat.id, f"🧾 <b>Заказ Premium создан!</b>\n\n👤 Получатель: {recipient}\n📅 Срок: {months} мес.\n💸 Сумма: {price_rub}₽ (~{amount_usdt} USDT)\n💎 Валюта: {asset}\n\n<b>Нажми кнопку ниже для оплаты.</b>", parse_mode="HTML", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "⚠️ Не удалось создать счёт. Попробуйте позже или спишите с баланса.", reply_markup=get_back_to_menu_inline())
            bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"ОШИБКА premium_callback: {e}")

def process_premium_recipient(message):
    try:
        recipient = message.text.strip()
        if not recipient.startswith("@"):
            recipient = "@" + recipient
        premium_data[message.from_user.id] = {"recipient": recipient}
        send_photo_safe(message.chat.id, IMG_PREMIUM, f"💎 <b>Покупка Premium</b>\n\n👤 <b>Получатель:</b> <code>{recipient}</code>\n\n📅 <b>Выберите срок действия премиума:</b>", get_premium_period_inline())
    except Exception as e:
        print(f"ОШИБКА process_premium_recipient: {e}")

# ===== INLINE МЕНЮ =====
@bot.callback_query_handler(func=lambda call: call.data in ["show_price", "show_ref", "check_sub", "menu_profile", "menu_help", "menu_pay", "menu_premium", "menu_balance", "menu_ref", "menu_promo", "menu_reviews", "menu_faq", "menu_main"])
def start_inline_callback(call):
    try:
        if call.data == "menu_main":
            caption = (
                "🌟 <b>Добро пожаловать в Defferent Shop!</b>\n\n"
                "⚡️ <b>У нас ты найдёшь Telegram Stars, Premium-подписки, а также аренду NFT-подарков, юзернеймов и анонимных номеров.</b>\n\n"
                "💎 <b>Мы не просто говорим, что мы лучшие — это подтверждают наши клиенты:</b>\n"
                "— Лучшие цены на рынке\n"
                "— Мгновенная выдача товара\n"
                "— Более 5000 довольных покупателей\n"
                "— Автоматическая доставка 24/7\n\n"
                "🛒 <b>Выбирай, что нужно, и получай сразу!</b>"
            )
            send_photo_safe(call.message.chat.id, IMG_START, caption, get_start_inline())
        elif call.data == "menu_profile":
            profile(call.message)
        elif call.data == "menu_help":
            help_command(call.message)
        elif call.data == "menu_pay":
            price_cmd(call.message)
        elif call.data == "menu_premium":
            premium_cmd(call.message)
        elif call.data == "menu_balance":
            balance(call.message)
        elif call.data == "menu_ref":
            ref_cmd(call.message)
        elif call.data == "menu_promo":
            promo_cmd(call.message)
        elif call.data == "menu_reviews":
            bot.send_message(call.message.chat.id, "⭐ <b>Оставьте отзыв:</b>\n\nНапишите текст отзыва в чат.", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
        elif call.data == "menu_faq":
            faq_cmd(call.message)
        elif call.data == "show_price":
            text = "💎 <b>Прайс-лист:</b>\n\n"
            for amount, price in PRICES:
                text += f"⭐ <b>{amount} звёзд</b> — {price:.0f}₽\n"
            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=get_price_inline())
        elif call.data == "show_ref":
            bot_username = bot.get_me().username
            link = f"https://t.me/{bot_username}?start={call.from_user.id}"
            _, _, _, ref_count = get_profile(call.from_user.id)
            bot.send_message(call.message.chat.id, f"🎁 <b>Реферальная система</b>\n\n<b>Приглашай друзей и получай {REF_BONUS}₽!</b>\n\n👥 Приглашено: {ref_count}\n\n🔗 <code>{link}</code>", parse_mode="HTML", reply_markup=get_back_to_menu_inline())
        elif call.data == "check_sub":
            if check_subscription(call.from_user.id):
                bot.send_message(call.message.chat.id, "✅ <b>Спасибо за подписку!</b>\n\nНапишите /start ещё раз.", parse_mode="HTML")
            else:
                bot.answer_callback_query(call.id, "❌ Вы ещё не подписались!", show_alert=True)
                return
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"ОШИБКА callback: {e}")

# ===== ВЕБХУК TELEGRAM =====
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_string = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route("/", methods=["GET"])
def index():
    return "Bot is running", 200

# ===== ВЕБХУК CRYPTO PAY =====
@app.route("/crypto/webhook", methods=["POST"])
def crypto_webhook():
    raw_body = request.get_data()
    signature = request.headers.get("crypto-pay-api-signature")
    secret = hashlib.sha256(CRYPTO_PAY_TOKEN.encode()).digest()
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return "Forbidden", 403
    update = request.get_json()
    if update.get("update_type") == "invoice_paid":
        invoice = update["payload"]
        payload = invoice.get("payload", "")
        parts = payload.split(":")
        if len(parts) >= 3 and parts[1] == "stars":
            user_id = int(parts[0])
            amount = int(parts[2])
            price_rub = float(parts[3]) if len(parts) > 3 else amount * STAR_RATE
            add_order(user_id, amount, price_rub, status="оплачен криптой", payment_status="оплачен")
            username = str(user_id)
            try:
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                if row and row["username"]:
                    username = row["username"]
            except:
                pass
            local_order_id = int(time.time())
            result = krab_create_stars_order(username, amount, local_order_id)
            if result:
                krab_order_id = result.get("orderId") or result.get("order_id")
                add_order(user_id, amount, price_rub, status="создан в KRAB", krab_order_id=str(krab_order_id), payment_status="ожидает оплаты в KRAB")
                try:
                    bot.send_message(user_id, f"✅ <b>Оплата прошла!</b>\n\n⭐ Звёзд: {amount}\n💸 Сумма: {price_rub:.0f}₽\n\n<b>Заказ создан в KRAB, ожидайте зачисления.</b>", parse_mode="HTML")
                except:
                    pass
                log_to_channel(f"🔔 <b>Оплата звёзд криптой</b>\n👤 @{username}\n⭐ {amount}\n💸 {price_rub:.0f}₽\n🆔 KRAB: {krab_order_id}")
            else:
                process_failed_order(user_id, amount, price_rub)
        elif len(parts) >= 3 and parts[1] == "premium":
            user_id = int(parts[0])
            months = int(parts[2])
            price_rub = float(parts[3]) if len(parts) > 3 else PREMIUM_PRICES.get(str(months), 1200)
            recipient = f"@{user_id}"
            try:
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM users WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                if row and row["username"]:
                    recipient = f"@{row['username']}"
            except:
                pass
            local_order_id = int(time.time())
            result = krab_create_premium_order(recipient, months, local_order_id)
            if result:
                krab_order_id = result.get("orderId") or result.get("order_id")
                add_premium_order(user_id, recipient, months, price_rub, status="создан в KRAB", krab_order_id=str(krab_order_id), payment_status="ожидает оплаты в KRAB")
                try:
                    bot.send_message(user_id, f"✅ <b>Оплата Premium прошла успешно!</b>\n\n📅 Срок: {months} мес.\n💸 Сумма: {price_rub}₽\n\n<b>Заказ создан в KRAB, ожидайте зачисления.</b>", parse_mode="HTML")
                except:
                    pass
                log_to_channel(f"🔔 <b>Premium криптой</b>\n🆔 ID: <code>{user_id}</code>\n📅 {months} мес.\n💸 {price_rub}₽\n🆔 KRAB: {krab_order_id}")
            else:
                process_failed_order(user_id, 0, price_rub, order_type="premium", recipient=recipient, months=months)
    return "OK", 200

# ===== ВЕБХУК KRAB =====
@app.route("/krab/webhook", methods=["POST"])
def krab_webhook():
    raw_body = request.get_data()
    signature = request.headers.get("X-Signature") or request.headers.get("x-signature")
    expected = hmac.new(KRAB_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    if signature and not hmac.compare_digest(signature, expected):
        return "Forbidden", 403
    update = request.get_json()
    if not update:
        return "OK", 200
    order_id = str(update.get("orderId") or update.get("order_id"))
    status = update.get("status")
    order_type = update.get("type")
    if order_type == "stars":
        row = get_order_by_krab_id(order_id)
        if row:
            user_id, amount, price = row
            if status in ["completed", "success", "done"]:
                update_order_status(user_id, order_id, "выполнен", "выполнен")
                try:
                    bot.send_message(user_id, f"🎉 <b>Звёзды зачислены!</b>\n\n⭐ Количество: {amount}\n\n<b>Спасибо за покупку!</b>", parse_mode="HTML")
                except:
                    pass
                log_to_channel(f"✅ <b>Заказ звёзд выполнен</b>\n🆔 {order_id}\n👤 ID: <code>{user_id}</code>\n⭐ {amount} звёзд")
    elif order_type == "premium":
        row = get_premium_by_krab_id(order_id)
        if row:
            user_id, recipient, months, price = row
            if status in ["completed", "success", "done"]:
                update_premium_status(user_id, order_id, "выполнен", "выполнен")
                try:
                    bot.send_message(user_id, f"🎉 <b>Premium зачислен!</b>\n\n👤 Получатель: {recipient}\n📅 Срок: {months} мес.\n\n<b>Спасибо за покупку!</b>", parse_mode="HTML")
                except:
                    pass
                log_to_channel(f"✅ <b>Premium выполнен</b>\n🆔 {order_id}\n👤 ID: <code>{user_id}</code>\n📅 {months} мес.")
    return "OK", 200

# ===== ЗАПУСК =====
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8080))
    print("Бот запущен...")
    app.run(host="0.0.0.0", port=port)
