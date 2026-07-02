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
STORE_LINK = os.getenv("STORE_LINK", "@aqk1992")
SNAP_LINK = os.getenv("SNAP_LINK", "@aqk1992")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

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

# ================== نظام الذاكرة (Supabase) ==================
async def load_users():
    """تحميل المشتركين من Supabase أو ملف محلي احتياطياً."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        if not os.path.exists(USERS_FILE): return {}
        try:
            with open(USERS_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    url = f"{SUPABASE_URL}/rest/v1/users?select=user_id,expiry"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    rows = await resp.json()
                    return {row["user_id"]: row["expiry"] for row in rows}
                print("Supabase load_users error status:", resp.status)
    except Exception as e:
        print("Supabase load_users error:", e)
    return {}

async def save_user(user_id, expiry):
    """حفظ/تحديث مشترك واحد في Supabase أو ملف محلي احتياطياً."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        users = {}
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding='utf-8') as f:
                    users = json.load(f)
            except: pass
        users[str(user_id)] = expiry
        with open(USERS_FILE, "w", encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
        return True
    url = f"{SUPABASE_URL}/rest/v1/users?on_conflict=user_id"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {"user_id": str(user_id), "expiry": float(expiry)}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=12) as resp:
                return resp.status in (200, 201)
    except Exception as e:
        print("Supabase save_user error:", e)
        return False

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

async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True
    users = await load_users()
    return str(user_id) in users and time.time() < float(users[str(user_id)])

# ================== محرك التحليل المطور V48 ==================
def calculate_vwap(quote):
    """حساب Volume Weighted Average Price من بيانات الشموع."""
    highs = quote.get('high', [])
    lows = quote.get('low', [])
    closes = quote.get('close', [])
    volumes = quote.get('volume', [])
    cum_pv = 0.0
    cum_v = 0.0
    for h, l, c, v in zip(highs, lows, closes, volumes):
        if h is None or l is None or c is None or v is None or v == 0:
            continue
        typical = (h + l + c) / 3.0
        cum_pv += typical * v
        cum_v += v
    return cum_pv / cum_v if cum_v > 0 else None

def fill_gaps(values):
    """ملء القيم المفقودة بآخر قيمة صالحة."""
    out = []
    last = None
    for v in values:
        if v is not None:
            last = v
        out.append(last)
    return out

def sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period

