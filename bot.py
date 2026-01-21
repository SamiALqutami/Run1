import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ========= الإعدادات =========
OWNER_ID = 7834574830
BOT_TOKEN = "8536314905:AAFN5mkHLIkJBgfxtFwwp7-nsxFmDHzehB4"

GITHUB_TOKEN = "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"
OWNER = "SamiALqutami"
REPO = "Tmooil"
WORKFLOW_FILE = "main.yml"
BRANCH = "main"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ========= لوحة التحكم =========
def control_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 تشغيل", callback_data="run"),
            InlineKeyboardButton("⛔ إيقاف", callback_data="stop")
        ],
        [
            InlineKeyboardButton("📊 الحالة", callback_data="status")
        ]
    ])

# ========= GitHub API =========
def github_request(method, endpoint, data=None):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/{endpoint}"
    if method == "POST":
        return requests.post(url, headers=HEADERS, json=data, timeout=15)
    return requests.get(url, headers=HEADERS, timeout=15)

# ========= أوامر =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(
        "🎮 لوحة التحكم في GitHub Actions",
        reply_markup=control_keyboard()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        return

    if query.data == "run":
        await query.edit_message_text("⏳ جاري تشغيل Workflow...")
        r = await asyncio.to_thread(
            github_request,
            "POST",
            f"actions/workflows/{WORKFLOW_FILE}/dispatches",
            {"ref": BRANCH}
        )
        if r.status_code == 204:
            await query.edit_message_text("✅ تم التشغيل بنجاح", reply_markup=control_keyboard())
        else:
            await query.edit_message_text(f"❌ فشل التشغيل\n{r.text}", reply_markup=control_keyboard())

    elif query.data == "status":
        r = await asyncio.to_thread(
            github_request,
            "GET",
            "actions/runs?per_page=1"
        )
        runs = r.json().get("workflow_runs", [])
        if not runs:
            await query.edit_message_text("ℹ️ لا توجد عمليات", reply_markup=control_keyboard())
            return

        run = runs[0]
        msg = (
            f"📊 الحالة الحالية\n\n"
            f"🔹 الحالة: `{run['status']}`\n"
            f"🔹 النتيجة: `{run['conclusion']}`\n"
            f"⏰ بدأ: `{run['run_started_at']}`\n"
            f"🔗 {run['html_url']}"
        )
        await query.edit_message_text(msg, reply_markup=control_keyboard())

    elif query.data == "stop":
        r = await asyncio.to_thread(
            github_request,
            "GET",
            "actions/runs?per_page=1"
        )
        runs = r.json().get("workflow_runs", [])
        if not runs:
            await query.edit_message_text("ℹ️ لا يوجد تشغيل لإيقافه", reply_markup=control_keyboard())
            return

        run_id = runs[0]["id"]
        stop = await asyncio.to_thread(
            github_request,
            "POST",
            f"actions/runs/{run_id}/cancel"
        )

        if stop.status_code == 202:
            await query.edit_message_text("⛔ تم إيقاف العملية", reply_markup=control_keyboard())
        else:
            await query.edit_message_text("❌ فشل الإيقاف", reply_markup=control_keyboard())

# ========= تشغيل =========
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    print("🤖 البوت يعمل...")
    app.run_polling()