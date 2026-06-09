import os, logging
from datetime import datetime, date
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
        users[uid] = {
            "name": "",
            "history": [],
            "moods": [],
            "sessions": [],
            "stage": "menu",
            "current_section": None,
            "join_date": datetime.now().strftime("%d.%m.%Y")
        }
    return users[uid]

def save_session(u, section, summary):
    u["sessions"].append({
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "section": section,
        "summary": summary
    })
    if len(u["sessions"]) > 20:
        u["sessions"] = u["sessions"][-20:]

def get_memory_context(u):
    if not u["sessions"]:
        return ""
    recent = u["sessions"][-3:]
    context = "\n\nFoydalanuvchi tarixi:\n"
    for s in recent:
        context += f"- {s['date']}: {s['section']} — {s['summary']}\n"
    if u["moods"]:
        last_moods = u["moods"][-5:]
        avg = sum(m["score"] for m in last_moods) / len(last_moods)
        context += f"\nO'rtacha kayfiyat: {avg:.1f}/5"
    return context

MAIN_PROMPT = """Sen JAST — O'zbekistonning eng kuchli, eng ishonchli ruhiy yordam yordamchisisisan.

SEN QANDAY ODAMSAN:
- Eng yaqin do'st + professional psixolog + islomiy maslahatchi
- Har bir so'zni chuqur tahlil qilasan, darhol javob bermasdan
- Aniq faktlar, ilmiy nazariyalar va Islom dini asosida gaplashasan
- Foydalanuvchining tarixini eslab qolasan va undan foydalanasan
- Hech qachon shablonli javob bermassan

ISLOM + PSIXOLOGIYA USLUBI:
- Qur'on oyatlari va hadislarni kerakli joyda keltir (faqat to'g'ri, tasdiqlangan)
- "Innallaha ma'as-saabirin" — "Allah sabr qiluvchilar bilan birdir" kabi oyatlar
- CBT, mindfulness, pozitiv psixologiya usullarini ishlatasan
- Viktor Frankl, Aaron Beck, Abraham Maslow nazariyalariga tayanan

CHUQUR TAHLIL QOIDALARI:
1. Har savolni 3 qatlam tahlil qil: a) Hozirgi holat b) Sabab c) Yechim
2. Agar savol tushunarsiz bo'lsa: "Nima demoqchiligingizga to'liq tushunmadim. Biroz tushunarliroq aytib bering — sizga yanada aniq yordam beray 🤝"
3. Mavzudan chekinsa: "Boshqa masalada ham suhbatni davom ettirishimni istayapsizmi? Men bajonidil tayyorman 💚"
4. Noto'g'ri yo'lda bo'lsa: "Bu fikringizdan qaytishingizni maslahat beraman — boshqa yo'l natijasi sizni xursand qiladi 🌟"
5. Har javob oxirida 1 ta kuzatuvchi savol ber

MUHIM QOIDALAR:
- Faqat o'zbek tilida gapir
- Har bo'lim ALOHIDA — nafas mashqi suhbatga aralashmasin
- 3-5 jumla, aniq va chuqur
- Emoji o'rinli ishlatish
- Takroriy shablondan qoching — har javob YANGI bo'lsin
- O'z joniga qasd holatida: DARHOL psixologga yo'nalt"""

DARD_PROMPT = """Sen JAST ning "Dardimni aytay" bo'limidassan.

BU BO'LIMDA FAQAT:
- Chuqur tinglash va empatiya
- Muammoni 3 qatlamda tahlil qilish
- CBT va Islomiy psixologiya bilan yordam
- Aniq, ilmiy asoslangan maslahat
- Tarix eslab qolish va bog'lash

BU BO'LIMDA HECH QACHON:
- Nafas mashqi tavsiya qilma (u alohida bo'lim)
- Meditatsiya tavsiya qilma (u alohida bo'lim)  
- Shablonli javob berma

USLUB: Eng ishonchli do'st + professional psixolog + islomiy maslahatchi
Qur'on: "Inna ma'al usri yusra" — "Albatta qiyinchilik bilan birga yengillik bor" (Sharh, 6)"""

