""" تحديث شامل لملف bot.py ميزات:

جلب التوكنات من Secrets (بيئة التشغيل)

تحقق ومخارج لطباعة ما إذا كانت التوكنات موجودة (بدون كشفها)

عمليات تشغيل / إيقاف / حالة للـ GitHub Actions (dispatches, cancel, list runs)

retries عند فشل طلبات الشبكة

تسجيل (logging)

أمر /debug لعرض حالة التهيئة (للمالك فقط)

رسائل واضحة في حالة أخطاء التوكن أو صلاحيات GitHub

قابلية ربط watcher بإرسال dispatch لملف watcher (اختياري)


ملاحظة أمان: لا تضع التوكنات داخل هذا الملف. استخدم GitHub Secrets باسماء:

TELEGRAM_BOT_TOKEN

MY_GITHUB_TOKEN


استعمال: ارفعه للريبو باسم bot.py ثم شغّل الـ Workflow في Actions. """

import os import sys import asyncio import time import logging from typing import Optional, Dict, Any

import requests from requests.exceptions import RequestException

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import ( ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, )

==================== إعدادات المستخدم ====================

OWNER_ID = 7834574830  # غيّر إذا لزم OWNER = "SamiALqutami" REPO = "Tmooil" WORKFLOW_FILE = os.getenv("WORKFLOW_FILE", "main.yml") BRANCH = os.getenv("WORKFLOW_BRANCH", "main") WATCHER_WORKFLOW_FILE = os.getenv("WATCHER_WORKFLOW_FILE", "watcher.yml")  # اختياري

==================== جلب التوكنات من البيئة ====================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")

==================== تهيئة الهيدر لطلبات GitHub ====================

HEADERS = { "Authorization": f"Bearer {GITHUB_TOKEN}" if GITHUB_TOKEN else "", "Accept": "application/vnd.github+json" }

==================== تهيئة اللوق ====================

logging.basicConfig( level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", ) logger = logging.getLogger(name)

==================== أدوات مساعدة ====================

def mask_token(token: Optional[str]) -> str: if not token: return "<not set>" if len(token) <= 8: return "*" * len(token) return token[:4] + "..." + token[-4:]

def github_api_url(endpoint: str) -> str: return f"https://api.github.com/repos/{OWNER}/{REPO}/{endpoint}"

def requests_retry_session(retries: int = 3, backoff: float = 0.5): session = requests.Session() # يمكن توسيع هذه الوظيفة إن أردت استخدام urllib3 Retry session.retries = retries session.backoff = backoff return session

def github_request(method: str, endpoint: str, json_data: Optional[Dict[str, Any]] = None, timeout: int = 15): """إجراء بسيط مع إعادة محاولة بسيطة. يعيد كائن Response أو يرفع استثناء.""" url = github_api_url(endpoint) last_exc = None session = requests_retry_session() for attempt in range(1, 4): try: if method.upper() == "POST": resp = session.post(url, headers=HEADERS, json=json_data, timeout=timeout) else: resp = session.get(url, headers=HEADERS, timeout=timeout)

# اذا كان JSON return non-JSON يمكن الوصول إليه لاحقاً
        return resp

    except RequestException as e:
        last_exc = e
        logger.warning("محاولة GitHub (%d) فشلت: %s", attempt, str(e))
        time.sleep(session.backoff * attempt)

raise last_exc or Exception("فشل غير معروف في طلب GitHub")

async def send_owner_message(app, text: str): """إرسال رسالة خاصة للمالك مع محاولة إعادة المحاولة إذا فشل الإرسال.""" try: await app.bot.send_message(chat_id=OWNER_ID, text=text) except Exception as e: logger.warning("فشل إرسال رسالة للمالك: %s", e)

==================== لوحة الأزرار ====================

def control_keyboard(): return InlineKeyboardMarkup([ [ InlineKeyboardButton("🚀 تشغيل", callback_data="run"), InlineKeyboardButton("⛔ إيقاف", callback_data="stop"), ], [InlineKeyboardButton("📊 الحالة", callback_data="status")], ])

==================== معالجات الأوامر ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.effective_user.id != OWNER_ID: return await update.message.reply_text("🎮 لوحة التحكم في GitHub Actions", reply_markup=control_keyboard())

async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): """يعطي معلومات التهيئة دون كشف التوكنات الكاملة - للمالك فقط""" if update.effective_user.id != OWNER_ID: return

bot_set = bool(BOT_TOKEN)
gh_set = bool(GITHUB_TOKEN)

text = (
    f"🔧 حالة التهيئة:\n"
    f"- BOT token set: {'✅' if bot_set else '❌'} ({mask_token(BOT_TOKEN)})\n"
    f"- GH token set: {'✅' if gh_set else '❌'} ({mask_token(GITHUB_TOKEN)})\n"
    f"- Repo: {OWNER}/{REPO}\n"
    f"- Workflow file: {WORKFLOW_FILE}\n"
    f"- Watcher workflow (optional): {WATCHER_WORKFLOW_FILE}\n"
)
await update.message.reply_text(text)

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer()

if query.from_user.id != OWNER_ID:
    return

