import os, logging
from datetime import datetime
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_ID = 8023489682
groq_client = Groq(api_key=GROQ_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
users = {}

def get_user(uid):
    if uid not in users:
        users[uid] = {"history": [], "moods": [], "name": ""}
    return users[uid]

PROMPT = """Sen JAST — o'zbek tilidagi professional ruhiy yordam yordamchisisiz.
QOIDALAR:
1. FAQAT ruhiy salomatlik, his-tuyg'ular, stress, tashvish, depressiya, munosabatlar, shaxsiy o'sish mavzularida gaplash.
2. Boshqa mavzular so'ralsa: "Men faqat ruhiy salomatlik bo'yicha yordam bera olaman. Qanday his qilyapsiz bugun? 💚" de.
3. Har doim o'zbek tilida javob ber.
4. Qisqa, issiq, empatik javob ber (2-4 jumla).
5. Emoji ishlatib yoz.
6. Foydalanuvchini tinglaysan, hukm chiqarmassan.
7. Jiddiy muammolarda psixologga yo'nalt."""

def menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💬 Suhbat"), KeyboardButton("😊 Kayfiyat")],
        [KeyboardButton("🧘 Meditatsiya"), KeyboardButton("🌬 Nafas mashqi")],
        [KeyboardButton("👨‍⚕️ Psixolog bilan bog'lanish")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["name"] = update.effective_user.first_name or "Do'stim"
    await update.message.reply_text(
        f"Salom, {u['name']}! 👋\n\nMen JAST — sizning ruhiy yordam do'stingizman. 💚\n\nQuyidagilardan birini tanlang:",
        reply_markup=menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    txt = update.message.text

    if txt == "💬 Suhbat":
        await update.message.reply_text("💬 Qanday his qilyapsiz? Men tinglayman. 💚", reply_markup=menu())
        return

    if txt == "😊 Kayfiyat":
        await update.message.reply_text("😊 Bugun kayfiyatingiz qanday?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("😄 Zo'r", callback_data="mood_5"), InlineKeyboardButton("🙂 Yaxshi", callback_data="mood_4")],
            [InlineKeyboardButton("😐 O'rtacha", callback_data="mood_3"), InlineKeyboardButton("😔 Yomon", callback_data="mood_2")],
            [InlineKeyboardButton("😢 Juda yomon", callback_data="mood_1")]]))
        return

    if txt == "🧘 Meditatsiya":
        MEDS = [("🧘 Tana skaneri (5 daqiqa)", "1️⃣ Qulay o'tiring\n2️⃣ Ko'zingizni yuming\n3️⃣ Oyoq barmoqdan boshlang\n4️⃣ Sekin boshgacha keling\n5️⃣ Har joyda 10 soniya to'xtang\n\n⏱ 5 daqiqa. 🙏"),("🌊 Xotirjamlik (3 daqiqa)", "1️⃣ Ko'zingizni yuming\n2️⃣ Dengiz to'lqinini tasavvur qiling\n3️⃣ Nafas = to'lqin keladi\n4️⃣ Chiqarish = to'lqin ketadi\n\n⏱ 3 daqiqa. 💙"),("☀️ Ertalab zaryadka (2 daqiqa)", "1️⃣ O'rningizdan turing\n2️⃣ Qo'llarni ko'taring\n3️⃣ 5 marta nafas\n4️⃣ Bugun 1 yaxshi narsa o'ylang\n\n⏱ 2 daqiqa. 💚")]
        await update.message.reply_text("🧘 Meditatsiya tanlang:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(m[0], callback_data=f"med_{i}")] for i,m in enumerate(MEDS)]))
        return

    if txt == "🌬 Nafas mashqi":
        BREATHS = [("4-7-8 Nafas 😴", "4️⃣ soniya — nafas\n7️⃣ soniya — ushlab tur\n8️⃣ soniya — chikar\n\n🔁 4 marta\n💡 Uxlay olmayotganingizda!"),("Quti nafas 📦", "4️⃣-4️⃣-4️⃣-4️⃣ soniya\n\n🔁 5 marta\n💡 Stressda!"),("Tez tinchlash ⚡", "2️⃣ nafas — 4️⃣ chikar\n\n🔁 6 marta = 1 daqiqa\n💡 Panikada!")]
        await update.message.reply_text("🌬 Nafas mashqi tanlang:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(b[0], callback_data=f"breath_{i}")] for i,b in enumerate(BREATHS)]))
        return

    if txt == "👨‍⚕️ Psixolog bilan bog'lanish":
        await update.message.reply_text("👨‍⚕️ Psixolog raqamini olish uchun:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 Psixolog raqamini olish", url="https://t.me/boburxoja")]]))
        return

    # AI chat
    u["history"].append({"role":"user","content":txt})
    if len(u["history"]) > 6:
        u["history"] = u["history"][-6:]
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        r = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":PROMPT}]+u["history"], max_tokens=200, temperature=0.7)
        reply = r.choices[0].message.content
        u["history"].append({"role":"assistant","content":reply})
    except:
        reply = "Hozir texnik muammo. Qayta yozing. 🙏"
    await update.message.reply_text(reply, reply_markup=menu())

