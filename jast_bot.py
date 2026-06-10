import os
import logging
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
    context = "\n\n📜 Foydalanuvchi tarixi:\n"
    for s in u["sessions"][-3:]:
        context += f"- {s['date']}: {s['section']} — {s['summary']}\n"
    if u["moods"]:
        avg = sum(m["score"] for m in u["moods"][-5:]) / min(len(u["moods"]),5)
        context += f"\n📊 O'rtacha kayfiyat: {avg:.1f}/5"
    return context

MAIN_PROMPT = """Sen JAST — O'zbekistonning eng kuchli, eng ishonchli ruhiy ko'mak yordamchisisan.

SENING SHAXSIYATING:
- Eng yaqin do'st, professional psixolog va islomiy maslahatchi unvoni.
- Har bir so'zni chuqur tahlil qilasan va shoshmasdan, mulohaza bilan javob berasan.
- Aniq faktlar, ilmiy nazariyalar va Islom dini ma'rifatiga tayangan holda suhbat quradi.
- Foydalanuvchining o'tgan seanslar tarixini yodda saqlaysan va undan unumli foydalanasan.
- Hech qachon bir xil, shablonli va quruq javoblar qaytarmaysan.

TIL VA GRAMMATIKA QOIDALARI:
- Faqat va faqat o'zbek adabiy tilida, imlo xatolarisiz gapir.
- O'zbek tilidagi "o' ", "g' ", "sh", "ch" harflari va tutuq belgilarini o'z o'rnida to'g'ri ishlat. (Masalan: bolim emas bo'lim, togri emas to'g'ri, bolsa emas bo'lsa).
- Jumlalarni mantiqan va grammatik jihatdan mukammal darajada tuz, chala gaplarni qoldirma.

ISLOM + PSIXOLOGIYA USLUBI:
- Qur'on oyatlari va sahih hadislarni faqat kerakli, mos o'rinlarda va aniq manbasi bilan keltir.
- Kognitiv-xulq-atvor terapiyasi (CBT), mindfulness va pozitiv psixologiya usullarini qo'lla.
- Viktor Frankl, Aaron Bek, Abraham Maslow kabi olimlarning ilmiy nazariyalariga tayangan holda tavsiyalar ber.

CHUQUR TAHLIL VA MATNNI TO'G'RI TUSHUNISH QOIDALARI:
1. DIQQAT: Foydalanuvchi lotin alifbosida "zor boldi" (zo'r bo'ldi), "kayfiyatim zor", "yaxshi uxlash uchun maslahat bering" deb yozsa, buni ijobiy holat deb qabul qil! Foydalanuvchining kayfiyati yomon deb o'ylama va unga asossiz hamdardlik bildirma.
2. Agar foydalanuvchining kayfiyati a'lo bo'lsa, uning quvonchiga sherik bo'l, erishgan ijobiy holatini maqta va buni yanada mustahkamlash, bugungi tunni xotirjam o'tkazish uchun dam olish va uyqu gigiyenasi bo'yicha amaliy tavsiyalar ber.
3. Har bir muammoni yoki so'rovni 3 bosqichda tahlil qil: a) Hozirgi holat b) Kelib chiqish sababi c) Amaliy yechim.
4. Agar foydalanuvchining savoli tushunarsiz bo'lsa: "Nima demoqchi bo'lganingizni to'liq tushuna olmadim. Biroz aniqroq tushuntirib bera olasizmi? Sizga to'g'ri ko'mak berishni istayman." deb so'ra.
5. Har bir javobing oxirida suhbatni davom ettiruvchi va chuqur o'ylantiruvchi 1 ta ochiq savol ber.

MUHIM QOIDALAR:
- Javoblaring chuqur ma'no, aniqlik va mantiqiy yakunga ega bo'lsin. Hech qachon gapni chala qoldirma.
- Agar foydalanuvchida o'z joniga qasd qilish moyilligini sezsang, uni kechiktirmasdan professional shoshilinch psixologik yordamga yo'naltir."""

