import telebot
from telebot import types
from flask import Flask, request
import sqlite3
from datetime import datetime

# ===== НАСТРОЙКИ =====
TOKEN = "8828538265:AAFc7ZpB4o3eduUyNrQTozXgujzSpYRKvt0"
ADMIN_ID = 7621775709
SUPPORT_USERNAME = "coo_vernost"

# Адрес туннеля (без слэша в конце), например https://abc.ngrok.io
WEBHOOK_URL = "https://ТВОЙ_ТУННЕЛЬ"

bot = telebot.TeleBot(TOKEN)
app = Flask(name)

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            price REAL,
            status TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, balance, created_at)
        VALUES (?, ?, 0, ?)
        ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
    """, (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def add_balance(user_id, amount):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, balance, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
    """, (user_id, "без_ника", amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), amount))
    conn.commit()
    conn.close()

def add_order(user_id, amount, price, status="новый"):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, amount, price, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, amount, price, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders")
    orders_count = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM orders")
    stars_sold = cursor.fetchone()[0]
    conn.close()
    return users_count, orders_count, stars_sold

# ===== КЛАВИАТУРЫ =====
def get_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("❓ Помощь"))
    markup.add(types.KeyboardButton("⭐ Купить звёзды"), types.KeyboardButton("💰 Баланс"))
    markup.add(types.KeyboardButton("🛠 Тех поддержка"))
    return markup

def get_support_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}"
    ))
    return markup

# ===== КОМАНДЫ =====
@bot.message_handler(commands=['start'])
def start(message):
    add_user(message.from_user.id, message.from_user.username or "без_ника")
    bot.send_message(
        message.chat.id,
        "Приветствуем вас в Different Shop! ⭐\n\n"
        "Давно искали звёзды по курсу ниже рынка?\n"
        "Этот бот создан именно для вас — зачисляем звёзды за считанные секунды.",
        reply_markup=get_keyboard()
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📖 Помощь:\n\n"
        "⭐ Купить звёзды — оформить покупку\n"
        "💰 Баланс — проверить счёт\n"
        "🛠 Тех поддержка — связаться с нами\n\n"
        "Если что-то пошло не так — напиши в поддержку.",
        reply_markup=get_keyboard()
    )

@bot.message_handler(commands=['pay'])
def pay(message):
    bot.send_message(
        message.chat.id,
        "⭐ Здесь будет оплата звёзд.\n"
        "Скоро подключим официальную оплату через Telegram Stars.",
        reply_markup=get_keyboard()
    )

@bot.message_handler(commands=['balance'])
def balance(message):
    bal = get_balance(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"💰 Ваш баланс: {bal} звёзд.",
        reply_markup=get_keyboard()
    )

@bot.message_handler(commands=['tp'])
def tp(message):
    bot.send_message(
        message.chat.id,
        "🛠 Тех поддержка\nНажми кнопку ниже, чтобы написать нам:",
        reply_markup=get_support_inline()
    )
    bot.send_message(message.chat.id, "Возвращаемся в меню:", reply_markup=get_keyboard())

@bot.message_handler(commands=['give'])
def give(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, user_id, amount = message.text.split()
        add_balance(int(user_id), int(amount))
        bot.send_message(message.chat.id, f"✅ Начислено {amount} звёзд пользователю {user_id}")
        try:
            bot.send_message(int(user_id), f"🎉 Вам начислено {amount} звёзд!")
        except:
            pass
    except:
        bot.send_message(message.chat.id, "Формат: /give ID СУММА")

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    users_count, orders_count, stars_sold = get_stats()
    bot.send_message(
        message.chat.id,
        f"📊 Статистика:\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"🧾 Заказов: {orders_count}\n"
        f"⭐ Продано звёзд: {stars_sold}"
    )

@bot.message_handler(commands=['order'])
def order(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, user_id, amount, price = message.text.split()
        add_order(int(user_id), int(amount), float(price))
        bot.send_message(message.chat.id, f"✅ Заказ создан: {amount} звёзд за {price}")
    except:
        bot.send_message(message.chat.id, "Формат: /order ID КОЛИЧЕСТВО ЦЕНА")

@bot.message_handler(content_types=['text'])
def handle_buttons(message):
    text = message.text
    add_user(message.from_user.id, message.from_user.username or "без_ника")

    if text == "❓ Помощь":
        help_command(message)
    elif text == "⭐ Купить звёзды":
        pay(message)
    elif text == "💰 Баланс":
        balance(message)
    elif text == "🛠 Тех поддержка":
        tp(message)
    else:
        bot.send_message(
            message.chat.id,
            f"Не знаю такой команды: {text}\nВоспользуйся кнопками ниже.",
            reply_markup=get_keyboard()
        )

# ===== ВЕБХУК =====
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

# ===== ЗАПУСК =====
if name == "main":
    init_db()
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    print(f"Вебхук установлен: {WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=8080)
