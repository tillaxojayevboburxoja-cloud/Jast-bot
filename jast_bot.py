import os, logging
from datetime import datetime
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
PSYCHOLOGIST = os.environ.get("PSYCHOLOGIST_USERNAME", "@jast_psixolog")
groq_client = Groq(api_key=GROQ_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAIN_MENU, CHAT, MOOD, MEDITATION, BREATHING = range(5)
users = {}

def get_user(uid):
    if uid not in users:
        users[uid] = {"history": [], "moods": [], "name": ""}
    return users[uid]

PROMPT = "Sen JAST - o'zbek tilida ruhiy yordam yordamchisi. Faqat o'zbek tilida gapir. Qisqa javob ber."

def menu():
    return ReplyKeyboardMarkup([[KeyboardButton("Suhbat"), KeyboardButton("Kayfiyat")],[KeyboardButton("Meditatsiya"), KeyboardButton("Nafas mashqi")],[KeyboardButton("Psixolog bilan boglaning")]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["name"] = update.effective_user.first_name or "Dostim"
    await update.message.reply_text(f"Salom, {u['name']}!\n\nMen JAST — ruhiy yordam yordamchingman.\nNimadan boshlaysiz?", reply_markup=menu())
    return MAIN_MENU

async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    txt = update.message.text
    if txt in ["Suhbat","Kayfiyat","Meditatsiya","Nafas mashqi","Psixolog bilan boglaning"]:
        return await handle_menu(update, context)
    u["history"].append({"role":"user","content":txt})
    if len(u["history"]) > 6:
        u["history"] = u["history"][-6:]
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        r = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":PROMPT}]+u["history"], max_tokens=200, temperature=0.7)
        reply = r.choices[0].message.content
        u["history"].append({"role":"assistant","content":reply})
    except:
        reply = "Hozir texnik muammo. Qayta yozing."
    await update.message.reply_text(reply, reply_markup=menu())
    return CHAT

async def mood_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bugun kayfiyatingiz qanday?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Zor", callback_data="mood_5"), InlineKeyboardButton("Yaxshi", callback_data="mood_4")],[InlineKeyboardButton("Ortacha", callback_data="mood_3"), InlineKeyboardButton("Yomon", callback_data="mood_2")],[InlineKeyboardButton("Juda yomon", callback_data="mood_1")]]))
    return MOOD

async def mood_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = get_user(q.from_user.id)
    score = int(q.data.split("_")[1])
    u["moods"].append({"score":score,"date":datetime.now().strftime("%d.%m")})
    texts = {5:"Ajoyib!",4:"Yaxshi.",3:"Tushunarli. Nima boldi?",2:"Qiyin payt. Yolgiz emassiz.",1:"Bu ogir. Men tinglayman."}
    await q.edit_message_text(texts[score])
    if score <= 2:
        await context.bot.send_message(q.message.chat_id, "Psixolog bilan gaplashing:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Psixologga yozing", url=f"https://t.me/{PSYCHOLOGIST.replace('@','')}")]]))
    await context.bot.send_message(q.message.chat_id, "Davom etish:", reply_markup=menu())
    return MAIN_MENU

MEDS = [("Tana skaneri (5 daqiqa)", "1. Qulay turing\n2. Kozingizni yuming\n3. Oyoq barmoqdan boshlang\n4. Boshgacha keling\n5. Har joyda 10 soniya toting"),("Xotirjamlik (3 daqiqa)", "1. Kozingizni yuming\n2. Dengiz tolqinini tasavvur qiling\n3. Nafas = tolqin keladi\n4. Chikarish = tolqin ketadi"),("Ertalab zaryadka (2 daqiqa)", "1. Ornidan turing\n2. Qollarni kotaring\n3. 5 marta nafas\n4. Bugun 1 yaxshi narsa oylang")]

async def med_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Meditatsiya tanlang:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(m[0], callback_data=f"med_{i}")] for i,m in enumerate(MEDS)]))
    return MEDITATION

async def med_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{MEDS[idx][0]}\n\n{MEDS[idx][1]}")
    await context.bot.send_message(q.message.chat_id, "Barakalla!", reply_markup=menu())
    return MAIN_MENU

BREATHS = [("4-7-8 Nafas", "4 soniya nafas\n7 soniya ushlab tur\n8 soniya chikar\n\n4 marta takrorla"),("Quti nafas", "4 soniya nafas\n4 soniya ushlab\n4 soniya chikar\n4 soniya ushlab\n\n5 marta"),("Tez tinchlash", "2 soniya nafas\n4 soniya chikar\n\n6 marta = 1 daqiqa")]

async def breath_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Nafas mashqi tanlang:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(b[0], callback_data=f"breath_{i}")] for i,b in enumerate(BREATHS)]))
    return BREATHING

async def breath_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{BREATHS[idx][0]}\n\n{BREATHS[idx][1]}")
    await context.bot.send_message(q.message.chat_id, "Yaxshi ish!", reply_markup=menu())
    return MAIN_MENU

async def psychologist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Professional yordam olish jasorat belgisi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Psixologga yozing", url=f"https://t.me/{PSYCHOLOGIST.replace('@','')}")]]))
    return MAIN_MENU

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if t == "Suhbat": return await start(update, context)
    elif t == "Kayfiyat": return await mood_start(update, context)
    elif t == "Meditatsiya": return await med_start(update, context)
    elif t == "Nafas mashqi": return await breath_start(update, context)
    elif t == "Psixolog bilan boglaning": return await psychologist(update, context)
    else: return await chat_message(update, context)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(entry_points=[CommandHandler("start", start)], states={MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu)], CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message)], MOOD: [CallbackQueryHandler(mood_cb, pattern="^mood_")], MEDITATION: [CallbackQueryHandler(med_cb, pattern="^med_")], BREATHING: [CallbackQueryHandler(breath_cb, pattern="^breath_")]}, fallbacks=[CommandHandler("start", start)])
    app.add_handler(conv)
    logger.info("JAST ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