DARD_PROMPT = """Sen JAST loyihasining "Dardimni aytay" bo'limidasan.

BU BO'LIMDA FAQAT:
- Foydalanuvchini chuqur tinglash, tushunish va unga samimiy empatiya bildirish kerak.
- Muammoni 3 ta qatlamda (holat, sabab, yechim) tahlil qilasan.
- CBT (kognitiv-xulq-atvor terapiyasi) va Islomiy psixologiya tamoyillari asosida yordam ko'rsatasan.
- Tavsiyalaring aniq va ilmiy jihatdan asoslangan bo'lishi shart.

BU BO'LIMDA HECH QACHON:
- Nafas mashqlari yoki meditatsiyani maslahat berma.
- Grammatik jihatdan noto'g'ri yoki shablonli jumlalar tuzma.

Qur'oni Karim: "Inna ma'al usri yusra" — Albatta, har bir qiyinchilik bilan birga bir yengillik bordir (Sharh surasi, 6-oyat)."""

NAFAS_PROMPT = """Sen JAST loyihasining "Nafas mashqi" bo'limidasan.
Faqat va faqat nafas olish texnikalari hamda ularning inson organizmiga ta'siri haqida gapir.
Ilmiy asoslar sifatida parasimpatik asab tizimi va vagus nervining faollashishini tushuntir.
Foydalanuvchining hozirgi holatiga qarab qaysi nafas texnikasi mos kelishini aniq tushuntirib ber hamda mashq natijasini so'ra."""

MOTIVATSIYA_PROMPT = """Sen JAST loyihasining "Motivatsiya" bo'limidasan.
Faqat va faqat foydalanuvchiga kuchli, ilmiy va mantiqiy jihatdan asoslangan motivatsiya ber. Viktor Frankl va Toni Robbinsning hayotiy prinsiplaridan misollar keltir.
Qur'oni Karim: "Albatta, Alloh bir qavmning ahvolini, ular o'zlarini o'zgartirmagunlaricha o'zgartirmas" (Ra'd surasi, 11-oyat).
Foydalanuvchi uchun bugunning o'zida amalga oshirishi kerak bo'lgan 1 ta aniq maqsad va qadam belgilab ber. Jumlalaring 4-5 tadan oshmasin, biroq juda ta'sirli va jo'shqin bo'lsin."""

def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("❤️ Dardimni aytay"), KeyboardButton("🎭 Kayfiyatim")],
        [KeyboardButton("🧘 Meditatsiya"), KeyboardButton("🫁 Nafas mashqi")],
        [KeyboardButton("⚡ Motivatsiya"), KeyboardButton("📅 Bugungi kun")],
        [KeyboardButton("👨‍⚕️ Psixolog"), KeyboardButton("📖 Mening tarixim")]
    ], resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("⬅️ Bosh menu")]], resize_keyboard=True)

