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
        users[uid] = {"name":"","history":[],"moods":[],"sessions":[],"stage":"menu","current_section":None,"join_date":datetime.now().strftime("%d.%m.%Y")}
    return users[uid]

def save_session(u, section, summary):
    u["sessions"].append({"date":datetime.now().strftime("%d.%m.%Y %H:%M"),"section":section,"summary":summary})
    if len(u["sessions"]) > 20:
        u["sessions"] = u["sessions"][-20:]

def get_memory_context(u):
    if not u["sessions"]:
        return ""
    context = "\n\nFoydalanuvchi tarixi:\n"
    for s in u["sessions"][-3:]:
        context += f"- {s['date']}: {s['section']} — {s['summary']}\n"
    if u["moods"]:
        avg = sum(m["score"] for m in u["moods"][-5:]) / min(len(u["moods"]),5)
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
- CBT, mindfulness, pozitiv psixologiya usullarini ishlatasan
- Viktor Frankl, Aaron Beck, Abraham Maslow nazariyalariga tayanan

CHUQUR TAHLIL QOIDALARI:
1. Har savolni 3 qatlam tahlil qil: a) Hozirgi holat b) Sabab c) Yechim
2. Agar savol tushunarsiz bolsa: "Nima demoqchiligingizga toliq tushunmadim. Biroz tushunarliroq aytib bering — sizga yanada aniq yordam beray"
3. Mavzudan chekinsa: "Boshqa masalada ham suhbatni davom ettirishimni istayapsizmi? Men bajonidil tayyorman"
4. Notogri yolda bolsa: "Bu fikringizdan qaytishingizni maslahat beraman — boshqa yol natijasi sizni xursand qiladi"
5. Har javob oxirida 1 ta kuzatuvchi savol ber

MUHIM QOIDALAR:
- Faqat uzbek tilida gapir
- Har bolim ALOHIDA — nafas mashqi suhbatga aralashmasin
- 3-5 jumla, aniq va chuqur
- Takroriy shablondan qoching — har javob YANGI bolsin
- Ozjoniga qasd holatida: DARHOL psixologga yonalt"""

DARD_PROMPT = """Sen JAST ning Dardimni aytay bolimidasan.

BU BOLIMDA FAQAT:
- Chuqur tinglash va empatiya
- Muammoni 3 qatlamda tahlil qilish
- CBT va Islomiy psixologiya bilan yordam
- Aniq, ilmiy asoslangan maslahat

BU BOLIMDA HECH QACHON:
- Nafas mashqi tavsiya qilma
- Meditatsiya tavsiya qilma
- Shablonli javob berma

