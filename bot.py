import os
import telebot
from telebot import types
from flask import Flask, request
import sqlite3
from datetime import datetime
import csv
import io
import threading
import time

# ===== НАСТРОЙКИ =====
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
SUPPORT_USERNAME = "coo_vernost"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
CHANNEL_USERNAME = "@defferent_shop"
REF_BONUS = 10

IMG_START = "https://i.postimg.cc/0yPd3jn9/Screenshot-20261012-231702-com-lemon-lvoverseas-Edit-Activity.jpg"
IMG_PROFILE = "https://i.postimg.cc/bJ0HSdtd/Screenshot-20261012-205847-com-lemon-lvoverseas-Edit-Activity.jpg"
IMG_PRICE = "https://i.postimg.cc/1RDFQPfC/Screenshot-20261012-232337-com-lemon-lvoverseas-Edit-Activity.jpg"
IMG_HELP = "https://i.postimg.cc/qMd8hq9c/Screenshot-20261012-232832-com-lemon-lvoverseas-Edit-Activity.jpg"
IMG_REF = "https://i.postimg.cc/pXWX9tLP/Screenshot-20261013-024508-com-lemon-lvoverseas-Edit-Activity.jpg"
IMG_PROMO = "https://i.postimg.cc/Dy2S3X9t/Screenshot-20261013-015351-com-lemon-lvoverseas-Edit-Activity.jpg"
IMG_ADMIN = "https://i.postimg.cc/RhvZmkDw/Screenshot-20261013-015539-com-lemon-lvoverseas-Edit-Activity.jpg"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

PRICES = [
    (50, 50 * 1.35), (100, 100 * 1.35), (150, 150 * 1.35), (250, 250 * 1.35),
    (500, 500 * 1.35), (1000, 1000 * 1.35), (2500, 2500 * 1.35), (5000, 5000 * 1.35),
]

# ===== БАЗА =====
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
            user_id INTEGER, amount INTEGER, price REAL, status TEXT, created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, discount INTEGER, uses_left INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, text TEXT, created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, balance, created_at) VALUES (?, ?, 0, ?)
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
    cursor.execute("SELECT balance, total_spent, total_purchases, ref_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, 0, 0, 0)

def add_balance(user_id, amount):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, balance, created_at) VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
    """, (user_id, "без_ника", amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), amount))
    conn.commit()
    conn.close()

def add_order(user_id, amount, price, status="новый"):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, amount, price, status, created_at) VALUES (?, ?, ?, ?, ?)
    """, (user_id, amount, price, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def update_purchase(user_id, price):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_spent = total_spent + ?, total_purchases = total_purchases + 1 WHERE user_id = ?", (price, user_id))
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

def add_promo(code, discount, uses_left):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO promos (code, discount, uses_left) VALUES (?, ?, ?)", (code, discount, uses_left))
    conn.commit()
    conn.close()

def use_promo(code):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT discount, uses_left FROM promos WHERE code = ?", (code,))
    row = cursor.fetchone()
    if row and row[1] > 0:
        cursor.execute("UPDATE promos SET uses_left = uses_left - 1 WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return row[0]
    conn.close()
    return None

def add_review(user_id, text):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO reviews (user_id, text, created_at) VALUES (?, ?, ?)", (user_id, text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===== КЛАВИАТУРЫ =====
def get_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("👤 Профиль"), types.KeyboardButton("❓ Помощь"))
    markup.add(types.KeyboardButton("⭐ Купить звёзды"), types.KeyboardButton("💰 Баланс"))
    markup.add(types.KeyboardButton("💎 Прайс"), types.KeyboardButton("🎁 Рефералы"))
    markup.add(types.KeyboardButton("🎟 Промокод"), types.KeyboardButton("⭐ Отзывы"))
    markup.add(types.KeyboardButton("🛠 Тех поддержка"))
    return markup

def get_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📊 Статистика"), types.KeyboardButton("👥 Пользователи"))
    markup.add(types.KeyboardButton("🧾 Заказы"), types.KeyboardButton("📢 Рассылка"))
    markup.add(types.KeyboardButton("🎟 Создать промокод"), types.KeyboardButton("📤 Экспорт"))
    markup.add(types.KeyboardButton("🏠 В меню"))
    return markup

def get_support_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💬 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}"))
    return markup

def get_price_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    for amount, price in PRICES:
        markup.add(types.InlineKeyboardButton(f"⭐ {amount} — {price:.0f}₽", callback_data=f"buy_{amount}"))
    return markup

def get_start_inline():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("💎 Прайс", callback_data="show_price"), types.InlineKeyboardButton("🎁 Рефералы", callback_data="show_ref"))
    markup.add(types.InlineKeyboardButton("🛠 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}"))
    return markup