async def ai_response(prompt, history, user_msg, max_tokens=800):
    history.append({"role":"user","content":user_msg})
    if len(history) > 12:
        history = history[-12:]
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":prompt}]+history,
            max_tokens=max_tokens, 
            temperature=0.75
        )
        reply = r.choices[0].message.content
        history.append({"role":"assistant","content":reply})
        return reply, history
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "⚠️ Hozirda texnik nosozlik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring.", history

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    u["name"] = update.effective_user.first_name or "Do'stim"
    u["stage"] = "menu"
    u["history"] = []
    u["current_section"] = None
    memory = ""
    if u["sessions"]:
        last = u["sessions"][-1]
        memory = f"\n\n🧠 *Esimda:* `{last['date']}` sanasida *{last['section']}* bo'limida suhbatlashgan edik. Mashq yoki tavsiyalar natijasi qanday bo'ldi?"
    await update.message.reply_text(
        f"👋 Salom, *{u['name']}*! \n\n"
        f"🤖 Men *JAST* — sizning eng ishonchli ruhiy ko'makdosh va sirdosh do'stingizman.\n\n"
        f"✨ Har qanday dard, tashvish yoki sizni o'ylantirayotgan savollar bilan keling — men har doim sizni tinglashga tayyorman."
        f"{memory}\n\n"
        f"👇 Bugun sizga qanday yordam bera olaman?",
        reply_markup=main_menu(), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    txt = update.message.text

    if txt == "⬅️ Bosh menu" or txt == "Bosh menu":
        if u["history"] and u["current_section"]:
            save_session(u, u["current_section"], u["history"][-1]["content"][:100])
        u["stage"] = "menu"
        u["history"] = []
        u["current_section"] = None
        await update.message.reply_text("🏡 Bosh menuga qaytdingiz.", reply_markup=main_menu())
        return

    if txt == "❤️ Dardimni aytay":
        u["stage"] = "dard"
        u["current_section"] = "Dard"
        u["history"] = []
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(
            DARD_PROMPT + memory_ctx, u["history"],
            f"Foydalanuvchi dard bo'limiga kirdi. Ismi: {u['name']}. Uni samimiy kutib ol va hozirda uni nima qiynayotganini so'ra.", max_tokens=800)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if txt == "🎭 Kayfiyatim":
        u["stage"] = "mood"
        u["current_section"] = "Kayfiyat"
        await update.message.reply_text(
            "📝 Bugun kayfiyatingiz qanday?\nO'z holatingizga to'g'ri va halol baho bering:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤩 Ajoyib (5)", callback_data="mood_5"),
                 InlineKeyboardButton("🙂 Yaxshi (4)", callback_data="mood_4")],
                [InlineKeyboardButton("😐 O'rtacha (3)", callback_data="mood_3"),
                 InlineKeyboardButton("🙁 Yomon (2)", callback_data="mood_2")],
                [InlineKeyboardButton("😭 Juda yomon (1)", callback_data="mood_1")]]))
        return

    if txt == "🧘 Meditatsiya":
        u["stage"] = "med"
        u["current_section"] = "Meditatsiya"
        await update.message.reply_text(
            "✨ *Meditatsiya* — ichki xotirjamlik va qalb tozaligiga olib boruvchi yo'ldir.\n\n"
            "📖 *Qur'oni Karim:* _\"Ala bizikrillahi tatmainnul qulub\"_ — "
            "Bilingki, qalblar faqat Allohni zikr qilish bilan taskin topadi (Ra'd surasi, 28-oyat).\n\n"
            "👇 O'zingizga mos keladigan meditatsiya turini tanlang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Tana skaneri (5 daqiqa)", callback_data="med_0")],
                [InlineKeyboardButton("🌊 Xotirjamlik sohili (3 daqiqa)", callback_data="med_1")],
                [InlineKeyboardButton("🌅 Tonggi ruhan quvvatlanish (2 daqiqa)", callback_data="med_2")],
                [InlineKeyboardButton("🌌 Kechki tinchlanish (5 daqiqa)", callback_data="med_3")]]), parse_mode="Markdown")
        return

    if txt == "🫁 Nafas mashqi":
        u["stage"] = "nafas"
        u["current_section"] = "Nafas"
        await update.message.reply_text(
            "🌬️ *To'g'ri nafas olish* — eng samarali tabiiy davodir.\n\n"
            "🔬 *Ilmiy asos:* Chuqur va tartibli nafas olish vagus nervini faollashtiradi hamda organizmdagi kortizol (stress) gormonini kamaytiradi.\n\n"
            "👇 Hozirgi ruhiy holatingiz qanday?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😰 Tashvish va Xavotir", callback_data="breath_0")],
                [InlineKeyboardButton("🤬 Asabiylashish va G'azab", callback_data="breath_1")],
                [InlineKeyboardButton("🥱 Uyqusizlik muammosi", callback_data="breath_2")],
                [InlineKeyboardButton("🤯 Kuchli stress va Zo'riqish", callback_data="breath_3")],
                [InlineKeyboardButton("🟢 Umumiy tinchlanish", callback_data="breath_4")]]), parse_mode="Markdown")
        return

    if txt == "⚡ Motivatsiya":
        u["stage"] = "motivatsiya"
        u["current_section"] = "Motivatsiya"
        u["history"] = []
        reply, u["history"] = await ai_response(
            MOTIVATSIYA_PROMPT, u["history"],
            f"Foydalanuvchi {u['name']} motivatsiya izlamoqda. Unga kuchli, ilmiy va islomiy asoslangan motivatsiya ber. Oxirida amalga oshirishi mumkin bo'lgan aniq bir qadam taklif qil.", max_tokens=800)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if txt == "📅 Bugungi kun":
        u["stage"] = "menu"
        today = datetime.now()
        bugun = today.strftime("%d.%m.%Y")
        
        # PROMPT MUTLAQ TUZATILDI: Tarixiy faktlarni aniq generatsiya qilish va matn g'alizligini yo'qotish bo'yicha qat'iy filtr qo'shildi.
        prompt_today = f"""Bugun kalendar bo'yicha {bugun} sana (kun va oyga e'tibor ber). Foydalanuvchiga sof o'zbek adabiy tilida, grammatik va imlo xatolarsiz quyidagi reja asosida chiroyli xabar yozib ber:

1. Bugungi kunda (aynan shu oy va kunda) tarixda sodir bo'lgan 2 ta eng muhim, aniq va haqiqiy tarixiy voqeani yil va aniq qisqacha tavsifi bilan yoz (Faktlar 100% real bo'lsin, yil yoki shaxslarni mutloq chalkashtirma!).
2. Shu kunda tug'ilgan dunyoga mashhur 1 ta munosib shaxs, uning insoniyatga keltirgan foydasi va unga tegishli ilhomlantiruvchi, ma'noli iqtibosni keltir. Gaplarni takrorlama.
3. Bugungi kun uchun maxsus, 2-3 jumladan iborat ta'sirli va tugallangan ruhiy motivatsiya yoz. (Matnda so'z o'yinlari yoki imlo xatolari bo'lmasin, masalan: "ishonch bilan intiling" kabi toza yozilsin).
4. Islomiy nuqtai nazar: Ushbu yangi kunga sog'-salomat yetkazgani uchun Allohga shukronalik bildirish va berilgan umr ne'matini qadrlash haqida "Ibrohim" surasining 7-oyati ma'nosini chiroyli adabiy tilda bayon qil ("Agar shukr qilsangiz, albatta ziyoda qilurman...").

MUHIM QOIDALAR:
- Hech qanday gap yoki fikr chala qolmasin.
- Bir marta aytilgan ma'lumot (masalan, shaxs ismi) matn davomida aynan o'sha so'zlar bilan asossiz qayta-qayta takrorlanmasin.
- -ganligini, -ishligini kabi sun'iy shakllardan qochib, ravon o'zbek tilida yoz."""

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        try:
            r = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt_today}],
                max_tokens=1200, temperature=0.6) # Temp biroz pasaytirildi (faktlar aniq chiqishi uchun)
            reply = r.choices[0].message.content
        except:
            reply = f"✨ Bugun {bugun} — siz uchun yangi imkoniyatlar eshigi!\n\n💪 Bugun ham hayotingizda go'zal o'zgarishlar qilishga qodirsiz. Alloh kunigizga baraka bersin!"
        await update.message.reply_text(f"📅 *Bugun — {bugun}*\n\n{reply}", reply_markup=main_menu(), parse_mode="Markdown")
        return

    if txt == "👨‍⚕️ Psixolog":
        await update.message.reply_text(
            "🤝 *Mutaxassis psixolog bilan bog'lanish*\n\n"
            "🕌 Islom dinida ham ta'kidlanganidek, xastalik yoki ruhiy tanglik vaqtida tabibga (mutaxassisga) murojaat qilish — sunnatdir.\n"
            "💡 Professional yordam olish — bu zaiflik emas, balki o'z kelajagiga bo'lgan yuksak jasorat belgisidir!\n\n"
            "👇 Psixolog bilan to'g'ridan-to'g'ri bog'lanish uchun quyidagi tugmani bosing:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📞 Psixolog bilan muloqot", url="https://t.me/boburxoja")
            ]]), parse_mode="Markdown")
        return

    if txt == "📖 Mening tarixim":
        moods = u.get("moods", [])
        sessions = u.get("sessions", [])
        join = u.get("join_date", "noma'lum")
        if not moods and not sessions:
            await update.message.reply_text(
                f"👋 Salom, {u['name']}!\n\nHali sizning ruhiy tarixingiz bo'yicha ma'lumotlar shakllandi. Bot xizmatlaridan faol foydalanishni boshlang! 🚀", reply_markup=main_menu())
            return
        text = f"📖 *{u['name']} ning ruhiy jurnali:*\n\n📅 *Botga a'zo bo'lingan sana:* {join}\n"
        if moods:
            avg = sum(m["score"] for m in moods) / len(moods)
            best = max(moods, key=lambda x: x["score"])
            worst = min(moods, key=lambda x: x["score"])
            text += f"\n📊 *Kayfiyat qaydlari:* {len(moods)} ta\n"
            text += f"📈 *O'rtacha ruhiy ko'rsatkich:* {avg:.1f}/5\n"
            text += f"☀️ *Eng ko'tarinki ruhdagi kun:* {best['date']} — {best['label']}\n"
            text += f"☁️ *Eng qiyin o'tgan kun:* {worst['date']} — {worst['label']}\n"
        if sessions:
            text += f"\n💬 *O'tkazilgan seanslar soni:* {len(sessions)} ta\n\n🕒 *So'nggi suhbatlar:*\n"
            for s in sessions[-3:]:
                text += f"- {s['date']}: {s['section']}\n"
        text += f"\n🚀 To'xtab qolmang — har kuni o'zligingiz sari bir qadam tashlang!"
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="Markdown")
        return

    if u["stage"] == "dard":
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(DARD_PROMPT + memory_ctx, u["history"], txt, max_tokens=800)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "nafas_chat":
        reply, u["history"] = await ai_response(NAFAS_PROMPT, u["history"], txt, max_tokens=800)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "motivatsiya":
        reply, u["history"] = await ai_response(MOTIVATSIYA_PROMPT, u["history"], txt, max_tokens=800)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if u["stage"] == "mood_chat":
        memory_ctx = get_memory_context(u)
        reply, u["history"] = await ai_response(MAIN_PROMPT + memory_ctx, u["history"], txt, max_tokens=800)
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    memory_ctx = get_memory_context(u)
    reply, u["history"] = await ai_response(MAIN_PROMPT + memory_ctx, u["history"], txt, max_tokens=800)
    await update.message.reply_text(reply, reply_markup=main_menu())

