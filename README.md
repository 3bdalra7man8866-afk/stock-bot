# Stock Bot

بوت Telegram لتحليل الأسهم الأمريكية وإدارة الاشتراكات.

## المتطلبات

- Python 3.10+
- حساب Telegram
- حساب Railway

## التشغيل محلياً

1. نسخ ملف البيئة:
   ```bash
   cp .env.example .env
   ```
2. تعديل قيم `.env` بتوكن البوت والإعدادات.
3. تثبيت المتطلبات:
   ```bash
   pip install -r requirements.txt
   ```
4. تشغيل البوت:
   ```bash
   python U.py
   ```

## النشر على Railway

1. أنشئ مستودع GitHub وارفع المشروع (بدون ملف `.env`، فهو في `.gitignore`).
2. في Railway: **New Project → Deploy from GitHub repo** واختر المستودع.
3. اذهب إلى **Variables** وأضف كل متغيرات `.env`:
   - `BOT_TOKEN`
   - `ADMIN_ID`
   - `SECRET_KEY`
   - `USERS_FILE`
   - `STORE_LINK`
   - `SNAP_LINK`
4. اضغط **Deploy**.

> **ملاحظة:** ملف `.env` محلي فقط. لا ترفعه إلى GitHub أبداً.