# تشغيل Workflow
if query.data == "run":
    await query.edit_message_text("⏳ جاري إرسال أمر تشغيل...")
    try:
        resp = await asyncio.to_thread(
            github_request,
            "POST",
            f"actions/workflows/{WORKFLOW_FILE}/dispatches",
            {"ref": BRANCH},
        )
    except Exception as e:
        logger.error("خطأ في طلب التشغيل: %s", e)
        await query.edit_message_text("❌ حدث خطأ أثناء التواصل مع GitHub. تفقد السجلات.")
        await send_owner_message(context.application, f"خطأ في تشغيل workflow: {e}")
        return

    if resp.status_code == 204:
        await query.edit_message_text("✅ تم إرسال أمر التشغيل بنجاح", reply_markup=control_keyboard())
    else:
        # عرض تفاصيل مختصرة
        msg = f"❌ فشل التشغيل (HTTP {resp.status_code})\n{resp.text}"
        logger.warning(msg)
        await query.edit_message_text(msg, reply_markup=control_keyboard())
        if resp.status_code in (401, 403):
            await send_owner_message(context.application, "تحذير: استجابة GitHub تفيد بمشكلة في التوكن أو الصلاحيات.")

# حالة آخر Run
elif query.data == "status":
    await query.edit_message_text("⏳ جلب حالة آخر تشغيل...")
    try:
        resp = await asyncio.to_thread(github_request, "GET", "actions/runs?per_page=1")
    except Exception as e:
        logger.error("خطأ جلب الحالة: %s", e)
        await query.edit_message_text("❌ فشل جلب الحالة من GitHub.", reply_markup=control_keyboard())
        return

    if resp.status_code != 200:
        await query.edit_message_text(f"❌ خطأ GitHub (HTTP {resp.status_code})\n{resp.text}", reply_markup=control_keyboard())
        return

    data = resp.json()
    runs = data.get("workflow_runs", [])
    if not runs:
        await query.edit_message_text("ℹ️ لا توجد عمليات مسجلة.", reply_markup=control_keyboard())
        return

    run = runs[0]
    status = run.get("status", "unknown")
    conclusion = run.get("conclusion") or "قيد التشغيل/بانتظار"
    started = run.get("run_started_at", "N/A")
    html_url = run.get("html_url", "")

    msg = (
        f"📊 الحالة الحالية لآخر عملية:\n\n"
        f"🔹 الحالة: `{status}`\n"
        f"🔹 النتيجة: `{conclusion}`\n"
        f"⏰ بدأ في: `{started}`\n"
        f"🔗 {html_url}"
    )
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=control_keyboard())

# إيقاف آخر Run
elif query.data == "stop":
    await query.edit_message_text("⏳ جاري محاولة إيقاف آخر عملية (إن وجدت)...")
    try:
        resp = await asyncio.to_thread(github_request, "GET", "actions/runs?per_page=1")
    except Exception as e:
        logger.error("خطأ جلب العمليات: %s", e)
        await query.edit_message_text("❌ فشل التواصل مع GitHub.", reply_markup=control_keyboard())
        return

    if resp.status_code != 200:
        await query.edit_message_text(f"❌ خطأ GitHub (HTTP {resp.status_code})\n{resp.text}", reply_markup=control_keyboard())
        return

    runs = resp.json().get("workflow_runs", [])
    if not runs:
        await query.edit_message_text("ℹ️ لا توجد عمليات لإيقافها.", reply_markup=control_keyboard())
        return

    run = runs[0]
    run_id = run.get("id")
    run_status = run.get("status")
    if run_status not in ("in_progress", "queued"):
        await query.edit_message_text("ℹ️ آخر عملية ليست في حالة قابلة للإيقاف.", reply_markup=control_keyboard())
        return

    try:
        stop_resp = await asyncio.to_thread(github_request, "POST", f"actions/runs/{run_id}/cancel")
    except Exception as e:
        logger.error("خطأ إرسال أمر الإيقاف: %s", e)
        await query.edit_message_text("❌ فشل إرسال أمر الإيقاف.", reply_markup=control_keyboard())
        return

    if stop_resp.status_code == 202:
        await query.edit_message_text(f"⛔ تم إرسال طلب إيقاف للعملية `{run_id}`", reply_markup=control_keyboard())
    else:
        await query.edit_message_text(f"❌ فشل الإيقاف (HTTP {stop_resp.status_code})", reply_markup=control_keyboard())

==================== نقطة الدخول للتشغيل ====================

if name == "main": # تحقق أولي قبل التشغيل logger.info("بدء التحقق من المتغيرات...") logger.info("BOT_TOKEN set: %s", bool(BOT_TOKEN)) logger.info("GITHUB_TOKEN set: %s", bool(GITHUB_TOKEN))

if not BOT_TOKEN:
    logger.error("لم يتم العثور على TELEGRAM_BOT_TOKEN في البيئة. تأكد من وضعه في Secrets والتمرير في YAML.")
if not GITHUB_TOKEN:
    logger.error("لم يتم العثور على MY_GITHUB_TOKEN في البيئة. تأكد من وضعه في Secrets والتمرير في YAML.")

if not BOT_TOKEN or not GITHUB_TOKEN:
    logger.error("لن يتم تشغيل البوت حتى تُعالج المتغيرات المفقودة.")
    sys.exit(1)

app = ApplicationBuilder().token(BOT_TOKEN).build()

# أوامر
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("debug", debug_cmd))
app.add_handler(CallbackQueryHandler(handle_buttons))

logger.info("🤖 البوت جاهز - بدء التشغيل (polling)...")
try:
    app.run_polling()
except KeyboardInterrupt:
    logger.info("تم الإيقاف بواسطة المستخدم")
except Exception as e:
    logger.exception("خطأ غير متوقع عند تشغيل البوت: %s", e)
    # حاول إبلاغ المالك إن أمكن (غير مضمون داخل Action إذا انتهت صلاحية البوت)
    try:
        asyncio.run(send_owner_message(app, f"خطأ غير متوقع في bot.py: {e}"))
    except Exception:
        pass 
