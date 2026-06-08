import os, logging
from datetime import datetime
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
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
        users[uid] = {
            "history": [],
            "moods": [],
            "name": "",
            "stage": "start",
            "problem": ""
        }
    return users[uid]

SYSTEM_PROMPT = """Sen JAST — O'zbekistonning eng kuchli ruhiy yordam yordamchisisisan.

SEN QANDAY ISHLAYSAN:
1. Foydalanuvchi muammosini aytganda — AVVAL his-tuyg'ularini tan ol
2. 1-2 ta aniqlashtiruvchi savol ber
3. Muammoni aniqlagach — mos terapevtik texnikani qo'll
4. CBT (salbiy fikrni qayta shakllantirish), nafas mashqi, meditatsiya, motivatsiya texnikalarini ishlatish
5. Har javob oxirida kuzatib boruvchi savol ber
6. Kichik muvaffaqiyatlarni nishonla — "Zo'r, bu katta qadam!"
7. O'z joniga qasd, zo'ravonlik holatida — darhol psixologga yo'nalt

TERAPEVTIK TEXNIKALAR (ishlatish majburiy):

CBT texnikasi — salbiy fikr kelganda:
"Bu fikr haqiqatmi? Buning isboti bormi? Eng yomon holat nima bo'lardi? Eng yaxshi holat-chi?"

Nafas texnikasi — stress/tashvish uchun:
"4 soniya nafas → 7 soniya ushlab tur → 8 soniya chiqa — 3 marta takrorla"

Minnatdorlik texnikasi — tushkunlik uchun:
"Bugun 3 ta yaxshi narsa toping — kichkina bo'lsa ham"

Fikr qayd etish — ko'p o'ylash uchun:
"Bu fikrni yozing → Hissiyotingizni belgilang → Muqobil fikr o'ylang"

Kuchli tomonlar — ishonchsizlik uchun:
"Hayotingizda 3 ta muvaffaqiyatingizni aytib bering"

MUHIM QOIDALAR:
- Faqat o'zbek tilida gapir
- Hech qachon "men bilmayman" dema — doim yordam ber
- Boshqa mavzularda: "Men faqat ruhiy salomatlik bo'yicha yordam bera olaman 💚"
- Har javob 3-5 jumladan iborat bo'lsin
- Emoji ishlatib yoz — issiq, samimiy ton
- Foydalanuvchi yaxshi natijaga chiqsa: "Siz bugun katta qadam qo'ydingiz! 🌟"

USLUB: Eng yaxshi do'st + professional psixolog = JAST"""

DIAGNOSTIC_PROMPT = """Sen JAST diagnostika tizimisisan. Foydalanuvchi muammosini tahlil qil va FAQAT quyidagi kategoriyalardan birini qaytara:

STRESS — ish, o'qish, moliyaviy stress
TASHVISH — kelajak, noaniqlik, qo'rquv  
TUSHKUNLIK — kayfiyat tushish, umidsizlik
YOLG'IZLIK — muloqot yo'qligi, tushunilmaslik
G'AZAB — asabiylik, chidamsizlik
UYQU — uxlay olmaslik, charchoq
ISHONCH — o'ziga ishonchsizlik, shubha
MUNOSABAT — oila, do'st, sevgi muammolari
INQIROZ — o'z joniga qasd, o'ziga zarar

Faqat bitta so'z qaytara. Boshqa narsa yozma."""

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💬 Dardimni aytay"), KeyboardButton("😊 Kayfiyatim")],
        [KeyboardButton("🧘 Meditatsiya"), KeyboardButton("🌬 Nafas mashqi")],
        [KeyboardButton("💪 Motivatsiya"), KeyboardButton("👨‍⚕️ Psixolog")],
        [KeyboardButton("📊 Mening holatim")]
    ], resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("🏠 Bosh menu")]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["name"] = update.effective_user.first_name or "Do'stim"
    u["stage"] = "menu"
    u["history"] = []
    await update.message.reply_text(
        f"Salom, {u['name']}! 👋\n\n"
        f"Men JAST — sizning ruhiy yordam do'stingizman. 💚\n\n"
        f"Har qanday muammo, tashvish yoki his-tuyg'u bilan kelishingiz mumkin.\n"
        f"Men doim siz bilan birman. 🤝\n\n"
        f"Bugun sizga qanday yordam bera olaman?",
        reply_markup=main_menu())