def get_sub_check_inline():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"))
    markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
    return markup

def send_typing(chat_id):
    try:
        bot.send_chat_action(chat_id, "typing")
    except:
        pass

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

        if not check_subscription(message.from_user.id):
            send_typing(message.chat.id)
            bot.send_message(
                message.chat.id,
                f"👋 <b>Для использования бота подпишитесь на канал:</b>\n{CHANNEL_USERNAME}",
                parse_mode="HTML",
                reply_markup=get_sub_check_inline()
            )
            return

        caption = (
            "🌟 <b>Добро пожаловать в Different Shop!</b> 🌟\n\n"
            "⭐ <b>Мы продаём звёзды Telegram</b> по курсу ниже рынка.\n"
            "⚡ <b>Зачисление — за считанные секунды.</b>\n"
            "💎 <b>Более 5000 довольных клиентов.</b>\n\n"
            "👇 <b>Выбери действие на клавиатуре ниже:</b>"
        )
        send_typing(message.chat.id)
        bot.send_photo(message.chat.id, photo=IMG_START, caption=caption, parse_mode="HTML", reply_markup=get_keyboard())
        bot.send_message(message.chat.id, "⚡ <b>Быстрый доступ:</b>", parse_mode="HTML", reply_markup=get_start_inline())

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
            "💰 <b>Баланс</b> — проверить счёт\n"
            "🎁 <b>Рефералы</b> — пригласить друзей\n"
            "🎟 <b>Промокод</b> — активировать скидку\n"
            "🛠 <b>Тех поддержка</b> — связаться с нами"
        )
        bot.send_photo(message.chat.id, photo=IMG_HELP, caption=caption, parse_mode="HTML", reply_markup=get_keyboard())
    except Exception as e:
        print(f"ОШИБКА help: {e}")

@bot.message_handler(commands=['price'])
def price_cmd(message):
    try:
        send_typing(message.chat.id)
        text = "💎 <b>Прайс-лист:</b>\n\n"
        for amount, price in PRICES:
            text += f"⭐ <b>{amount} звёзд</b> — {price:.0f}₽\n"
        text += "\n<b>Выберите количество для покупки:</b>"
        bot.send_photo(message.chat.id, photo=IMG_PRICE, caption=text, parse_mode="HTML", reply_markup=get_price_inline())
    except Exception as e:
        print(f"ОШИБКА price: {e}")

@bot.message_handler(commands=['pay'])
def pay(message):
    price_cmd(message)

@bot.message_handler(commands=['balance'])
def balance(message):
    try:
        send_typing(message.chat.id)
        bal = get_balance(message.from_user.id)
        bot.send_message(message.chat.id, f"💰 <b>Ваш баланс:</b> {bal:.2f}₽.", parse_mode="HTML", reply_markup=get_keyboard())
    except Exception as e:
        print(f"ОШИБКА balance: {e}")

@bot.message_handler(commands=['tp'])
def tp(message):
    try:
        bot.send_message(message.chat.id, "🛠 <b>Тех поддержка</b>\nНажми кнопку ниже:", parse_mode="HTML", reply_markup=get_support_inline())
        bot.send_message(message.chat.id, "Возвращаемся в меню:", reply_markup=get_keyboard())
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
        bot.send_photo(message.chat.id, photo=IMG_PROFILE, caption=caption, parse_mode="HTML", reply_markup=get_keyboard())
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
        bot.send_photo(message.chat.id, photo=IMG_REF, caption=caption, parse_mode="HTML", reply_markup=get_keyboard())
    except Exception as e:
        print(f"ОШИБКА ref: {e}")

@bot.message_handler(commands=['promo'])
def promo_cmd(message):
    try:
        send_typing(message.chat.id)
        bot.send_message(message.chat.id, "🎟 <b>Введите промокод:</b>\n\nНапример: <code>/promo SALE10</code>", parse_mode="HTML")
    except Exception as e:
        print(f"ОШИБКА promo: {e}")

@bot.message_handler(commands=['myorders'])
def myorders_cmd(message):
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, amount, price, status, created_at FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (message.from_user.id,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "🧾 <b>У вас пока нет заказов.</b>", parse_mode="HTML")
            return
        text = "🧾 <b>Ваши последние заказы:</b>\n\n"
        for oid, amount, price, status, created_at in rows:
            text += f"#{oid} | {amount}⭐ | {price}₽ | {status} | {created_at}\n"
        bot.send_message(message.chat.id, text, parse_mode="HTML")
    except Exception as e:
        print(f"ОШИБКА myorders: {e}")