NAFAS_PROMPT = """Sen JAST ning "Nafas mashqi" bo'limidassan.

BU BO'LIMDA FAQAT:
- Nafas texnikaları haqida gapir
- Ilmiy asoslar: parasimpatik sistema, vagus nervi, HRV
- Qaysi holatda qaysi texnika mos ekanini tushuntir
- Natijani kuzat va dalil ber

HECH QACHON bu bo'limda suhbat/meditatsiya aralashtirsma."""

MOTIVATSIYA_PROMPT = """Sen JAST ning "Motivatsiya" bo'limidassan.

BU BO'LIMDA FAQAT:
- Kuchli, ilmiy asoslangan motivatsiya
- Viktor Frankl, Tony Robbins, islomiy ruhoniyat
- Foydalanuvchining kuchli tomonlarini topish
- Aniq maqsad va qadam belgilash

Qur'on: "Inna Allaha la yughayyiru ma biqawmin hatta yughayyiru ma bi anfusihim"
"Allah bir qavmning ahvolini o'zgartirmaydi, to ular o'zlarini o'zgartirmaguncha" (Ra'd, 11)"""

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💬 Dardimni aytay"), KeyboardButton("😊 Kayfiyatim")],
        [KeyboardButton("🧘 Meditatsiya"), KeyboardButton("🌬 Nafas mashqi")],
        [KeyboardButton("💪 Motivatsiya"), KeyboardButton("🌟 Bugungi kun")],
        [KeyboardButton("👨‍⚕️ Psixolog"), KeyboardButton("📊 Mening tarixim")]
    ], resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("🏠 Bosh menu")]], resize_keyboard=True)