async def diagnose_problem(text):
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": DIAGNOSTIC_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=20, temperature=0.1)
        return r.choices[0].message.content.strip().upper()
    except:
        return "STRESS"

async def get_ai_response(history, user_message):
    history.append({"role": "user", "content": user_message})
    if len(history) > 10:
        history = history[-10:]
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            max_tokens=300, temperature=0.7)
        reply = r.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        return reply, history
    except:
        return "Hozir texnik muammo bor. Qayta yozing. 🙏", history

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    txt = update.message.text

    # Bosh menu
    if txt == "🏠 Bosh menu":
        u["stage"] = "menu"
        u["history"] = []
        await update.message.reply_text("Bosh menuga qaytdingiz 🏠", reply_markup=main_menu())
        return

    # Kayfiyat
    if txt == "😊 Kayfiyatim":
        u["stage"] = "mood"
        await update.message.reply_text(
            "😊 Bugun kayfiyatingiz qanday?\nO'zingizga to'g'ri baho bering:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😄 Ajoyib", callback_data="mood_5"),
                 InlineKeyboardButton("🙂 Yaxshi", callback_data="mood_4")],
                [InlineKeyboardButton("😐 O'rtacha", callback_data="mood_3"),
                 InlineKeyboardButton("😔 Yomon", callback_data="mood_2")],
                [InlineKeyboardButton("😢 Juda yomon", callback_data="mood_1")]]))
        return

    # Meditatsiya
    if txt == "🧘 Meditatsiya":
        u["stage"] = "med"
        await update.message.reply_text(
            "🧘 Qaysi meditatsiyani sinab ko'rmoqchisiz?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧘 Tana skaneri (5 daq)", callback_data="med_0")],
                [InlineKeyboardButton("🌊 Xotirjamlik (3 daq)", callback_data="med_1")],
                [InlineKeyboardButton("☀️ Ertalab zaryadka (2 daq)", callback_data="med_2")],
                [InlineKeyboardButton("🌙 Kechki tinchlanish (5 daq)", callback_data="med_3")]]))
        return

    # Nafas mashqi
    if txt == "🌬 Nafas mashqi":
        u["stage"] = "breath"
        await update.message.reply_text(
            "🌬 Hozir qanday holatsiz?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😰 Tashvish/xavotir", callback_data="breath_0")],
                [InlineKeyboardButton("😤 Asab/g'azab", callback_data="breath_1")],
                [InlineKeyboardButton("😴 Uxlay olmayapman", callback_data="breath_2")],
                [InlineKeyboardButton("😓 Stress/zo'riqish", callback_data="breath_3")]]))
        return

    # Motivatsiya
    if txt == "💪 Motivatsiya":
        u["stage"] = "chat"
        u["history"] = []
        motivatsiya_prompt = "Menga kuchli motivatsiya ber, hayotga yangi ko'z bilan qarashimga yordam ber"
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        reply, u["history"] = await get_ai_response(u["history"], motivatsiya_prompt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    # Psixolog
    if txt == "👨‍⚕️ Psixolog":
        await update.message.reply_text(
            "👨‍⚕️ *Mutaxassis psixolog bilan bog'lanish*\n\n"
            "Ba'zida professional yordam olish eng to'g'ri qadam. "
            "Bu kuchsizlik emas — bu *jasorat* belgisi! 💪\n\n"
            "Psixolog raqamini olish uchun tugmani bosing:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📞 Psixolog raqamini olish", url="https://t.me/boburxoja")
            ]]), parse_mode="Markdown")
        return

    # Mening holatim
    if txt == "📊 Mening holatim":
        moods = u.get("moods", [])
        chats = len(u.get("history", []))
        if not moods:
            await update.message.reply_text(
                "📊 Hali ma'lumot yo'q.\n\nKayfiyatingizni kuzatib boring — vaqt o'tishi bilan o'sishingizni ko'rasiz! 🌱",
                reply_markup=main_menu())
        else:
            avg = sum(m["score"] for m in moods) / len(moods)
            last = moods[-1]
            trend = "📈 O'syapti" if len(moods) > 1 and moods[-1]["score"] >= moods[-2]["score"] else "📉 Tushyapti"
            await update.message.reply_text(
                f"📊 *Sizning holatiz:*\n\n"
                f"😊 Kayfiyat yozuvlari: {len(moods)} ta\n"
                f"📈 O'rtacha ball: {avg:.1f}/5\n"
                f"🕐 Oxirgi kayfiyat: {last['label']} ({last['date']})\n"
                f"📊 Tendensiya: {trend}\n\n"
                f"💬 Suhbatlar: {chats // 2} ta\n\n"
                f"Davom eting — har kuni bir qadam! 🌟",
                reply_markup=main_menu(), parse_mode="Markdown")
        return

    # Dardimni aytay — diagnostika
    if txt == "💬 Dardimni aytay":
        u["stage"] = "listening"
        u["history"] = []
        await update.message.reply_text(
            "💚 Men sizni tinglayman...\n\n"
            "Nima qiynayapti? Ochiq gapirishingiz mumkin — "
            "bu yerda hech kim sizni hukm qilmaydi. 🤝",
            reply_markup=back_menu())
        return

    # Suhbat davomi
    if u["stage"] == "listening":
        u["problem"] = txt
        # Muammoni aniqlash
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        problem_type = await diagnose_problem(txt)

        # Inqiroz holati
        if problem_type == "INQIROZ":
            await update.message.reply_text(
                "💙 Sizi eshityapman. Bu juda og'ir payt...\n\n"
                "Lekin siz yolg'iz emassiz. Hoziroq mutaxassis bilan gaplashing — "
                "ular sizga yordam beradi:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📞 Darhol yordam olish", url="https://t.me/boburxoja")
                ]]))
            return

        # Mos yo'nalish taklif qilish
        tavsiyalar = {
            "STRESS": "💆 Stress darajangiz yuqori ko'rinadi. Avval **nafas texnikasi** bilan tanangizni tinchlaylik, keyin muammoni birga ko'rib chiqamiz.",
            "TASHVISH": "🤗 Tashvish va xavotir odamni charchatadi. Sizga **CBT texnikasi** yordam beradi — fikrlarni tartibga solaylik.",
            "TUSHKUNLIK": "💙 Kayfiyat tushishi og'ir holat. **Minnatdorlik texnikasi** va motivatsiya bilan birga chiqamiz bu holatdan.",
            "YOLG'IZLIK": "🤝 Yolg'izlik og'ir his. Men siz bilan birman. Gaplashaylik — siz tushunilishga loyiqsiz.",
            "G'AZAB": "😤 G'azab ichida yonish — bu charchash belgisi. **Nafas texnikasi** bilan boshlaylik.",
            "UYQU": "😴 Uyqu muammolari juda ko'p narsaga ta'sir qiladi. **4-7-8 nafas texnikasi** yordam beradi.",
            "ISHONCH": "💪 O'zingizga ishonch — bu o'rgatiladi. Kuchli tomonlaringizni birga topamiz.",
            "MUNOSABAT": "💔 Munosabat muammolari juda og'ir. Men sizni tinglayman — batafsil aytib bering."
        }

        tavsiya = tavsiyalar.get(problem_type, "💚 Tushundim. Birga hal qilamiz.")
        u["stage"] = "chat"

        await update.message.reply_text(tavsiya, parse_mode="Markdown", reply_markup=back_menu())
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # AI dan chuqur javob olish
        reply, u["history"] = await get_ai_response(
            u["history"],
            f"Foydalanuvchi muammosi: {txt}\nMuammo turi: {problem_type}\n"
            f"Unga mos terapevtik yondashuv bilan yordam ber. "
            f"Avval empatiya ko'rsat, keyin aniq savol ber."
        )
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    # Davomiy suhbat
    if u["stage"] == "chat":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        reply, u["history"] = await get_ai_response(u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    # Agar boshqa narsa yozsa
    await update.message.reply_text(
        "Men sizi tinglayman 💚\n\nQuyidagilardan birini tanlang yoki dardingizni yozing:",
        reply_markup=main_menu())

async def mood_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    score = int(q.data.split("_")[1])
    labels = {5:"Ajoyib 😄", 4:"Yaxshi 🙂", 3:"O'rtacha 😐", 2:"Yomon 😔", 1:"Juda yomon 😢"}
    u["moods"].append({"score": score, "label": labels[score], "date": datetime.now().strftime("%d.%m %H:%M")})

    responses = {
        5: "😄 Ajoyib! Bu energiyani saqlang!\n\nBugun nimaga minnatdorsiz? 3 ta narsa ayting — bu his-tuyg'uni mustahkamlaydi! 💛",
        4: "🙂 Yaxshi! Shu holatni qadrlang.\n\nBugun o'zingiz uchun bitta yaxshi narsa qiling — nima bo'ladi?",
        3: "😐 O'rtacha... Bu holat o'tib ketadi.\n\nNima sizni o'rtacha his qildiryapti? Bitta sabab aytib bering.",
        2: "😔 Qiyin payt, lekin yolg'iz emassiz.\n\nNima bo'ldi bugun? Menga ayting — birga o'ylab ko'ramiz. 💙",
        1: "😢 Bu juda og'ir...\n\nSiz bilan birman. Nima qiynayapti? Ochiq gapirishingiz mumkin — men eshityapman. 💙"
    }

    u["stage"] = "chat"
    await q.edit_message_text(responses[score])
    await context.bot.send_message(q.message.chat_id, "Davom etish:", reply_markup=back_menu())

    if score <= 2:
        await context.bot.send_message(
            q.message.chat_id,
            "Agar juda og'ir bo'lsa — psixolog bilan gaplashing:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📞 Psixolog raqamini olish", url="https://t.me/boburxoja")
            ]]))