async def mood_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    score = int(q.data.split("_")[1])
    labels = {5:"🤩 Ajoyib", 4:"🙂 Yaxshi", 3:"😐 O'rtacha", 2:"🙁 Yomon", 1:"😭 Juda yomon"}
    u["moods"].append({"score":score,"label":labels[score],"date":datetime.now().strftime("%d.%m.%Y %H:%M")})
    responses = {
        5: "🤩 Ajoyib! Bu ko'tarinki energiyani saqlab qolish uchun bugun hayotingizdagi 3 ta minnatdorlik sababini yozing. Hozirda kimdan yoki nimadan minnatdorsiz?",
        4: "🙂 Yaxshi kayfiyat — bu ulug' ne'mat! Qur'oni Karimda: 'Agar shukr qilsangiz, albatta ziyoda qilurman' (Ibrohim surasi, 7-oyat) deyilgan. Bugun sizni nima xursand qildi?",
        3: "😐 O'rtacha... Bu holat sizga o'zingizga e'tibor berish kerakligini anglatuvchi signaldir. To'liq baxtli bo'lishingizga nima to'sqinlik qilmoqda? Birgalikda tahlil qilamiz.",
        2: "🙁 Yomon kayfiyat — bu vaqtinchalik holat, u albatta o'tib ketadi. Har bir qiyinchilik ortida yengillik bor. Bugun aynan nima sababdan dilingiz xira bo'ldi?",
        1: "😭 Juda og'ir kun... Men butun qalbim bilan sizni tushunib turibman. Siz aslo yolg'iz emassiz, men har doim yoningizdaman. Sizni aynan nima qiynayotganini so'zlab bering."
    }
    u["stage"] = "mood_chat"
    u["history"] = []
    await q.edit_message_text(responses[score])
    await context.bot.send_message(q.message.chat_id, "💬 Sirdosh sifatida sizni tinglayapman...", reply_markup=back_menu())
    if score <= 2:
        await context.bot.send_message(
            q.message.chat_id, "⚠️ Agar o'zingizni juda og'ir his qilayotgan bo'lsangiz, tajribali mutaxassis bilan suhbatlashishni tavsiya etaman:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👨‍⚕️ Psixolog bilan bog'lanish", url="https://t.me/boburxoja")]]))

