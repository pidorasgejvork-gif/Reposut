import os
import telebot
from telebot import types
from flask import Flask, request
import sqlite3
from datetime import datetime
import csv
import io

# ===== НАСТРОЙКИ =====
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
SUPPORT_USERNAME = "coo_vernost"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
REF_BONUS = 10  # бонус за приглашённого (₽)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ===== ПРАЙС =====
PRICES = [
    (50, 50 * 1.35),
    (100, 100 * 1.35),
    (150, 150 * 1.35),
    (250, 250 * 1.35),
    (500, 500 * 1.35),
    (1000, 1000 * 1.35),
    (2500, 2500 * 1.35),
    (5000, 5000 * 1.35),
]

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            total_spent REAL DEFAULT 0,
            total_purchases INTEGER DEFAULT 0,
            referrer_id INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY,
            discount INTEGER,
            uses_left INTEGER
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

def get_profile(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT balance, total_spent, total_purchases, ref_count FROM users WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2], row[3]
    return 0, 0, 0, 0

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

def update_purchase(user_id, price):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users SET total_spent = total_spent + ?, total_purchases = total_purchases + 1
        WHERE user_id = ?
    """, (price, user_id))
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
    cursor.execute("SELECT COALESCE(SUM(price), 0) FROM orders")
    total_money = cursor.fetchone()[0]
    conn.close()
    return users_count, orders_count, stars_sold, total_money

def set_referrer(user_id, referrer_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] == 0 and user_id != referrer_id:
        cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, user_id))
        cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (referrer_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_user_by_username(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row

def ban_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] == 1 if row else False

def get_all_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# ===== КЛАВИАТУРЫ =====
def get_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👤 Профиль"), types.KeyboardButton("❓ Помощь"))
    markup.add(types.KeyboardButton("⭐ Купить звёзды"), types.KeyboardButton("💰 Баланс"))
    markup.add(types.KeyboardButton("💎 Прайс"), types.KeyboardButton("🎁 Рефералы"))
    markup.add(types.KeyboardButton("🛠 Тех поддержка"))
    return markup

def get_support_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}"
    ))
    return markup

def get_price_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    for amount, price in PRICES:
        markup.add(types.InlineKeyboardButton(
            f"⭐ {amount} — {price:.0f}₽", callback_data=f"buy_{amount}"
        ))
    return markup

# ===== КОМАНДЫ =====
@bot.message_handler(commands=['start'])
def start(message):
    if is_banned(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 Вы забанены.")
        return

    args = message.text.split()
    add_user(message.from_user.id, message.from_user.username or "без_ника")

    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if set_referrer(message.from_user.id, referrer_id):
                try:
                    bot.send_message(referrer_id, f"🎉 По вашей ссылке пришёл новый пользователь! +{REF_BONUS}₽ на баланс.")
                except:
                    pass
        except:
            pass

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
        "👤 Профиль — ваш профиль и статистика\n"
        "💎 Прайс — цены на звёзды\n"
        "⭐ Купить звёзды — оформить покупку\n"
        "💰 Баланс — проверить счёт\n"
        "🎁 Рефералы — пригласить друзей и получить бонус\n"
        "🛠 Тех поддержка — связаться с нами",
        reply_markup=get_keyboard()
    )

@bot.message_handler(commands=['price'])
def price_cmd(message):
    text = "💎 Прайс-лист:\n\n"
    for amount, price in PRICES:
        text += f"⭐ {amount} звёзд — {price:.0f}₽\n"
    text += "\nВыберите количество для покупки:"
    bot.send_message(message.chat.id, text, reply_markup=get_price_inline())

@bot.message_handler(commands=['pay'])
def pay(message):
    price_cmd(message)

@bot.message_handler(commands=['balance'])
def balance(message):
    bal = get_balance(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"💰 Ваш баланс: {bal:.2f}₽.",
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

@bot.message_handler(commands=['profile'])
def profile(message):
    user_id = message.from_user.id
    add_user(user_id, message.from_user.username or "без_ника")
    balance, total_spent, total_purchases, ref_count = get_profile(user_id)

    caption = (
        f"👤 Профиль\n\n"
        f"🆔 ID: {user_id}\n\n"
        f"💰 Баланс: {balance:.2f}₽\n"
        f"💸 Сумма покупок: {total_spent:.2f}₽\n"
        f"🛒 Количество покупок: {total_purchases}\n"
        f"🎁 Приглашено: {ref_count}"
    )

    bot.send_photo(
        message.chat.id,
        photo="https://i.postimg.cc/bJ0HSdtd/Screenshot-20261012-205847-com-lemon-lvoverseas-Edit-Activity.jpg",
        caption=caption,
        reply_markup=get_keyboard()
    )

@bot.message_handler(commands=['ref'])
def ref_cmd(message):
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    _, _, _, ref_count = get_profile(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"🎁 Реферальная система\n\n"
        f"Приглашай друзей и получай {REF_BONUS}₽ за каждого!\n\n"
        f"👥 Приглашено: {ref_count}\n\n"
        f"🔗 Ваша ссылка:\n{link}",
        reply_markup=get_keyboard()
    )

# ===== АДМИН-КОМАНДЫ =====
@bot.message_handler(commands=['give'])
def give(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, user_id, amount = message.text.split()
        add_balance(int(user_id), float(amount))
        bot.send_message(message.chat.id, f"✅ Начислено {amount}₽ пользователю {user_id}")
        try:
            bot.send_message(int(user_id), f"🎉 Вам начислено {amount}₽!")
        except:
            pass
    except:
        bot.send_message(message.chat.id, "Формат: /give ID СУММА")

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    users_count, orders_count, stars_sold, total_money = get_stats()
    bot.send_message(
        message.chat.id,
        f"📊 Статистика:\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"🧾 Заказов: {orders_count}\n"
        f"⭐ Продано звёзд: {stars_sold}\n"
        f"💰 Заработано: {total_money:.2f}₽"
    )

@bot.message_handler(commands=['users'])
def users_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, total_spent FROM users ORDER BY created_at DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        bot.send_message(message.chat.id, "Пользователей нет.")
        return
    text = "👥 Последние 50 пользователей:\n\n"
    for uid, uname, bal, spent in rows:
        text += f"ID: {uid} | @{uname} | {bal:.2f}₽ | куплено: {spent:.2f}₽\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['find'])
def find_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, username = message.text.split()
        username = username.replace("@", "")
        row = get_user_by_username(username)
        if row:
            bot.send_message(message.chat.id, f"ID: {row[0]}\nНик: @{row[1]}\nБаланс: {row[2]:.2f}₽")
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
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        bot.send_message(message.chat.id, "Формат: /broadcast текст")
        return
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            bot.send_message(uid, text)
            sent += 1
        except:
            pass
    bot.send_message(message.chat.id, f"✅ Отправлено {sent} из {len(users)}")

@bot.message_handler(commands=['export'])
def export_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, total_spent, total_purchases, ref_count FROM users")
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "username", "balance", "total_spent", "total_purchases", "ref_count"])
    writer.writerows(rows)

    output.seek(0)
    bot.send_document(message.chat.id, ("users.csv", output.getvalue().encode("utf-8")))

@bot.message_handler(commands=['orders'])
def orders_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, amount, price, status, created_at FROM orders ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        bot.send_message(message.chat.id, "Заказов нет.")
        return
    text = "🧾 Последние 20 заказов:\n\n"
    for oid, uid, amount, price, status, created_at in rows:
        text += f"#{oid} | {uid} | {amount}⭐ | {price}₽ | {status} | {created_at}\n"
    bot.send_message(message.chat.id, text)

# ===== ОБРАБОТКА КНОПОК =====
@bot.message_handler(content_types=['text'])
def handle_buttons(message):
    text = message.text
    add_user(message.from_user.id, message.from_user.username or "без_ника")

    if text == "👤 Профиль":
        profile(message)
    elif text == "❓ Помощь":
        help_command(message)
    elif text == "⭐ Купить звёзды":
        pay(message)
    elif text == "💰 Баланс":
        balance(message)
    elif text == "💎 Прайс":
        price_cmd(message)
    elif text == "🎁 Рефералы":
        ref_cmd(message)
    elif text == "🛠 Тех поддержка":
        tp(message)
    else:
        bot.send_message(
            message.chat.id,
            f"Не знаю такой команды: {text}\nВоспользуйся кнопками ниже.",
            reply_markup=get_keyboard()
        )

# ===== ОБРАБОТКА ПОКУПОК =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_callback(call):
    amount = int(call.data.split("_")[1])
    price = amount * 1.35
    add_order(call.from_user.id, amount, price)
    update_purchase(call.from_user.id, price)

    bot.send_message(
        call.message.chat.id,
        f"🧾 Заказ создан!\n\n"
        f"⭐ Звёзд: {amount}\n"
        f"💸 Сумма: {price:.2f}₽\n\n"
        f"Оплата пока в разработке. Скоро подключим официальные Telegram Stars."
    )
    bot.answer_callback_query(call.id)

    try:
        bot.send_message(
            ADMIN_ID,
            f"🔔 Новый заказ!\n\n"
            f"👤 @{call.from_user.username or call.from_user.id}\n"
            f"🆔 ID: {call.from_user.id}\n"
            f"⭐ Звёзд: {amount}\n"
            f"💸 Сумма: {price:.2f}₽"
        )
    except:
        pass

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
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8080))

    try:
        bot.remove_webhook()
        bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
        print(f"Вебхук установлен: {WEBHOOK_URL}/{TOKEN}")
    except Exception as e:
        print(f"Ошибка установки вебхука: {e}")

    app.run(host="0.0.0.0", port=port)