MEDS = [
    ("🧘 Tana skaneri (5 daqiqa)",
     "Tanangizni bosidan oyoqlarigacha skanerlaylik:\n\n"
     "1️⃣ Qulay joyda o'tiring yoki yoting\n"
     "2️⃣ Ko'zingizni yuming\n"
     "3️⃣ Boshingizdan boshlang — qayerda taranglik bor?\n"
     "4️⃣ Yelkalar... Ko'krak... Qorin...\n"
     "5️⃣ Oyoqlaringizgacha — har joyda 10 soniya to'xtang\n\n"
     "⏱ 5 daqiqa. Shoshilmang. Hozir boshlang. 🙏"),
    ("🌊 Xotirjamlik (3 daqiqa)",
     "Ko'zingizni yumib, dengiz qirg'og'ini tasavvur qiling:\n\n"
     "🌊 Har nafas — to'lqin keladi\n"
     "🌊 Har chiqarish — to'lqin ketadi\n"
     "💭 Fikrlar kelsa — to'lqin olib ketsin\n"
     "☁️ Siz qirg'oqda — xotirjam, xavfsiz\n\n"
     "⏱ 3 daqiqa. Hoziroq boshlang. 💙"),
    ("☀️ Ertalab zaryadka (2 daqiqa)",
     "Yangi kunni kuch bilan boshlang:\n\n"
     "1️⃣ O'rningizdan turing\n"
     "2️⃣ Qo'llarni osmonga ko'taring\n"
     "3️⃣ 5 marta chuqur nafas oling\n"
     "4️⃣ Bugun 1 ta maqsad belgilang\n"
     "5️⃣ O'zingizga: 'Men bugunni yaxshi o'tkazaman!' — deyish\n\n"
     "⏱ 2 daqiqa. Har kuni! 💚"),
    ("🌙 Kechki tinchlanish (5 daqiqa)",
     "Kunni tinch yakunlash uchun:\n\n"
     "1️⃣ Yotib oling\n"
     "2️⃣ Bugun bo'lgan 3 ta yaxshi narsani o'ylang\n"
     "3️⃣ Tanangizni bo'shashtirib, sekin nafas oling\n"
     "4️⃣ Ertangi kun haqida xotirjam o'ylang\n"
     "5️⃣ 'Bugun yaxshi kun bo'ldi' — deyish\n\n"
     "⏱ 5 daqiqa. Har kechasi. 🌙")
]