MEDS_DATA = [
    ("🔍 Tana skaneri (5 daqiqa)",
     "🔬 *Ilmiy asos:* Tana skaneri (Body scan) meditatsiyasi ichki hissiyotlarni idrok etish (interoception) qobiliyatini kuchaytiradi va jismoniy bloklarni yozadi.\n\n"
     "1️⃣ Qulay joylashib o'tiring yoki yoting.\n2️⃣ Ko'zlaringizni yumib, 3 marta sekin va chuqur nafas oling.\n"
     "3️⃣ Diqqatingizni boshingizdan boshlang — u yerda biron taranglik bormi?\n"
     "4️⃣ Yelka ➡️ Ko'krak qafasi ➡️ Qorin bo'shlig'i ➡️ Oyoqlar sari sekin tushing.\n"
     "5️⃣ Har bir a'zoda 10 soniya to'xtab, u yerdagi og'riq yoki stressni nafas chiqarish orqali qo'yib yuboring.\n\n⏱️ Davomiyligi: 5 daqiqa. Mashqni hoziroq boshlang."),
    ("🌊 Xotirjamlik sohili (3 daqiqa)",
     "🔬 *Ilmiy asos:* Mindfulness (onglilik) meditatsiyasi miyadagi xavotir markazi hisoblangan amigdalani tinchlantiradi.\n\n"
     "1️⃣ Ko'zlaringizni yuming. Tinch va osoyishta dengiz qirg'og'ini tasavvur qiling.\n"
     "2️⃣ Har safar nafas olganingizda — sokin to'lqin qirg'oqqa kelayotganini his eting.\n3️⃣ Har safar nafas chiqarganingizda — to'lqin sekin ortiga qaytayotganini tasavvur qiling.\n"
     "4️⃣ Xayolingizga chalg'ituvchi fikrlar kelsa, ularga qarshilik qilmang, to'lqinlar ularni ham yuvib ketayotganini tasavvur qiling.\n\n⏱️ Davomiyligi: 3 daqiqa. Hoziroq sinab ko'ring."),
    ("🌅 Tonggi ruhan quvvatlanish (2 daqiqa)",
     "🔬 *Ilmiy asos:* Tonggi maxsus rituallar kun davomida stress gormoni (kortizol) darajasini ijobiy boshqarishga yordam beradi.\n\n"
     "1️⃣ O'rningizdan tik turing.\n2️⃣ Qo'llaringizni yuqoriga, osmon sari cho'zing.\n"
     "3️⃣ 5 marta ketma-ket erkin va keng nafas oling.\n4️⃣ Bugungi kun davomida erishmoqchi bo'lgan 1 ta asosiy ezgu niyatni belgilang.\n"
     "5️⃣ Ichingizda «Bismillah, bugun yangi muvaffaqiyatlar kuni!» deb o'zingizga ishonch bildiring.\n\n⏱️ Davomiyligi: 2 daqiqa. Har kuni ertalab takrorlang!"),
    ("🌌 Kechki tinchlanish (5 daqiqa)",
     "🔬 *Ilmiy asos:* Kechki minnatdorlik rituali miyada serotonin (baxt gormoni) ajralishini ko'paytiradi va uyqu sifatini yaxshilaydi.\n\n"
     "1️⃣ Yotoqda to'liq qulay joylashib oling.\n2️⃣ Bugun hayotingizda sodir bo'lgan 3 ta kichik bo'lsa-da yaxshi voqeani eslang.\n"
     "3️⃣ Bugun kimga qanday ezgulik ulashdingiz?\n4️⃣ Ertangi go'zal kun uchun ichki bir niyat qiling.\n"
     "5️⃣ «Alhamdulillah, o'tgan kunim uchun ham, berilgan ne'matlar uchun ham!» deb pichirlang.\n\n⏱️ Davomiyligi: 5 daqiqa. Har kecha uyqudan oldin bajaring.")
]

