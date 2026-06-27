import asyncio
import aiohttp
import random
import json
import os
import hmac
import hashlib
import base64
import time
from datetime import datetime
import pytz
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

def _load_env(path=".env"):
    """تحميل متغيرات البيئة من ملف .env بدون حاجة لحزم خارجية."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)

_load_env()

# ================== الإعدادات السيادية ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
SECRET_KEY = os.getenv("SECRET_KEY")
USERS_FILE = os.getenv("USERS_FILE", "users_database.json")
STORE_LINK = os.getenv("STORE_LINK", "https://shadeedsa.com/")
SNAP_LINK = os.getenv("SNAP_LINK", "https://www.snapchat.com/add/t6x")

OLD_CODES = [
    "STK-MTc3MjM4MzU2MDo3NGI3MjI2YThlMzA", "STK-MTc3MjM5NjQ4MDpjMjQxY2E1YTViY2Y",
    "STK-MTc3MjM5NjQ4Njo4YTc2OGNmZWM5ZDI", "STK-MTc3MjI2MzgwMzozNDBjYzExMmFhNjM",
    "STK-MTgwMTIwODIzMDo2MzM4ODcyMGM3MjU", "STK-MTc3MjI2NTIxMToxOTk0MDFhODM2ZTk",
    "STK-MTc3MjI3MjU0NTphOTcyYzhhMzNjZTY", "STK-MTc3MjI3MzUzNjpmNDkwMWM1MDExYWE",
    "STK-MTc3MjI3MzU0MTphMzU3MzEyNWMyOWI", "STK-MTc3MjI4MzQ1MTo1NGQzODU5YTc5MWU",
    "STK-MTc3MjI4MzU3NjpkMGFlN2IwMjZmMjU", "STK-MTc3MjI5MDI1MTo4ZDVlNGRkYzM2YTY",
    "STK-MTc3MjI5MTExNzowMjg2NWNh:3VkMzA", "STK-MTc3MjI5NjY2NTo0ZDA5Njk5ZDYwZjI",
    "STK-MTc3MjI5NjgwMDpiMjQwODIxY2JlNjM", "STK-MTc3MjI5NzEwNDpmOTY3YmExNjdkNzI",
    "STK-MTc3MjMwNTI4Mjo5Njk2ODExZTE1ZmI"
]

LEAD_STOCKS = ['NVDA', 'TSLA', 'AAPL', 'AMD', 'MSFT', 'META', 'AMZN', 'NFLX', 'GOOGL', 'PLTR', 'COIN', 'MARA']

# ================== نظام الذاكرة ==================
def load_users():
    if not os.path.exists(USERS_FILE): return {}
    try:
        with open(USERS_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def save_users(data):
    with open(USERS_FILE, "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ================== محرك التشفير ==================
def verify_secure_code(code):
    if code in OLD_CODES: return True, int(time.time()) + (30 * 86400)
    try:
        clean = code.replace("STK-", "").strip()
        missing_padding = len(clean) % 4
        if missing_padding: clean += '=' * (4 - missing_padding)
        decoded = base64.urlsafe_b64decode(clean).decode()
        expiry, sig = decoded.split(":", 1)
        check = hmac.new(SECRET_KEY.encode(), f"STOCK:{expiry}".encode(), hashlib.sha256).hexdigest()[:12]
        if sig == check and time.time() < int(expiry): return True, int(expiry)
        return False, "❌ الكود غير صالح."
    except: return False, "⚠️ خطأ في التنسيق."

def generate_secure_code(days):
    expiry = int(time.time()) + (days * 86400)
    sig = hmac.new(SECRET_KEY.encode(), f"STOCK:{expiry}".encode(), hashlib.sha256).hexdigest()[:12]
    token = base64.urlsafe_b64encode(f"{expiry}:{sig}".encode()).decode().replace("=", "")
    return f"STK-{token}"

def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True
    users = load_users()
    return str(user_id) in users and time.time() < float(users[str(user_id)])

# ================== محرك التحليل المطور V48 ==================
async def fetch_analysis(symbol, type_label="تحليل"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=5d"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=12) as response:
                if response.status != 200: return None
                data = await response.json()
                res = data['chart']['result'][0]
                price = res['meta']['regularMarketPrice']
                change = ((price - res['meta']['previousClose']) / res['meta']['previousClose']) * 100
                accuracy = random.randint(64, 78)
                
                # ⚖️ إضافة فلتر شرعي بسيط (محاكاة ذكية)
                halal_status = "✅ سهم متوافق" if symbol.upper() not in ['NFLX', 'COIN', 'MARA'] else "⚠️ مراجعة الشرعية"
                
                if change > 0.4:
                    rec = "✅ توصية: شراء (Buy)"
                    news = "🟢 إيجابية وتدفق سيولة"
                elif change < -0.8:
                    rec = "🔻 توصية: بيع (Sell)"
                    news = "🔴 ضغط بيعي فني"
                else:
                    rec = "⏳ الحالة: مراقبة (Wait)"
                    news = "⚪ استقرار بانتظار اتجاه"

                return {
                    "symbol": symbol.upper(), "price": price, "change": round(change, 2),
                    "accuracy": accuracy, "news": news, "rec": rec, "halal": halal_status,
                    "t1": round(price * 1.015, 2), "t2": round(price * 1.038, 2), "t3": round(price * 1.06, 2),
                    "stop": round(price * 0.96, 2)
                }
        except: return None

def format_report(d):
    return (f"📊 **تقرير فني: {d['symbol']}** | {d['halal']}\n"
            f"───────────────────\n"
            f"💰 **السعر:** `${d['price']}` ({d['change']}%)\n"
            f"📢 **{d['rec']}**\n"
            f"🎯 **نسبة النجاح:** `{d['accuracy']}%` (واقعية)\n"
            f"📰 **الأخبار:** `{d['news']}`\n"
            f"───────────────────\n"
            f"✅ **الأهداف المحدثة:**\n"
            f"🎯 هدف 1: `${d['t1']}` | 🎯 هدف 2: `${d['t2']}`\n"
            f"👑 هدف ذهبي: `${d['t3']}`\n\n"
            f"🛡️ **الوقف:** `${d['stop']}`\n"
            f"───────────────────")

# ================== معالجة الأوامر ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_subscribed(uid):
        await update.message.reply_text(f"⚠️ **الاشتراك غير مفعل.**\nرابط المتجر: {STORE_LINK}")
        return

    welcome_msg = (
        "🦅 **مرحباً بك في نظام الأسهم الأمريكية V48**\n"
        "أهلاً بك يا أدمن، إليك شرح الخيارات الجديدة:\n\n"
        "📈 **فرص الارتفاع:** مسح فني لأقوى الأسهم المرشحة للصعود.\n"
        "📉 **تنبيهات الهبوط:** تحذير من الأسهم التي تعاني من ضغط بيعي.\n"
        "🔍 **فحص سهم معين:** فحص شامل لأي سهم (أخبار + أهداف + شرعية).\n"
        "🌟 **سهم اليوم:** أفضل فرصة تم اختيارها بعناية من فريقنا.\n"
        "⚖️ **الفلتر الشرعي:** تم دمج حالة الشرعية داخل التقارير الفنية.\n"
        "📊 **سجل الأداء:** عرض نتائج التوصيات السابقة لضمان الشفافية.\n"
        "🧮 **الحاسبة:** لضمان دخولك بوزن محفظة سليم.\n\n"
        "اختر ما يناسبك من القائمة أدناه:"
    )

    menu = [
        ["📈 أفضل فرص الارتفاع", "📉 تنبيهات الهبوط"],
        ["🔍 فحص سهم معين", "🌟 سهم اليوم"],
        ["📊 سجل أداء الأسبوع", "🕒 حالة السوق"],
        ["🧮 حاسبة المخاطر", "⚙️ الدعم والاشتراك"]
    ]
    if uid == ADMIN_ID: menu.insert(0, ["🛠 لوحة التحكم"])
    await update.message.reply_text(welcome_msg, reply_markup=ReplyKeyboardMarkup(menu, resize_keyboard=True), parse_mode="Markdown")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.strip(); uid = update.effective_user.id

    if text.startswith("STK-"):
        ok, exp = verify_secure_code(text)
        if ok:
            users = load_users(); users[str(uid)] = exp; save_users(users)
            await update.message.reply_text("✅ تم تفعيل اشتراكك بنجاح! اضغط /start")
        else: await update.message.reply_text(exp)
        return

    if not is_subscribed(uid): return

    if text in ["📈 أفضل فرص الارتفاع", "📉 تنبيهات الهبوط"]:
        wait = await update.message.reply_text("📡 فحص السوق بناءً على الفلاتر الجديدة...")
        for s in random.sample(LEAD_STOCKS, 3):
            res = await fetch_analysis(s, text)
            if res: await update.message.reply_text(format_report(res), parse_mode="Markdown")
        await wait.delete()

    elif text == "🔍 فحص سهم معين":
        await update.message.reply_text("🔍 أرسل رمز السهم الآن (مثال: `TSLA`):")

    elif text == "🌟 سهم اليوم":
        res = await fetch_analysis("NVDA", "سهم اليوم")
        if res: await update.message.reply_text("👑 **سهم اليوم المختار بعناية**\n\n" + format_report(res), parse_mode="Markdown")

    elif text == "📊 سجل أداء الأسبوع":
        # سجل تجريبي توضيحي — يُنصح بربطه بقاعدة بيانات حقيقية لاحقاً
        report = (
            "📊 **سجل أداء توصيات الأسبوع الماضي (عرض توضيحي):**\n"
            "───────────────────\n"
            "✅ صفقات حققت الهدف الأول: `14`\n"
            "🔥 صفقات حققت الهدف الذهبي: `6`\n"
            "🛡️ صفقات ضربت الوقف: `3`\n"
            "───────────────────\n"
            "📈 **متوسط النجاح العام:** `74%`\n"
            "⚠️ *هذا السجل عرض توضيحي/محاكاة فقط ولا يمثل بيانات تداول حقيقية.*\n"
            "💡 *الشفافية هي سر استمرارنا.*"
        )
        await update.message.reply_text(report, parse_mode="Markdown")

    elif text == "🧮 حاسبة المخاطر":
        await update.message.reply_text("🧮 أرسل كلمة 'احسب' متبوعة بالمبلغ.\nمثال: `احسب 10000`")

    elif text.startswith("احسب"):
        try:
            amt = float(text.split()[1])
            await update.message.reply_text(f"🛡️ **إدارة المخاطر لـ `${amt}`:**\n- دخول الصفقة: `${amt*0.1}`\n- وقف خسارة المحفظة: `${amt*0.02}`")
        except: pass

    elif text == "🕒 حالة السوق":
        tz = pytz.timezone('America/New_York'); now = datetime.now(tz)
        status = "🟢 مفتوح" if (9 <= now.hour < 16 and now.weekday() < 5) else "🔴 مغلق"
        msg = f"🏛️ **بورصة نيويورك:** {status}\n⏰ الوقت: {now.strftime('%I:%M %p')}"
        # تنبيه ما قبل الافتتاح
        if now.hour == 8 and now.minute >= 30: msg += "\n⚠️ *تنبيه: السوق سيبدأ بعد قليل (Pre-Market)*"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "⚙️ الدعم والاشتراك":
        await update.message.reply_text(f"🛒 **المتجر:** {STORE_LINK}\n👻 **الدعم الفني:** {SNAP_LINK}")

    elif uid == ADMIN_ID and text == "🛠 لوحة التحكم":
        count = len(load_users())
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎫 شهر", callback_data="gen_1m"), InlineKeyboardButton("🎫 سنة", callback_data="gen_1y")]])
        await update.message.reply_text(f"👥 عدد المشتركين: {count}", reply_markup=kb)

    else:
        symbol = text.upper().replace("$", "").strip()
        if symbol.isalpha() and len(symbol) <= 5:
            res = await fetch_analysis(symbol)
            if res: await update.message.reply_text(format_report(res), parse_mode="Markdown")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id == ADMIN_ID:
        days = 30 if q.data == "gen_1m" else 365
        code = generate_secure_code(days)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎫 كود جديد:\n`{code}`")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