# ===== АДМИН =====
@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        bot.send_message(message.chat.id, "🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
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
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, balance, total_spent FROM users ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "Пользователей нет.")
            return
        text = "👥 <b>Последние 50 пользователей:</b>\n\n"
        for uid, uname, bal, spent in rows:
            text += f"ID: <code>{uid}</code> | @{uname} | {bal:.2f}₽ | куплено: {spent:.2f}₽\n"
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
            bot.send_message(message.chat.id, f"ID: <code>{row[0]}</code>\nНик: @{row[1]}\nБаланс: {row[2]:.2f}₽", parse_mode="HTML")
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
    except Exception as e:
        print(f"ОШИБКА export: {e}")

@bot.message_handler(commands=['orders'])
def orders_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, amount, price, status, created_at FROM orders ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.send_message(message.chat.id, "Заказов нет.")
            return
        text = "🧾 <b>Последние 20 заказов:</b>\n\n"
        for oid, uid, amount, price, status, created_at in rows:
            text += f"#{oid} | {uid} | {amount}⭐ | {price}₽ | {status} | {created_at}\n"
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
                    bot.send_message(message.chat.id, f"🎟 <b>Промокод активирован!</b>\nСкидка: {discount}%", parse_mode="HTML")
                else:
                    bot.send_message(message.chat.id, "❌ <b>Промокод не найден или закончился.</b>", parse_mode="HTML")
            except:
                bot.send_message(message.chat.id, "Формат: /promo КОД")
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
        elif text == "💰 Баланс":
            balance(message)
        elif text == "💎 Прайс":
            price_cmd(message)
        elif text == "🎁 Рефералы":
            ref_cmd(message)
        elif text == "🎟 Промокод":
            promo_cmd(message)
        elif text == "⭐ Отзывы":
            bot.send_message(message.chat.id, "⭐ <b>Оставьте отзыв:</b>\n\nНапишите текст отзыва в чат.", parse_mode="HTML")
        elif text == "🛠 Тех поддержка":
            tp(message)
        else:
            if len(text) > 10 and not text.startswith("/"):
                add_review(message.from_user.id, text)
                bot.send_message(message.chat.id, "⭐ <b>Спасибо за отзыв!</b>", parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, f"Не знаю такой команды: {text}\nВоспользуйся кнопками ниже.", reply_markup=get_keyboard())

    except Exception as e:
        print(f"ОШИБКА handle_buttons: {e}")
        bot.send_message(message.chat.id, f"⚠️ <b>Ошибка:</b> {e}", parse_mode="HTML")

# ===== ПОКУПКИ =====
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_callback(call):
    try:
        amount = int(call.data.split("_")[1])
        price = amount * 1.35
        add_order(call.from_user.id, amount, price)
        update_purchase(call.from_user.id, price)
        bot.send_message(call.message.chat.id, f"🧾 <b>Заказ создан!</b>\n\n⭐ Звёзд: {amount}\n💸 Сумма: {price:.2f}₽\n\n<b>Оплата пока в разработке.</b>", parse_mode="HTML")
        bot.answer_callback_query(call.id)
        try:
            bot.send_message(ADMIN_ID, f"🔔 <b>Новый заказ!</b>\n\n👤 @{call.from_user.username or call.from_user.id}\n🆔 ID: <code>{call.from_user.id}</code>\n⭐ Звёзд: {amount}\n💸 Сумма: {price:.2f}₽", parse_mode="HTML")
        except:
            pass
    except Exception as e:
        print(f"ОШИБКА buy: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ["show_price", "show_ref", "check_sub"])
def start_inline_callback(call):
    try:
        if call.data == "show_price":
            text = "💎 <b>Прайс-лист:</b>\n\n"
            for amount, price in PRICES:
                text += f"⭐ <b>{amount} звёзд</b> — {price:.0f}₽\n"
            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=get_price_inline())
        elif call.data == "show_ref":
            bot_username = bot.get_me().username
            link = f"https://t.me/{bot_username}?start={call.from_user.id}"
            _, _, _, ref_count = get_profile(call.from_user.id)
            bot.send_message(call.message.chat.id, f"🎁 <b>Реферальная система</b>\n\n<b>Приглашай друзей и получай {REF_BONUS}₽!</b>\n\n👥 Приглашено: {ref_count}\n\n🔗 <code>{link}</code>", parse_mode="HTML")
        elif call.data == "check_sub":
            if check_subscription(call.from_user.id):
                bot.send_message(call.message.chat.id, "✅ <b>Спасибо за подписку!</b>\n\nНапишите /start ещё раз.", parse_mode="HTML")
            else:
                bot.answer_callback_query(call.id, "❌ Вы ещё не подписались!", show_alert=True)
                return
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"ОШИБКА callback: {e}")

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