async def mood_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    score = int(q.data.split("_")[1])
    texts = {5:"😄 Ajoyib!",4:"🙂 Yaxshi.",3:"😐 Nima bo'ldi?",2:"😔 Yolg'iz emassiz.",1:"😢 Men tinglayman."}
    await q.edit_message_text(texts[score])
    await context.bot.send_message(q.message.chat_id, "Davom etish:", reply_markup=menu())

async def med_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    MEDS = [("🧘 Tana skaneri (5 daqiqa)", "1️⃣ Qulay o'tiring\n2️⃣ Ko'zingizni yuming\n3️⃣ Oyoq barmoqdan boshlang\n4️⃣ Sekin boshgacha keling\n5️⃣ Har joyda 10 soniya to'xtang\n\n⏱ 5 daqiqa. 🙏"),("🌊 Xotirjamlik (3 daqiqa)", "1️⃣ Ko'zingizni yuming\n2️⃣ Dengiz to'lqinini tasavvur qiling\n3️⃣ Nafas = to'lqin keladi\n4️⃣ Chiqarish = to'lqin ketadi\n\n⏱ 3 daqiqa. 💙"),("☀️ Ertalab zaryadka (2 daqiqa)", "1️⃣ O'rningizdan turing\n2️⃣ Qo'llarni ko'taring\n3️⃣ 5 marta nafas\n4️⃣ Bugun 1 yaxshi narsa o'ylang\n\n⏱ 2 daqiqa. 💚")]
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{MEDS[idx][0]}\n\n{MEDS[idx][1]}")
    await context.bot.send_message(q.message.chat_id, "✅ Barakalla! 💚", reply_markup=menu())

async def breath_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    BREATHS = [("4-7-8 Nafas 😴", "4️⃣ soniya — nafas\n7️⃣ soniya — ushlab tur\n8️⃣ soniya — chikar\n\n🔁 4 marta\n💡 Uxlay olmayotganingizda!"),("Quti nafas 📦", "4️⃣-4️⃣-4️⃣-4️⃣ soniya\n\n🔁 5 marta\n💡 Stressda!"),("Tez tinchlash ⚡", "2️⃣ nafas — 4️⃣ chikar\n\n🔁 6 marta = 1 daqiqa\n💡 Panikada!")]
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{BREATHS[idx][0]}\n\n{BREATHS[idx][1]}")
    await context.bot.send_message(q.message.chat_id, "✅ Yaxshi ish! 💚", reply_markup=menu())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Bu buyruq faqat admin uchun! 🔒")
        return
    total = len(users)
    total_moods = sum(len(u["moods"]) for u in users.values())
    total_chats = sum(len(u["history"]) for u in users.values())
    await update.message.reply_text(f"📊 JAST Statistika:\n\n👤 Foydalanuvchilar: {total}\n💬 Suhbatlar: {total_chats}\n😊 Kayfiyat: {total_moods}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(mood_cb, pattern="^mood_"))
    app.add_handler(CallbackQueryHandler(med_cb, pattern="^med_"))
    app.add_handler(CallbackQueryHandler(breath_cb, pattern="^breath_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("JAST ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