async def med_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"🧘 *{MEDS_DATA[idx][0]}*\n\n{MEDS_DATA[idx][1]}", parse_mode="Markdown")
    await context.bot.send_message(
        q.message.chat_id,
        "✨ Mashqni bajarishni boshlang — men sizni kutaman.\nTugatgach yozing: o'zingizda qanday ijobiy o'zgarish his qildingiz?",
        reply_markup=back_menu())

BREATHS_DATA = [
    ("😰 Tashvish va xavotir uchun — 4-7-8 nafas texnikasi",
     "🔬 *Ilmiy asos:* Bu texnika tanadagi parasimpatik asab tizimini faollashtiradi va adrenalin darajasini qisqa fursatda 40% gacha kamaytiradi.\n\n"
     "1️⃣ 4 soniya davomida — burun orqali chuqur nafas OLING.\n"
     "2️⃣ 7 soniya davomida — nafasingizni ichingizda ushlab TURING.\n"
     "3️⃣ 8 soniya davomida — og'iz orqali sekin va ovozsiz CHIQLARING.\n\n"
     "🔁 Ushbu siklni 4 marta takrorlang. Mashqni hozir boshlang."),
    ("🤬 G'azabni tushirish uchun — Kvadrat (Box) nafasi",
     "🔬 *Ilmiy asos:* Ushbu usuldan maxsus xizmat askarlari kuchli g'azab va kutilmagan stressni 3 daqiqada bartaraf etish uchun foydalanamiz.\n\n"
     "1️⃣ 4 soniya nafas oling ➡️ 4 soniya ushlab turing ➡️ 4 soniya chiqaring ➡️ 4 soniya nafas olmasdan kuting.\n\n"
     "🔁 Xayolingizda har bir tomoni 4 soniyadan iborat kvadrat chizing. Mashqni kamida 5 marta takrorlang."),
    ("🥱 Tinch uyquga ketish uchun — 4-7-8 ritmi",
     "🔬 *Ilmiy asos:* Doktor Endryu Veyl tomonidan ishlab chiqilgan ushbu texnika tanani 10 daqiqa ichida chuqur dam olish va uyqu rejimiga o'tkazadi.\n\n"
     "1️⃣ 4 soniya nafas oling ➡️ 7 soniya ushlab turing ➡️ 8 soniya davomida juda sekin chiqaring.\n\n"
     "🔁 Jarayonni 4-6 marta takrorlang. Ko'zlaringizni yuming va xonani to'liq qorong'i qiling."),
    ("🤯 Stress va toliqish uchun — Fiziologik xo'rsinish",
     "🔬 *Ilmiy asos:* Stenford universiteti tadqiqotlariga ko'ra, bu usul miyadagi stress signalini bir lahzada to'xtatuvchi eng tezkor tabiiy vositadir.\n\n"
     "1️⃣ Burun orqali ketma-ket 2 marta qisqa nafas oling (ikkinchi nafas birinchisidan chuqurroq bo'lsin).\n"
     "2️⃣ Og'iz orqali 1 marta juda uzun va erkin qibly nafas chiqarib yuboring.\n\n"
     "🔁 Jami 3-5 marta bajaring. Tanangizda darhol yengillik paydo bo'ladi."),
    ("🟢 Umumiy xotirjamlik — Diafragma (qorin) nafasi",
     "🔬 *Ilmiy asos:* Qorin bilan nafas olish yurak ritmining barqarorligini (HRV) yaxshilaydi va uzoq muddatda stressga chidamlilikni oshiradi.\n\n"
     "1️⃣ Bir qo'lingizni ko'kragingizga, ikkinchisini esa qorningiz ustiga qo'ying.\n"
     "2️⃣ 4 soniya davomida ko'kragingizni qimirlatmay, faqat qorinni shishirgan holda nafas oling.\n"
     "3️⃣ 4 soniya davomida qorinni ichkariga tortib, havoni sekin chiqaring.\n\n"
     "🔁 Kamida 10 marta bajaring. Kuniga 5-10 daqiqa shunday mashq qilish stressga chidamlilikni 2 barobarga oshiradi!")
]