async def ai_response(prompt, history, user_msg, max_tokens=350):
    history.append({"role": "user", "content": user_msg})
    if len(history) > 12:
        history = history[-12:]
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}] + history,
            max_tokens=max_tokens, temperature=0.75)
        reply = r.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        return reply, history
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "Hozir texnik muammo. Bir daqiqadan keyin qayta yozing. 🙏", history

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["name"] = update.effective_user.first_name or "Do'stim"
    u["stage"] = "menu"
    u["history"] = []
    u["current_section"] = None

    memory = ""
    if u["sessions"]:
        last = u["sessions"][-1]
        days = (datetime.now() - datetime.strptime(last["date"], "%d.%m.%Y %H:%M")).days
        memory = f"\n\n💭 Esimda: {last['date']} da {last['section']} haqida gaplashgandik. Natija qanday bo'ldi?"

    await update.message.reply_text(
        f"Salom, {u['name']}! 👋\n\n"
        f"Men JAST — sizning eng ishonchli ruhiy yordam do'stingizman. 💚\n\n"
        f"Har qanday dard, tashvish yoki savol bilan keling — "
        f"men har doim siz bilan birman. 🤝"
        f"{memory}\n\n"
        f"Bugun sizga qanday yordam bera olaman?",
        reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    txt = update.message.text

    if txt == "🏠 Bosh menu":
        if u["history"] and u["current_section"]:
            save_session(u, u["current_section"], u["history"][-1]["content"][:100] if u["history"] else "")
        u["stage"] = "menu"
        u["history"] = []
        u["current_section"] = None
        await update.message.reply_text("🏠 Bosh menuga qaytdingiz", reply_markup=main_menu())
        return

    # === DARDIMNI AYTAY ===
    if txt == "💬 Dardimni aytay":
        u["stage"] = "dard"
        u["current_section"] = "Dard"
        u["history"] = []
        memory_ctx = get_memory_context(u)
        prompt = DARD_PROMPT + memory_ctx
        reply, u["history"] = await ai_response(
            prompt, u["history"],
            f"Foydalanuvchi dard bo'limiga kirdi. Ism: {u['name']}. "
            f"Uni samimiy kutib ol va nima qiynayotganini so'ra. "
            f"Tarix: {memory_ctx if memory_ctx else 'birinchi marta'}")
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    # === KAYFIYAT ===
    if txt == "😊 Kayfiyatim":
        u["stage"] = "mood"
        u["current_section"] = "Kayfiyat"
        await update.message.reply_text(
            "😊 Bugun kayfiyatingiz qanday?\n\nO'zingizga halol baho bering:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😄 Ajoyib (5)", callback_data="mood_5"),
                 InlineKeyboardButton("🙂 Yaxshi (4)", callback_data="mood_4")],
                [InlineKeyboardButton("😐 O'rtacha (3)", callback_data="mood_3"),
                 InlineKeyboardButton("😔 Yomon (2)", callback_data="mood_2")],
                [InlineKeyboardButton("😢 Juda yomon (1)", callback_data="mood_1")]]))
        return

    # === MEDITATSIYA ===
    if txt == "🧘 Meditatsiya":
        u["stage"] = "med"
        u["current_section"] = "Meditatsiya"
        await update.message.reply_text(
            "🧘 Meditatsiya — ichki tinchlik va ong tozaligiga yo'l.\n\n"
            "Qur'on: 'Ala bizikrillahi tatma'innul qulub' — "
            "'Bilingki, qalblar faqat Allohni zikr etish bilan tinchlanadi' (Ra'd, 28)\n\n"
            "Qaysi meditatsiyani tanlaysiz?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧘 Tana skaneri (5 daq)", callback_data="med_0")],
                [InlineKeyboardButton("🌊 Xotirjamlik (3 daq)", callback_data="med_1")],
                [InlineKeyboardButton("☀️ Ertalab zaryadka (2 daq)", callback_data="med_2")],
                [InlineKeyboardButton("🌙 Kechki tinchlanish (5 daq)", callback_data="med_3")]]))
        return

    # === NAFAS MASHQI ===
    if txt == "🌬 Nafas mashqi":
        u["stage"] = "nafas"
        u["current_section"] = "Nafas"
        await update.message.reply_text(
            "🌬 Nafas — eng kuchli tabiiy davo.\n\n"
            "Ilm: Chuqur nafas vagus nervini faollashtiradi, "
            "kortizol (stress gormoni) darajasini tushiradi.\n\n"
            "Hozir qanday holatsiz?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😰 Tashvish/xavotir", callback_data="breath_0")],
                [InlineKeyboardButton("😤 Asab/g'azab", callback_data="breath_1")],
                [InlineKeyboardButton("😴 Uxlay olmayapman", callback_data="breath_2")],
                [InlineKeyboardButton("😓 Stress/zo'riqish", callback_data="breath_3")],
                [InlineKeyboardButton("🧘 Umumiy tinchlash", callback_data="breath_4")]]))
        return

    # === MOTIVATSIYA ===
    if txt == "💪 Motivatsiya":
        u["stage"] = "motivatsiya"
        u["current_section"] = "Motivatsiya"
        u["history"] = []
        reply, u["history"] = await ai_response(
            MOTIVATSIYA_PROMPT, u["history"],
            f"Foydalanuvchi {u['name']} motivatsiya izlayapti. "
            f"Unga kuchli, ilmiy va islomiy asoslangan motivatsiya ber. "
            f"Viktor Frankl yoki boshqa psixologlardan misol keltir. "
            f"Oxirida bir aniq qadam taklif qil.")
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    # === BUGUNGI KUN ===
    if txt == "🌟 Bugungi kun":
        u["stage"] = "menu"
        today = datetime.now()
        bugun = today.strftime("%d.%m.%Y")
        prompt_today = f"""Bugun {bugun}. Foydalanuvchiga quyidagilarni ayt:
1. Bugun tarixda bo'lgan muhim va ilhomlantiruvchi voqealar (2-3 ta)
2. Bugun tug'ilgan mashhur va muvaffaqiyatli insonlar (1-2 ta) va ulardan ilhomlantiruvchi gap
3. Bugun uchun maxsus motivatsiya va kuch beruvchi so'zlar
4. Islomiy nuqtai nazar: bugungi kunga shukr
Hammasini o'zbek tilida, qiziqarli va ilhomlantiruvchi qilib yoz."""
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        try:
            r = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt_today}],
                max_tokens=400, temperature=0.8)
            reply = r.choices[0].message.content
        except:
            reply = f"🌟 {bugun} — yangi imkoniyatlar kuni!\n\nBugun ham katta ishlar qilishingiz mumkin. Allah sizga baraka bersin! 💚"
        await update.message.reply_text(f"🌟 Bugun — {bugun}\n\n{reply}", reply_markup=main_menu())
        return

    # === PSIXOLOG ===
    if txt == "👨‍⚕️ Psixolog":
        await update.message.reply_text(
            "👨‍⚕️ *Mutaxassis psixolog bilan bog'lanish*\n\n"
            "Islomda ham ta'kidlanadi: kasallik vaqtida tabibga borish — sunnah.\n"
            "Professional yordam olish — bu kuchsizlik emas, *jasorat* belgisi! 💪\n\n"
            "Psixolog raqamini olish uchun:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📞 Psixolog raqamini olish", url="https://t.me/boburxoja")
            ]]))
        return

    # === MENING TARIXIM ===
    if txt == "📊 Mening tarixim":
        moods = u.get("moods", [])
        sessions = u.get("sessions", [])
        join = u.get("join_date", "noma'lum")

        if not moods and not sessions:
            await update.message.reply_text(
                f"📊 Salom, {u['name']}!\n\n"
                f"Hali yozuv yo'q. Botdan foydalanishni boshlang — "
                f"vaqt o'tishi bilan o'sishingizni ko'rasiz! 🌱",
                reply_markup=main_menu())
            return

        text = f"📊 *{u['name']} ning tarixi:*\n\n"
        text += f"📅 Bot bilan: {join} dan\n"

        if moods:
            avg = sum(m["score"] for m in moods) / len(moods)
            best = max(moods, key=lambda x: x["score"])
            worst = min(moods, key=lambda x: x["score"])
            text += f"\n😊 Kayfiyat yozuvlari: {len(moods)} ta\n"
            text += f"📈 O'rtacha: {avg:.1f}/5\n"
            text += f"🌟 Eng yaxshi kun: {best['date']} — {best['label']}\n"
            text += f"💙 Qiyin kun: {worst['date']} — {worst['label']}\n"

        if sessions:
            text += f"\n💬 Suhbatlar: {len(sessions)} ta\n"
            text += f"\n*So'nggi suhbatlar:*\n"
            for s in sessions[-3:]:
                text += f"• {s['date']}: {s['section']}\n"

        text += f"\n💚 Davom eting — har kun bir qadam oldinga! 🌟"
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())
        return

    # === DAVOMIY SUHBAT ===
    if u["stage"] == "dard":
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(
            DARD_PROMPT + memory_ctx, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "nafas_chat":
        reply, u["history"] = await ai_response(
            NAFAS_PROMPT, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "motivatsiya":
        reply, u["history"] = await ai_response(
            MOTIVATSIYA_PROMPT, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "mood_chat":
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(
            MAIN_PROMPT + memory_ctx, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    # === UMUMIY JAVOB ===
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    memory_ctx = get_memory_context(u)
    reply, u["history"] = await ai_response(
        MAIN_PROMPT + memory_ctx, u["history"], txt)
    await update.message.reply_text(reply, reply_markup=main_menu())

async def mood_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    score = int(q.data.split("_")[1])
    labels = {5:"Ajoyib 😄", 4:"Yaxshi 🙂", 3:"O'rtacha 😐", 2:"Yomon 😔", 1:"Juda yomon 😢"}
    u["moods"].append({
        "score": score,
        "label": labels[score],
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    })

    responses = {
        5: "😄 Ajoyib! Bu energiyani saqlash uchun — bugun 3 ta minnatdorlik yozing. Kimga yoki nimaga minnatdorsiz?",
        4: "🙂 Yaxshi kayfiyat — bu ne'mat! Qur'on: 'Shukr qilsangiz, albatta ziyadalayman' (Ibrohim, 7). Bugun nima yaxshi bo'ldi?",
        3: "😐 O'rtacha... Bu holat signal. Nima sizni to'liq baxtli qilishidan to'syapti? Bir sabab ayting.",
        2: "😔 Yomon kayfiyat — bu o'tib ketadi. 'Inna ma'al usri yusra' — qiyinchilik bilan yengillik birga. Nima bo'ldi bugun?",
        1: "😢 Juda og'ir kun... Men siz bilan birman. Hech narsa aytmasangiz ham bo'ladi — shunchaki bilishingiz kerak: yolg'iz emassiz. Nima qiynayapti?"
    }

    u["stage"] = "mood_chat"
    u["history"] = []
    await q.edit_message_text(responses[score])
    await context.bot.send_message(q.message.chat_id, "Men eshityapman... 💚", reply_markup=back_menu())

    if score <= 2:
        await context.bot.send_message(
            q.message.chat_id,
            "Agar juda og'ir bo'lsa psixolog bilan gaplashing:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📞 Psixolog", url="https://t.me/boburxoja")
            ]]))