Quron: Inna maal usri yusra — Albatta qiyinchilik bilan birga yengillik bor (Sharh, 6)"""

NAFAS_PROMPT = """Sen JAST ning Nafas mashqi bolimidasan.
Faqat nafas texnikalari haqida gapir. Ilmiy asoslar: parasimpatik sistema, vagus nervi.
Qaysi holatda qaysi texnika mos ekanini tushuntir. Natijani kuzat."""

MOTIVATSIYA_PROMPT = """Sen JAST ning Motivatsiya bolimidasan.
Kuchli, ilmiy asoslangan motivatsiya ber. Viktor Frankl, Tony Robbins.
Quron: Allah bir qavmning ahvolini ozgartirmaydi, to ular ozlarini ozgartirmaguncha (Rad, 11)
Aniq maqsad va qadam belgilash. 4-5 jumla, kuchli va ilhomlantiruvchi."""

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Dardimni aytay"), KeyboardButton("Kayfiyatim")],
        [KeyboardButton("Meditatsiya"), KeyboardButton("Nafas mashqi")],
        [KeyboardButton("Motivatsiya"), KeyboardButton("Bugungi kun")],
        [KeyboardButton("Psixolog"), KeyboardButton("Mening tarixim")]
    ], resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("Bosh menu")]], resize_keyboard=True)

async def ai_response(prompt, history, user_msg, max_tokens=350):
    history.append({"role":"user","content":user_msg})
    if len(history) > 12:
        history = history[-12:]
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":prompt}]+history,
            max_tokens=max_tokens, temperature=0.75)
        reply = r.choices[0].message.content
        history.append({"role":"assistant","content":reply})
        return reply, history
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "Hozir texnik muammo. Qayta yozing.", history

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["name"] = update.effective_user.first_name or "Dostim"
    u["stage"] = "menu"
    u["history"] = []
    u["current_section"] = None
    memory = ""
    if u["sessions"]:
        last = u["sessions"][-1]
        memory = f"\n\nEsimda: {last['date']} da {last['section']} haqida gaplashgandik. Natija qanday boldi?"
    await update.message.reply_text(
        f"Salom, {u['name']}! \n\n"
        f"Men JAST — sizning eng ishonchli ruhiy yordam dostingizman.\n\n"
        f"Har qanday dard, tashvish yoki savol bilan keling — men har doim siz bilan birman."
        f"{memory}\n\n"
        f"Bugun sizga qanday yordam bera olaman?",
        reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    txt = update.message.text

    if txt == "Bosh menu":
        if u["history"] and u["current_section"]:
            save_session(u, u["current_section"], u["history"][-1]["content"][:100])
        u["stage"] = "menu"
        u["history"] = []
        u["current_section"] = None
        await update.message.reply_text("Bosh menuga qaytdingiz", reply_markup=main_menu())
        return

    if txt == "Dardimni aytay":
        u["stage"] = "dard"
        u["current_section"] = "Dard"
        u["history"] = []
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(
            DARD_PROMPT + memory_ctx, u["history"],
            f"Foydalanuvchi dard bolimiga kirdi. Ism: {u['name']}. Uni samimiy kutib ol va nima qiynayotganini so'ra.")
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if txt == "Kayfiyatim":
        u["stage"] = "mood"
        u["current_section"] = "Kayfiyat"
        await update.message.reply_text(
            "Bugun kayfiyatingiz qanday?\nOzingizga halol baho bering:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Ajoyib (5)", callback_data="mood_5"),
                 InlineKeyboardButton("Yaxshi (4)", callback_data="mood_4")],
                [InlineKeyboardButton("Ortacha (3)", callback_data="mood_3"),
                 InlineKeyboardButton("Yomon (2)", callback_data="mood_2")],
                [InlineKeyboardButton("Juda yomon (1)", callback_data="mood_1")]]))
        return

    if txt == "Meditatsiya":
        u["stage"] = "med"
        u["current_section"] = "Meditatsiya"
        await update.message.reply_text(
            "Meditatsiya — ichki tinchlik va ong tozaligiga yol.\n\n"
            "Quron: Ala bizikrillahi tatmainnul qulub — "
            "Bilingki, qalblar faqat Allohni zikr etish bilan tinchlanadi (Rad, 28)\n\n"
            "Qaysi meditatsiyani tanlaysiz?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Tana skaneri (5 daq)", callback_data="med_0")],
                [InlineKeyboardButton("Xotirjamlik (3 daq)", callback_data="med_1")],
                [InlineKeyboardButton("Ertalab zaryadka (2 daq)", callback_data="med_2")],
                [InlineKeyboardButton("Kechki tinchlanish (5 daq)", callback_data="med_3")]]))
        return

    if txt == "Nafas mashqi":
        u["stage"] = "nafas"
        u["current_section"] = "Nafas"
        await update.message.reply_text(
            "Nafas — eng kuchli tabiiy davo.\n\n"
            "Ilm: Chuqur nafas vagus nervini faollashtiradi, kortizol darajasini tushiradi.\n\n"
            "Hozir qanday holatsiz?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Tashvish/xavotir", callback_data="breath_0")],
                [InlineKeyboardButton("Asab/gazab", callback_data="breath_1")],
                [InlineKeyboardButton("Uxlay olmayapman", callback_data="breath_2")],
                [InlineKeyboardButton("Stress/zoriqish", callback_data="breath_3")],
                [InlineKeyboardButton("Umumiy tinchlash", callback_data="breath_4")]]))
        return

    if txt == "Motivatsiya":
        u["stage"] = "motivatsiya"
        u["current_section"] = "Motivatsiya"
        u["history"] = []
        reply, u["history"] = await ai_response(
            MOTIVATSIYA_PROMPT, u["history"],
            f"Foydalanuvchi {u['name']} motivatsiya izlayapti. Kuchli, ilmiy va islomiy asoslangan motivatsiya ber. Oxirida bir aniq qadam taklif qil.")
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if txt == "Bugungi kun":
        u["stage"] = "menu"
        today = datetime.now()
        bugun = today.strftime("%d.%m.%Y")
        prompt_today = f"""Bugun {bugun}. Foydalanuvchiga quyidagilarni TOLIK va YAKUNLANGAN holda yoz:

1. Bugun tarixda bolgan 2-3 ta muhim va ilhomlantiruvchi voqea (yil va tavsif bilan)
2. Bugun tughilgan 1-2 ta mashhur va muvaffaqiyatli inson, ularning ishlari va TOLIK bir ilhomlantiruvchi gap
3. Bugun uchun kuchli motivatsiya (2-3 jumla)
4. Islomiy nuqtai nazar: bugungi kunga shukr (1 oyat yoki hadis)