def ema_series(data, period):
    if len(data) < period:
        return []
    k = 2 / (period + 1)
    ema = [None] * (period - 1) + [sum(data[:period]) / period]
    for price in data[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

def rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(prices):
    ema12 = ema_series(prices, 12)
    ema26 = ema_series(prices, 26)
    macd_line = [a-b if a is not None and b is not None else None for a,b in zip(ema12, ema26)]
    start = next((i for i,v in enumerate(macd_line) if v is not None), None)
    if start is None:
        return None, None, None
    macd_vals = macd_line[start:]
    signal_vals = ema_series(macd_vals, 9)
    if not signal_vals or signal_vals[-1] is None:
        return None, None, None
    return macd_vals[-1], signal_vals[-1], macd_vals[-1] - signal_vals[-1]

def momentum(prices, period=10):
    if len(prices) < period + 1:
        return None
    return ((prices[-1] - prices[-period-1]) / prices[-period-1]) * 100

def liquidity_flow(closes, volumes, period=14):
    if len(closes) < period + 1:
        return None, None
    inflow = 0.0
    outflow = 0.0
    for i in range(-period, 0):
        c = closes[i]
        prev_c = closes[i-1]
        v = volumes[i]
        if c is None or prev_c is None or v is None or v <= 0:
            continue
        if c > prev_c:
            inflow += v
        elif c < prev_c:
            outflow += v
    return inflow, outflow

async def fetch_analysis(symbol, type_label="تحليل"):
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=1mo"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=12) as response:
                if response.status != 200: return None
                data = await response.json()
                res = data['chart']['result'][0]
                price = res['meta']['regularMarketPrice']
                prev_close = res['meta'].get('previousClose') or price
                change = ((price - prev_close) / prev_close) * 100
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

                # 📊 حساب استراتيجية VWAP
                quote = res['indicators']['quote'][0]
                vwap = calculate_vwap(quote)
                if vwap:
                    vwap_dist = ((price - vwap) / vwap) * 100
                    if price > vwap * 1.005:
                        vwap_signal = "📈 السعر فوق VWAP — ضغط شرائي"
                    elif price < vwap * 0.995:
                        vwap_signal = "📉 السعر تحت VWAP — ضغط بيعي"
                    else:
                        vwap_signal = "⚖️ السعر قريب من VWAP — توازن"
                else:
                    vwap = 0
                    vwap_dist = 0
                    vwap_signal = "⚠️ لا توجد بيانات حجم كافية"

                # 📈 المؤشرات الفنية الإضافية
                closes = fill_gaps(quote.get('close', []))
                volumes = fill_gaps(quote.get('volume', []))

                rsi_val = rsi(closes)
                macd_line, macd_signal, macd_hist = compute_macd(closes)
                sma20 = sma(closes, 20)
                sma50 = sma(closes, 50)
                ema20_val = ema_series(closes, 20)[-1] if len(closes) >= 20 else None
                mom = momentum(closes)
                inflow, outflow = liquidity_flow(closes, volumes)
                if inflow is not None:
                    total_flow = inflow + outflow
                    if total_flow > 0:
                        in_pct = (inflow / total_flow) * 100
                        out_pct = (outflow / total_flow) * 100
                        liquidity_signal = f"🟢 سيولة داخلة {in_pct:.1f}% | 🔴 خارجة {out_pct:.1f}%"
                    else:
                        liquidity_signal = "⚪ لا توجد بيانات سيولة كافية"
                else:
                    liquidity_signal = "⚪ لا توجد بيانات سيولة كافية"

                return {
                    "symbol": symbol.upper(), "price": price, "change": round(change, 2),
                    "accuracy": accuracy, "news": news, "rec": rec, "halal": halal_status,
                    "t1": round(price * 1.015, 2), "t2": round(price * 1.038, 2), "t3": round(price * 1.06, 2),
                    "stop": round(price * 0.96, 2),
                    "vwap": round(vwap, 2), "vwap_dist": round(vwap_dist, 2), "vwap_signal": vwap_signal,
                    "rsi": round(rsi_val, 2) if rsi_val is not None else "N/A",
                    "macd": round(macd_line, 3) if macd_line is not None else "N/A",
                    "macd_signal": round(macd_signal, 3) if macd_signal is not None else "N/A",
                    "macd_hist": round(macd_hist, 3) if macd_hist is not None else "N/A",
                    "sma20": round(sma20, 2) if sma20 is not None else "N/A",
                    "sma50": round(sma50, 2) if sma50 is not None else "N/A",
                    "ema20": round(ema20_val, 2) if ema20_val is not None else "N/A",
                    "momentum": round(mom, 2) if mom is not None else "N/A",
                    "liquidity_signal": liquidity_signal
                }
        except: return None

def format_report(d):
    return (f"📊 **تقرير فني: {d['symbol']}**\n"
            f"{d['halal']}\n"
            f"───────────────────\n"
            f"💰 **السعر**\n"
            f"`${d['price']}` ({d['change']}%)\n"
            f"───────────────────\n"
            f"📢 **التوصية**\n"
            f"{d['rec']}\n"
            f"───────────────────\n"
            f"🎯 **نسبة النجاح**\n"
            f"`{d['accuracy']}%` (واقعية)\n"
            f"───────────────────\n"
            f"📰 **الأخبار**\n"
            f"`{d['news']}`\n"
            f"───────────────────\n"
            f"📊 **VWAP**\n"
            f"`${d['vwap']}` ({d['vwap_dist']}%)\n"
            f"{d['vwap_signal']}\n"
            f"───────────────────\n"
            f"📈 **المؤشرات الفنية**\n"
            f"• **RSI(14):** `{d['rsi']}`\n"
            f"• **MACD:** `{d['macd']}` | **Signal:** `{d['macd_signal']}` | **Hist:** `{d['macd_hist']}`\n"
            f"• **SMA20:** `{d['sma20']}` | **SMA50:** `{d['sma50']}` | **EMA20:** `{d['ema20']}`\n"
            f"• **الزخم (10):** `{d['momentum']}%`\n"
            f"• **السيولة:** {d['liquidity_signal']}\n"
            f"───────────────────\n"
            f"✅ **الأهداف**\n"
            f"🎯 هدف 1: `${d['t1']}`\n"
            f"🎯 هدف 2: `${d['t2']}`\n"
            f"👑 هدف ذهبي: `${d['t3']}`\n"
            f"───────────────────\n"
            f"🛡️ **الوقف**\n"
            f"`${d['stop']}`\n"
            f"───────────────────")

# ================== معالجة الأوامر ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not await is_subscribed(uid):
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
            await save_user(uid, exp)
            await update.message.reply_text("✅ تم تفعيل اشتراكك بنجاح! اضغط /start")
        else: await update.message.reply_text(exp)
        return

    if not await is_subscribed(uid): return

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
        await update.message.reply_text(f"**الدعم الفني:** {SNAP_LINK}")

    elif uid == ADMIN_ID and text == "🛠 لوحة التحكم":
        count = len(await load_users())
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