async def breath_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"🫁 *{BREATHS_DATA[idx][0]}*\n\n{BREATHS_DATA[idx][1]}", parse_mode="Markdown")
    u["stage"] = "nafas_chat"
    u["history"] = []
    await context.bot.send_message(
        q.message.chat_id,
        "🌬️ Mashqni bajarishni boshlang! Tugatgach, o'zingizda qanday o'zgarish sezganingizni yozib qoldiring — natijani birgalikda tahlil qilamiz.",
        reply_markup=back_menu())

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Ushbu buyruq faqat bot administratori uchun mo'ljallangan!")
        return
    total = len(users)
    total_moods = sum(len(u["moods"]) for u in users.values())
    total_sessions = sum(len(u["sessions"]) for u in users.values())
    active = sum(1 for u in users.values() if u.get("stage") != "menu")
    await update.message.reply_text(
        f"⚙️ *JAST Administrator Panelini:*\n\n"
        f"👥 *Jami ro'yxatdan o'tganlar:* {total} ta\n"
        f"🔥 *Hozirgi faol muloqotlar:* {active} ta\n"
        f"📊 *Kiritilgan kayfiyat qaydlari:* {total_moods} ta\n"
        f"💬 *Umumiy suhbat sessiyalari:* {total_sessions} ta", parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(mood_cb, pattern="^mood_"))
    app.add_handler(CallbackQueryHandler(med_cb, pattern="^med_"))
    app.add_handler(CallbackQueryHandler(breath_cb, pattern="^breath_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("JAST muvaffaqiyatli ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