MUHIM: Har bir fikrni TOLIK yakunla. Chala qoldirma. Hamma matn tugallangan bolsin."""

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        try:
            r = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt_today}],
                max_tokens=900, temperature=0.8)
            reply = r.choices[0].message.content
        except:
            reply = f"Bugun {bugun} — yangi imkoniyatlar kuni!\n\nBugun ham katta ishlar qilishingiz mumkin. Allah sizga baraka bersin!"
        await update.message.reply_text(f"Bugun — {bugun}\n\n{reply}", reply_markup=main_menu())
        return

    if txt == "Psixolog":
        await update.message.reply_text(
            "Mutaxassis psixolog bilan boglanish\n\n"
            "Islomda ham takidlanadi: kasallik vaqtida tabibga borish — sunnah.\n"
            "Professional yordam olish — bu kuchsizlik emas, jasorat belgisi!\n\n"
            "Psixolog raqamini olish uchun:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Psixolog raqamini olish", url="https://t.me/boburxoja")
            ]]))
        return

    if txt == "Mening tarixim":
        moods = u.get("moods", [])
        sessions = u.get("sessions", [])
        join = u.get("join_date", "noma'lum")
        if not moods and not sessions:
            await update.message.reply_text(
                f"Salom, {u['name']}!\n\nHali yozuv yoq. Botdan foydalanishni boshlang!", reply_markup=main_menu())
            return
        text = f"{u['name']} ning tarixi:\n\nBot bilan: {join} dan\n"
        if moods:
            avg = sum(m["score"] for m in moods) / len(moods)
            best = max(moods, key=lambda x: x["score"])
            worst = min(moods, key=lambda x: x["score"])
            text += f"\nKayfiyat yozuvlari: {len(moods)} ta\n"
            text += f"Ortacha: {avg:.1f}/5\n"
            text += f"Eng yaxshi kun: {best['date']} — {best['label']}\n"
            text += f"Qiyin kun: {worst['date']} — {worst['label']}\n"
        if sessions:
            text += f"\nSuhbatlar: {len(sessions)} ta\n\nSonggi suhbatlar:\n"
            for s in sessions[-3:]:
                text += f"- {s['date']}: {s['section']}\n"
        text += f"\nDavom eting — har kun bir qadam oldinga!"
        await update.message.reply_text(text, reply_markup=main_menu())
        return

    if u["stage"] == "dard":
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(DARD_PROMPT + memory_ctx, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "nafas_chat":
        reply, u["history"] = await ai_response(NAFAS_PROMPT, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "motivatsiya":
        reply, u["history"] = await ai_response(MOTIVATSIYA_PROMPT, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "mood_chat":
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(MAIN_PROMPT + memory_ctx, u["history"], txt)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    memory_ctx = get_memory_context(u)
    reply, u["history"] = await ai_response(MAIN_PROMPT + memory_ctx, u["history"], txt)
    await update.message.reply_text(reply, reply_markup=main_menu())

async def mood_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    score = int(q.data.split("_")[1])
    labels = {5:"Ajoyib", 4:"Yaxshi", 3:"Ortacha", 2:"Yomon", 1:"Juda yomon"}
    u["moods"].append({"score":score,"label":labels[score],"date":datetime.now().strftime("%d.%m.%Y %H:%M")})
    responses = {
        5: "Ajoyib! Bu energiyani saqlash uchun — bugun 3 ta minnatdorlik yozing. Kimga yoki nimaga minnatdorsiz?",
        4: "Yaxshi kayfiyat — bu nemat! Quron: Shukr qilsangiz, albatta ziyadalayman (Ibrohim, 7). Bugun nima yaxshi boldi?",
        3: "Ortacha... Bu holat signal. Nima sizni toliq baxtli qilishidan tosyapti? Bir sabab ayting.",
        2: "Yomon kayfiyat — bu otib ketadi. Inna maal usri yusra — qiyinchilik bilan yengillik birga. Nima boldi bugun?",
        1: "Juda ogir kun... Men siz bilan birman. Yolgiz emassiz. Nima qiynayapti?"
    }
    u["stage"] = "mood_chat"
    u["history"] = []
    await q.edit_message_text(responses[score])
    await context.bot.send_message(q.message.chat_id, "Men eshityapman...", reply_markup=back_menu())
    if score <= 2:
        await context.bot.send_message(
            q.message.chat_id, "Agar juda ogir bolsa psixolog bilan gaplashing:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Psixolog", url="https://t.me/boburxoja")]]))

MEDS_DATA = [
    ("Tana skaneri (5 daqiqa)",
     "Ilm: Body scan meditatsiyasi interoception — ichki his-tuygu idrokini kuchaytiradi.\n\n"
     "1. Qulay otiring yoki yoting\n2. Kozingizni yuming — 3 marta chuqur nafas\n"
     "3. Boshingizdan boshlang — qayerda taranglik bor?\n"
     "4. Yelkalar — Kokrak — Qorin — Oyoqlar\n"
     "5. Har joyda 10 soniya — taranglikni his qiling va qoyvoring\n\n5 daqiqa. Hozir boshlang."),
    ("Xotirjamlik (3 daqiqa)",
     "Ilm: Mindfulness meditatsiyasi amigdalani tinchitadi — xavotir markazi.\n\n"
     "Kozingizni yuming. Dengiz qirgogini tasavvur qiling.\n"
     "Har nafas — tolqin keladi. Har chikarish — tolqin ketadi.\n"
     "Fikrlar kelsa — tolqin olib ketsin.\n\n3 daqiqa. Hoziroq."),
    ("Ertalab zaryadka (2 daqiqa)",
     "Ilm: Ertalabki ritual kortizol darajasini ijobiy boshqaradi.\n\n"
     "1. Orningizdan turing\n2. Qollarni osmonga kotaring\n"
     "3. 5 marta chuqur nafas\n4. Bugun 1 ta maqsad\n"
     "5. Bismillah, bugun yaxshi kun — deyish\n\n2 daqiqa. Har kuni!"),
    ("Kechki tinchlanish (5 daqiqa)",
     "Ilm: Kechki minnatdorlik rituali serotonin ishlab chiqarishni oshiradi.\n\n"
     "1. Yotib oling\n2. Bugun bolgan 3 ta yaxshi narsa\n"
     "3. Kimga yaxshilik qildingiz bugun?\n4. Ertangi kun uchun 1 ta niyat\n"
     "5. Alhamdulillah bu kun uchun — deyish\n\n5 daqiqa. Har kechasi.")
]

async def med_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"{MEDS_DATA[idx][0]}\n\n{MEDS_DATA[idx][1]}")
    await context.bot.send_message(
        q.message.chat_id,
        "Boshlang — men kutib turaman.\nTugagach yozing: qanday his qildingiz?",
        reply_markup=back_menu())

BREATHS_DATA = [
    ("Tashvish uchun — 4-7-8 nafas",
     "Ilm: Bu texnika parasimpatik nervni faollashtiradi, adrenalin darajasini 40% kamaytiradi.\n\n"
     "4 soniya — burun orqali nafas OLING\n7 soniya — ushlab TURING\n8 soniya — ogiz orqali SEKIN chiqaring\n\n"
     "4 marta takrorlang. Hozir boshlang."),
    ("Gazab uchun — Quti nafas",
     "Ilm: Box breathing Navy SEAL lari ishlatadi — gazab va stressni 3 daqiqada bosadi.\n\n"
     "4 soniya nafas — 4 soniya ushlab tur — 4 soniya chikar — 4 soniya ushlab tur\n\n"
     "5 marta. Kvadrat chizing — har tomoni 4 soniya."),
    ("Uxlash uchun — 4-7-8",
     "Ilm: Dr. Andrew Weil texnikasi — 10-15 daqiqada uxlatadi.\n\n"
     "4 soniya nafas — 7 soniya ushlab tur — 8 soniya chikar\n\n"
     "4-6 marta. Kozingizni yuming. Xonani qorong'i qiling."),
    ("Stress uchun — Fiziologik xorsinish",
     "Ilm: Stanford tadqiqoti — eng tez stressni kamaytiruvchi nafas.\n\n"
     "1. Burun orqali 2 qisqa nafas (ikkinchisi kuchliroq)\n"
     "2. Ogiz orqali 1 uzun nafas chiqarish\n\n"
     "3-5 marta. Darhol tinchlash beradi."),
    ("Umumiy tinchlash — Diafragma nafas",
     "Ilm: Diafragma nafas HRV yaxshilaydi — stressga chidamlilik oshadi.\n\n"
     "Qorin ustiga qolingizni qoying.\n"
     "4 soniya — qorin kotalib nafas. 4 soniya — qorin tushib chikarish.\n\n"
     "10 marta. Har kuni 5-10 daqiqa — 1 oyda stressga chidamlilik 2 baravar oshadi!")
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
        "Boshlang! Tugagach yozing — qanday his qildingiz? Natijani birga tahlil qilamiz.",
        reply_markup=back_menu())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Bu buyruq faqat admin uchun!")
        return
    total = len(users)
    total_moods = sum(len(u["moods"]) for u in users.values())
    total_sessions = sum(len(u["sessions"]) for u in users.values())
    active = sum(1 for u in users.values() if u.get("stage") != "menu")
    await update.message.reply_text(
        f"JAST Admin Panel:\n\n"
        f"Jami foydalanuvchilar: {total}\n"
        f"Faol suhbatlar: {active}\n"
        f"Kayfiyat yozuvlari: {total_moods}\n"
        f"Suhbat sessiyalari: {total_sessions}")

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