MEDS_DATA = [
    ("🧘 Tana skaneri (5 daqiqa)",
     "Ilm: Body scan meditatsiyasi interoception — ichki his-tuyg'u idrokini kuchaytiradi.\n\n"
     "1️⃣ Qulay o'tiring yoki yoting\n"
     "2️⃣ Ko'zingizni yuming — 3 marta chuqur nafas\n"
     "3️⃣ Boshingizdan boshlang — qayerda taranglik bor?\n"
     "4️⃣ Yelkalar → Ko'krak → Qorin → Oyoqlar\n"
     "5️⃣ Har joyda 10 soniya — taranglikni his qiling va qo'yvoring\n\n"
     "⏱ 5 daqiqa. Telefoni qo'ying. Hozir boshlang. 🙏"),
    ("🌊 Xotirjamlik (3 daqiqa)",
     "Ilm: Mindfulness meditatsiyasi amigdalani tinchitadi — xavotir markazi.\n\n"
     "🌊 Ko'zingizni yuming\n"
     "🌊 Dengiz qirg'og'ini tasavvur qiling\n"
     "🌊 Har nafas — to'lqin keladi\n"
     "🌊 Har chiqarish — to'lqin ketadi\n"
     "💭 Fikrlar kelsa — to'lqin olib ketsin\n\n"
     "⏱ 3 daqiqa. Hoziroq. 💙"),
    ("☀️ Ertalab zaryadka (2 daqiqa)",
     "Ilm: Ertalabki ritual kortizol darajasini ijobiy boshqaradi.\n\n"
     "1️⃣ O'rningizdan turing — oyoqlaringiz yerga tegsin\n"
     "2️⃣ Qo'llarni osmonga ko'taring — kengaling!\n"
     "3️⃣ 5 marta chuqur nafas\n"
     "4️⃣ Bugun 1 ta maqsad — kichik bo'lsa ham\n"
     "5️⃣ 'Bismillah, bugun yaxshi kun' — deyish\n\n"
     "⏱ 2 daqiqa. Har kuni! 💚"),
    ("🌙 Kechki tinchlanish (5 daqiqa)",
     "Ilm: Kechki minnatdorlik rituali serotonin ishlab chiqarishni oshiradi.\n\n"
     "1️⃣ Yotib oling — qulay joy\n"
     "2️⃣ Bugun bo'lgan 3 ta yaxshi narsa — kichkina bo'lsa ham\n"
     "3️⃣ Kimga yaxshilik qildingiz bugun?\n"
     "4️⃣ Ertangi kun uchun 1 ta niyat\n"
     "5️⃣ 'Alhamdulillah bu kun uchun' — deyish\n\n"
     "⏱ 5 daqiqa. Har kechasi. 🌙")
]