async def med_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{MEDS[idx][0]}\n\n{MEDS[idx][1]}")
    await context.bot.send_message(
        q.message.chat_id,
        "✅ Ajoyib tanlov! Boshlang — men kutib turaman. 💚\n\n"
        "Tugagach yozing: natijangiz qanday bo'ldi?",
        reply_markup=back_menu())

BREATHS = [
    ("😰 Tashvish/xavotir uchun — 4-7-8 nafas",
     "Bu texnika tashvishni 5 daqiqada kamaytiradi:\n\n"
     "👃 4 soniya — burun orqali nafas OLING\n"
     "⏸ 7 soniya — ushlab TURING\n"
     "💨 8 soniya — og'iz orqali sekin CHIQARING\n\n"
     "🔁 4 marta takrorlang\n\n"
     "Hozir boshlang... Men kutib turaman. 💙"),
    ("😤 Asab/g'azab uchun — Quti nafas",
     "G'azabni 3 daqiqada bosing:\n\n"
     "▶️ 4 soniya — nafas oling\n"
     "⏸ 4 soniya — ushlab turing\n"
     "◀️ 4 soniya — chiqaring\n"
     "⏸ 4 soniya — ushlab turing\n\n"
     "🔁 5 marta takrorlang\n\n"
     "Kvadrat chizing — har tomoni 4 soniya. 📦"),
    ("😴 Uxlay olmayotganlar uchun — 4-7-8",
     "Uxlashdan oldin:\n\n"
     "👃 4 soniya — nafas oling\n"
     "⏸ 7 soniya — ushlab turing\n"
     "💨 8 soniya — chiqaring\n\n"
     "🔁 4-6 marta takrorlang\n\n"
     "Ko'zingizni yuming, xonani qorong'i qiling. 🌙\n"
     "Bu arxeologik usul — 10-15 daqiqada uxlatadi!"),
    ("😓 Stress/zo'riqish uchun — Tez tinchlash",
     "1 daqiqada stressni kamaytiring:\n\n"
     "▶️ 2 soniya — nafas oling\n"
     "◀️ 4 soniya — sekin chiqaring\n\n"
     "🔁 6 marta = 1 daqiqa\n\n"
     "Chiqarish nafasdan uzun bo'lishi — parasimpatik sistemani yoqadi.\n"
     "Hoziroq ishlating! ⚡")
]

async def breath_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{BREATHS[idx][0]}\n\n{BREATHS[idx][1]}")
    await context.bot.send_message(
        q.message.chat_id,
        "⏱ Boshlang! Tugagach natijangizni yozing — qanday his qildingiz? 💚",
        reply_markup=back_menu())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Bu buyruq faqat admin uchun! 🔒")
        return
    total = len(users)
    total_moods = sum(len(u["moods"]) for u in users.values())
    total_chats = sum(len(u["history"]) for u in users.values())
    active = sum(1 for u in users.values() if u.get("stage") != "start")
    await update.message.reply_text(
        f"📊 JAST Statistika:\n\n"
        f"👤 Jami foydalanuvchilar: {total}\n"
        f"🟢 Faol foydalanuvchilar: {active}\n"
        f"💬 Suhbat xabarlari: {total_chats}\n"
        f"😊 Kayfiyat yozuvlari: {total_moods}")

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