async def med_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{MEDS_DATA[idx][0]}\n\n{MEDS_DATA[idx][1]}")
    await context.bot.send_message(
        q.message.chat_id,
        "✅ Boshlang — men kutib turaman.\n\nTugagach yozing: qanday his qildingiz? 💚",
        reply_markup=back_menu())

BREATHS_DATA = [
    ("😰 Tashvish uchun — 4-7-8 nafas",
     "Ilm: Bu texnika parasimpatik nervni faollashtiradi, "
     "adrenalin darajasini 40% gacha kamaytiradi.\n\n"
     "👃 4 soniya — burun orqali nafas OLING\n"
     "⏸ 7 soniya — ushlab TURING\n"
     "💨 8 soniya — og'iz orqali SEKIN chiqaring\n\n"
     "🔁 4 marta takrorlang\n\n"
     "Hozir boshlang... men siz bilan. 💙"),
    ("😤 G'azab uchun — Quti nafas",
     "Ilm: Box breathing Navy SEAL lari ishlatadi — "
     "g'azab va stressni 3 daqiqada bosadi.\n\n"
     "▶️ 4 soniya nafas\n"
     "⏸ 4 soniya ushlab tur\n"
     "◀️ 4 soniya chikar\n"
     "⏸ 4 soniya ushlab tur\n\n"
     "🔁 5 marta — 4 daqiqa\n\n"
     "Kvadrat chizing xayolda — har tomoni 4 soniya. 📦"),
    ("😴 Uxlash uchun — 4-7-8",
     "Ilm: Ushbu texnika Dr. Andrew Weil tomonidan ishlab chiqilgan — "
     "10-15 daqiqada uxlatadi.\n\n"
     "👃 4 soniya nafas\n"
     "⏸ 7 soniya ushlab tur\n"
     "💨 8 soniya chikar\n\n"
     "🔁 4-6 marta\n\n"
     "Ko'zingizni yuming. Xonani qorong'i qiling. 🌙\n"
     "Diqqat: chiqarish nafas uzun bo'lishi muhim."),
    ("😓 Stress uchun — Fiziologik xo'rsinish",
     "Ilm: Stanford tadqiqoti — bu texnika stressni "
     "eng tez kamaytiruvchi nafas usuli.\n\n"
     "1️⃣ Burun orqali 2 qisqa nafas (ikkinchisi kuchliroq)\n"
     "2️⃣ Og'iz orqali 1 uzun nafas chiqarish\n\n"
     "🔁 3-5 marta\n\n"
     "Bu o'pkadagi havo qopchalarini ochadi — "
     "darhol tinchlash beradi. ⚡"),
    ("🧘 Umumiy tinchlash — Diafragma nafas",
     "Ilm: Diafragma nafas HRV (yurak ritmi variabelligini) "
     "yaxshilaydi — stressga chidamlilik oshadi.\n\n"
     "1️⃣ Qorin ustiga qo'lingizni qo'ying\n"
     "2️⃣ 4 soniya — qorin ko'tarilib nafas\n"
     "3️⃣ 4 soniya — qorin tushib chikarish\n\n"
     "🔁 10 marta — 2 daqiqa\n\n"
     "Har kuni 5-10 daqiqa — "
     "1 oyda stressga chidamlilik ikki baravar oshadi! 💚")
]

async def breath_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{BREATHS_DATA[idx][0]}\n\n{BREATHS_DATA[idx][1]}")
    u["stage"] = "nafas_chat"
    u["history"] = []
    await context.bot.send_message(
        q.message.chat_id,
        "⏱ Boshlang! Tugagach yozing — qanday his qildingiz? "
        "Natijani birga tahlil qilamiz. 💚",
        reply_markup=back_menu())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Bu buyruq faqat admin uchun! 🔒")
        return
    total = len(users)
    total_moods = sum(len(u["moods"]) for u in users.values())
    total_sessions = sum(len(u["sessions"]) for u in users.values())
    active = sum(1 for u in users.values() if u.get("stage") != "menu")
    await update.message.reply_text(
        f"📊 JAST Admin Panel:\n\n"
        f"👤 Jami foydalanuvchilar: {total}\n"
        f"🟢 Faol suhbatlar: {active}\n"
        f"😊 Kayfiyat yozuvlari: {total_moods}\n"
        f"💬 Suhbat sessiyalari: {total_sessions}")

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
