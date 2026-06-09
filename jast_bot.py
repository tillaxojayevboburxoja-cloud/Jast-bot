import os
import json
import logging
from datetime import datetime
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Tokenlarni yuklash
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ADMIN_ID = 8023489682

if not TELEGRAM_TOKEN or not GROQ_API_KEY:
    raise ValueError("TELEGRAM_TOKEN va GROQ_API_KEY muhit o'zgaruvchilari o'rnatilishi shart!")

groq_client = Groq(api_key=GROQ_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = "users_db.json"
users = {}

# ==================== STIKERLAR BAZASI ====================
# Telegram standart va rasmiy emoji/stiker unikal ID-lari (Xavfsiz va turg'un)
STICKER_IDS = {
    "hello": "CAACAgIAAxkBAAM6Zg3pG6S7-m0BvAABRx7_Sg8bAAOpAAIBAAMInEkAARvXgAIeBA", 
    "menu": "CAACAgIAAxkBAAM8Zg3pI3p5Mv_wAAFHHv9KDxsAA6kAAgEAAwInEkAARvXgAIeBA",
    "dard": "CAACAgIAAxkBAANAZg3pL3UqR3_wAAFHHv9KDxsAA6kAAgUAAwInEkAARvcFgAIeBA",
    "meditation": "CAACAgIAAxkBAANCZg3pOfWhC3_wAAFHHv9KDxsAA6kAAggAAwInEkAARvoFgAIeBA",
    "breath": "CAACAgIAAxkBAANEZg3pRHV_En_wAAFHHv9KDxsAA6kAAgkAAwInEkAARvsFgAIeBA",
    "motivation": "CAACAgIAAxkBAANGZg3pTmV8S3_wAAFHHv9KDxsAA6kAAgsAAwInEkAARvwFgAIeBA",
    "today": "CAACAgIAAxkBAANIZg3pWTX-U3_wAAFHHv9KDxsAA6kAAgwAAwInEkAARv0FgAIeBA",
    "alert": "CAACAgIAAxkBAANKZg3pY2U_X3_wAAFHHv9KDxsAA6kAAg0AAwInEkAARv4FgAIeBA",
    "ai_thinking": "CAACAgIAAxkBAANMZg3pbaU_Z3_wAAFHHv9KDxsAA6kAAg4AAwInEkAARv_FgAIeBA"
}

async def send_bot_sticker(context, chat_id, sticker_key):
    sticker_id = STICKER_IDS.get(sticker_key, STICKER_IDS["hello"])
    try:
        await context.bot.send_sticker(chat_id=chat_id, sticker=sticker_id)
    except Exception as e:
        logger.error(f"Stiker yuborishda xatolik ({sticker_key}): {e}")

# ==================== BAZA BILAN ISHLASH ====================
def load_data():
    global users
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception as e:
            logger.error(f"Baza yuklashda xatolik: {e}")
            users = {}
    else:
        users = {}

def save_data():
    try:
        temp_file = f"{DATA_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, DATA_FILE)
    except IOError as e:
        logger.error(f"Fayl tizimi band yoki yozishda xatolik: {e}")
    except Exception as e:
        logger.error(f"Kutilmagan baza xatoligi: {e}")

def get_user(uid):
    uid_str = str(uid)
    if uid_str not in users:
        users[uid_str] = {
            "name": "",
            "history": [],
            "moods": [],
            "sessions": [],
            "stage": "menu",
            "current_section": None,
            "join_date": datetime.now().strftime("%d.%m.%Y")
        }
        save_data()
    return users[uid_str]

def save_session(u, section, summary):
    if "sessions" not in u:
        u["sessions"] = []
    u["sessions"].append({
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "section": section,
        "summary": summary
    })
    if len(u["sessions"]) > 20:
        u["sessions"] = u["sessions"][-20:]
    save_data()

def get_memory_context(u):
    context = ""
    if u.get("sessions"):
        context += "\n\nFoydalanuvchi bilan o'tgan suhbatlarning qisqacha tarixi va konteksti:\n"
        for s in u["sessions"][-3:]:
            context += f"- {s['date']} kuni \"{s['section']}\" bo'limida suhbatlashildi. Xulosa: {s['summary']}\n"
    
    if u.get("moods"):
        recent_moods = u["moods"][-5:]
        if recent_moods:  
            avg = sum(m["score"] for m in recent_moods) / len(recent_moods)
            context += f"\nFoydalanuvchining so'nggi kunlardagi o'rtacha kayfiyati: {avg:.1f}/5"
    return context

# ==================== AI PROMPTLARI ====================
USLUB_FILTRI = """
O'ZBEK TILIDA MATN TUZISHNING QAT'IY QOIDALARI:
1. Sening ona tiring — o'zbek tili. Gaplarni o'zbek tili grammatikasi, kelshik qo'shimchalari (ning, ni, ga, da, dan) va egalik qo'shimchalariga mos ravishda, to'g'ri tuz. Ruscha yoki inglizcha gap tuzilishi shablonlaridan so'zma-so'z nusxa olma.
2. Ketma-ket keladigan gaplarda bir xil so'zlar va shablonlarni takrorlama. Boy va chiroyli sinonimlardan unumli foydalan.
3. Har bir fikr, ro'yxat yoki band mantiqan va grammatik jihatdan to'liq yakunlansin. Xabar yarim yo'lda uzilib qolishi taqiqlanadi.
4. "O'z-o'ziga qarash" emas, "O'z-o'zini kuzatish", "Muammolarni qiyinlashtirayotganini" emas, "Sizni qiynayotganini" kabi to'g'ri iboralarni ishlat. 
5. Matnda HTML teglari (masalan, <b>, <i>) ishlatish mutloqo taqiqlanadi. Faqat oddiy matn ko'rinishida javob ber.
"""

MAIN_PROMPT = f"Sen JAST — O'zbekistondagi eng malakali, samimiy va professional ruhiy yordam ko'rsatuvchi sun'iy intellekt yordamchisisan. Foydalanuvchining eng yaqin sirdoshisan. Har bir javobing oxirida foydalanuvchini mulohaza qilishga undaydigan bitta qiziqarli va ochiq savol ber. {USLUB_FILTRI}"
DARD_PROMPT = f"Sen JAST tizimining 'Dardimni aytay' bo'limidasan. Sening vazifang foydalanuvchini diqqat bilan eshitish, unga to'liq empatiya ko'rsatish va Kognitiv-xulq-atvor terapiyasi (CBT) uslubida yondashib, uning fikriy xatoliklarini anglashiga yordam berishdir. Foydalanuvchiga ushbu bo'limda nafas mashqlarini tavsiya qilma. Samimiy va professional bo'l. {USLUB_FILTRI}"
NAFAS_PROMPT = f"Sen JAST tizimining 'Nafas mashqi' bo'limi yordamchisisan. Faqat turli xil chuqur nafas olish texnikalari, ularning inson organizmiga, vagus nerviga hamda parasimpatik asab tizimiga ta'siri haqida ilmiy, tushunarli va ravon tilda gapir. {USLUB_FILTRI}"
MOTIVATSIYA_PROMPT = f"Sen JAST ruhiy ko'mak tizimining 'Motivatsiya' bo'limidasan. Insonning ichki kuchini uyg'otadigan, ham ilmiy, ham umuminsoniy qadriyatlarga asoslangan, shijoat beruvchi kuchli motivatsiya ber. Matn oxirida foydalanuvchi bugun bajarishi kerak bo'lgan bitta aniq va kichik amaliy qadamni belgilab ber. {USLUB_FILTRI}"

# ==================== MENYULAR ====================
def main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💔 Dardimni aytay"), KeyboardButton("🎭 Kayfiyatim")],
        [KeyboardButton("🧘‍♂️ Meditatsiya"), KeyboardButton("🫁 Nafas mashqi")],
        [KeyboardButton("🔥 Motivatsiya"), KeyboardButton("📅 Bugungi kun")],
        [KeyboardButton("👨‍⚕️ Psixolog"), KeyboardButton("📝 Mening tarixim")]
    ], resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("🏡 Bosh menu")]], resize_keyboard=True)

# ==================== AI JAVOBI FUNKSIYASI ====================
async def ai_response(prompt, user_id, user_msg, max_tokens=500):
    u = get_user(user_id)
    u["history"].append({"role": "user", "content": user_msg})
    
    if len(u["history"]) > 12:
        u["history"] = u["history"][-12:]
        
    try:
        r = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": prompt}] + u["history"],
            max_tokens=max_tokens, 
            temperature=0.7
        )
        reply = r.choices[0].message.content
        u["history"].append({"role": "assistant", "content": reply})
        save_data()
        return reply
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "🤖 Hozirgi vaqtda yuklama biroz yuqori bo'lmoqda. Iltimos, fikringizni qayta yozib ko'ring, men sizni eshitishga tayyorman! 🙏"

# ==================== HANDLERLAR ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = get_user(update.effective_user.id)
    u["name"] = update.effective_user.first_name or "Do'stim"
    u["stage"] = "menu"
    u["history"] = []
    u["current_section"] = None
    save_data()
    
    memory = ""
    if u.get("sessions"):
        last = u["sessions"][-1]
        memory = f"\n\n🧠 Oxirgi marta {last['date']} kuni {last['section']} mavzusida suhbatlashgan edik. O'shandan beri o'zgarishlar qanday? Men barchasini eslab qolganman."
    
    await send_bot_sticker(context, chat_id, "hello")
    await update.message.reply_text(
        f"👋 Salom, {u['name']}! \n\nMen JAST — sizning shaxsiy ruhiy ko'makchingiz va ishonchli do'stingizman. {memory}\n\nBugun ichingizni qanday mavzu qiynayapti yoki qanday yordam bera olaman? Quyidagi menyudan tanlang 👇",
        reply_markup=main_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    u = get_user(uid)
    txt = update.message.text

    # Xavfsizlik filtri
    xavfli_so'zlar = ["o'lmoqchiman", "o'lim", "suitsid", "suidsid", "jonimga qasd", "osmoqchi", "yashashni xohlamayman", "charchadim hayotdan", "o'zimni o'ld"]
    if any(soz in txt.lower() for soz in xavfli_so'zlar):
        await send_bot_sticker(context, chat_id, "alert")
        await update.message.reply_text(
            "⚠️ <b>Do'stim, iltimos, to'xtang!</b> \n\nHozir siz juda og'ir hissiyotlar ostida bo'lishingiz mumkin, lekin unutmang, siz yolg'iz emassiz va har qanday berk ko'chaning yechimi bor. "
            "Sizning hayotingiz va borligingiz biz uchun juda qadrli. Iltimos, hozirning o'zidayoq quyidagi professional yordam liniyalariga bepul bog'laning yoki yaqin insoningizga qo'ng'iroq qiling:\n\n"
            "📞 <b>Ishonch telefoni (Respublika bo'yicha):</b> 1003 yoki +998712441221\n"
            "❤️ O'zingizga imkon bering, yordam so'rash — bu kuchlilik belgisidir!",
            parse_mode="HTML"
        )
        return

    if txt == "🏡 Bosh menu":
        if u.get("history") and u.get("current_section"):
            last_msg = u["history"][-1]["content"] if "content" in u["history"][-1] else "Suhbat yakunlandi"
            save_session(u, u["current_section"], last_msg[:100])
        u["stage"] = "menu"
        u["history"] = []
        u["current_section"] = None
        save_data()
        await send_bot_sticker(context, chat_id, "menu")
        await update.message.reply_text("🏡 Bosh menyuga qaytdingiz. O'zingizni asrang. Xizmatga tayyorman 👇", reply_markup=main_menu())
        return

    if txt == "💔 Dardimni aytay":
        u["stage"] = "dard"
        u["current_section"] = "Dardimni aytay"
        u["history"] = []
        save_data()
        memory_ctx = get_memory_context(u)
        
        await send_bot_sticker(context, chat_id, "dard")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        reply = await ai_response(DARD_PROMPT + memory_ctx, uid, "Salom JAST, men hozir ruhiy tushkunlikdaman yoki ichimda og'riqli gaplar bor. Meni tingla va suhbatni boshla.")
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if txt == "🎭 Kayfiyatim":
        u["stage"] = "mood"
        u["current_section"] = "Kayfiyatni aniqlash"
        save_data()
        await update.message.reply_text(
            "🎭 <b>Bugungi ichki holatingiz va kayfiyatingizni qanday baholaysiz?</b>\n\nO'zingizga mutloq sodiq qolgan holda quyidagi tugmalardan birini tanlang. Men sizga mos tahlilni boshlayman:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤩 Ajoyib (5)", callback_data="mood_5"), InlineKeyboardButton("🙂 Yaxshi (4)", callback_data="mood_4")],
                [InlineKeyboardButton("😐 O'rtacha (3)", callback_data="mood_3"), InlineKeyboardButton("😟 Yomon (2)", callback_data="mood_2")],
                [InlineKeyboardButton("😭 Juda yomon (1)", callback_data="mood_1")]
            ]), parse_mode="HTML")
        return

    if txt == "🧘‍♂️ Meditatsiya":
        u["stage"] = "med"
        u["current_section"] = "Meditatsiya"
        save_data()
        await send_bot_sticker(context, chat_id, "meditation")
        await update.message.reply_text(
            "🧘‍♂️ <b>Meditatsiya — fikrlar shovqinini o'chirish va ruhiy sokinlikka erishish san'atidir.</b>\n\n"
            "🕌 <i>'Bilingki, qalblar faqat Allohning zikri ila orom olur.'</i> (Ra'd surasi, 28-oyat)\n\n"
            "Hozirgi holatingiz uchun quyidagi ruhiy mashqlardan birini tanlang 👇",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧠 Tana skaneri (5 daqiqa)", callback_data="med_0")],
                [InlineKeyboardButton("🌊 Ruhiy xotirjamlik daryosi (3 daqiqa)", callback_data="med_1")],
                [InlineKeyboardButton("☀️ Tonggi energiya zaryadi (2 daqiqa)", callback_data="med_2")],
                [InlineKeyboardButton("🌌 Kechki uyqu oldi tinchlanish (5 daqiqa)", callback_data="med_3")]
            ]), parse_mode="HTML")
        return

    if txt == "🫁 Nafas mashqi":
        u["stage"] = "nafas"
        u["current_section"] = "Nafas mashqlari"
        save_data()
        await send_bot_sticker(context, chat_id, "breath")
        await update.message.reply_text(
            "🫁 <b>To'g'ri nafas olish — asab tizimini bir necha daqiqada tinchlantirishning ilmiy isbotlangan usulidir.</b>\n\nHozir sizni qaysi holat bezovta qilmoqda? Shunga qarab nafas texnikasini tanlaymiz:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😰 Kuchli xavotir va vahima", callback_data="breath_0")],
                [InlineKeyboardButton("😡 Asabiylashish va g'azab", callback_data="breath_1")],
                [InlineKeyboardButton("😴 Uyqusizlik va fikrlar ko'pligi", callback_data="breath_2")],
                [InlineKeyboardButton("😮‍cv Kunlik stress va zo'riqish", callback_data="breath_3")],
                [InlineKeyboardButton("🍃 Umumiy o'pka kengayishi", callback_data="breath_4")]
            ]), parse_mode="HTML")
        return

    if txt == "🔥 Motivatsiya":
        u["stage"] = "motivatsiya"
        u["current_section"] = "Motivatsiya olish"
        u["history"] = []
        save_data()
        await send_bot_sticker(context, chat_id, "motivation")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        reply = await ai_response(MOTIVATSIYA_PROMPT, uid, "Menga hozirgi holatim uchun juda kuchli, irodani uyg'otadigan va amaliy qadamga ega motivatsiya ber.")
        await update.message.reply_text(reply, reply_markup=back_menu())
        return

    if txt == "📅 Bugungi kun":
        u["stage"] = "menu"
        today = datetime.now()
        bugun = today.strftime("%d.%m.%Y")
        save_data()
        
        prompt_today = f"""Bugun {bugun} sana. Quyidagi qismlardan iborat o'ta chiroyli va adabiy ma'lumot tuz:
1. Tarix varaqlarida bugun: Ushbu sanada dunyoda yoki mintaqamizda sodir bo'lgan 2-3 ta eng muhim, qiziqarli va odamni chuqur o'ylantiradigan voqea.
2. Bugun tug'ilgan buyuklar: Shu kuni tug'ilgan mashhur tarixiy shaxs, olim yoki mutafakkir va uning hayotga bo'lgan qarashlarini aks ettiruvchi oltin iqtibosi.
3. Kun shijoati: Insonni harakatga keltiruvchi, bugungi kunini qadrlashga undovchi 2-3 ta olovli jumla.
4. Kun hikmati (Qalb oromi): Shukronalik, sabr yoki ilm haqida 1 ta go'zal Qur'on oyati yoki sahih hadis ma'nosi va uning bugungi hayotimizga bog'liq qisqa sharhi.

Matnda umuman HTML teglari ishlatma."""

        await send_bot_sticker(context, chat_id, "today")
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            r = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt_today}],
                max_tokens=1200, 
                temperature=0.7
            )
            reply = r.choices[0].message.content
        except Exception as e:
            logger.error(f"Bugun xatolik: {e}")
            reply = f"Bugun {bugun} — siz uchun yangi baxt, yangi imkoniyatlar va hayotingizni go'zallashtirish uchun berilgan yana bir go'zal imkoniyatdir! ✨"
        
        await update.message.reply_text(f"✨ Bugun — {bugun} yil varog'i ✨\n\n{reply}", reply_markup=main_menu())
        return

    if txt == "👨‍⚕️ Psixolog":
        await update.message.reply_text(
            "👨‍⚕️ <b>Professional psixolog ko'magi!</b>\n\nAgar sizga sun'iy intellektdan tashqari, hayotiy tajribaga ega bo'lgan mutaxassis bilan jonli suhbat yoki chuqur terapiya seansi kerak bo'lsa, quyidagi tugma orqali mutaxassisimiz bilan to'g'ridan-to'g'ri bog'lanishingiz mumkin:\n\n"
            "💬 <i>Yordam so'rash — zaiflik emas, aksincha muammoga qarshi turish uchun jasoratdir!</i> 👇",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤝 Psixolog bilan bog'lanish", url="https://t.me/boburxoja")]]),
            parse_mode="HTML"
        )
        return

    if txt == "📝 Mening tarixim":
        moods = u.get("moods", [])
        sessions = u.get("sessions", [])
        join = u.get("join_date", "noma'lum")
        
        if not moods and not sessions:
            await update.message.reply_text("📝 <b>Hali ruhiy tarixingiz shakllanmagan.</b>\n\nMen bilan ko'proq suhbatlashib, kayfiyatingizni belgilab borsangiz, shu bo'limda sizning shaxsiy o'sish grafikangiz va ruhiy jurnalingiz paydo bo'ladi! 🌱", parse_mode="HTML")
            return
            
        text = f"📝 <b>{u['name']} ning Shaxsiy Ruhiy Kundaligi</b>\n\n📅 <b>Tizimdagi faollik:</b> {join} dan buyon\n"
        if moods:
            avg = sum(m["score"] for m in moods) / len(moods)
            text += f"📊 <b>Belgilangan kayfiyatlar:</b> {len(moods)} marta\n📈 <b>O'rtacha ruhiy ko'rsatkich:</b> {avg:.1f} / 5.0\n"
        if sessions:
            text += f"\n💬 <b>Oxirgi suhbatlashilgan muhim seanslar:</b>\n"
            for s in sessions[-4:]:
                text += f"▪️ <i>{s['date']}</i> — {s['section']} bo'limi\n"
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="HTML")
        return

    # Umumiy holatda AI'ga yuborish
    await send_bot_sticker(context, chat_id, "ai_thinking")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    memory_ctx = get_memory_context(u)
    
    if u["stage"] == "dard":
        reply = await ai_response(DARD_PROMPT + memory_ctx, uid, txt)
    elif u["stage"] == "nafas_chat":
        reply = await ai_response(NAFAS_PROMPT, uid, txt)
    elif u["stage"] == "motivatsiya":
        reply = await ai_response(MOTIVATSIYA_PROMPT, uid, txt)
    elif u["stage"] == "mood_chat":
        reply = await ai_response(MAIN_PROMPT + memory_ctx, uid, txt)
    else:
        reply = await ai_response(MAIN_PROMPT + memory_ctx, uid, txt)
        
    await update.message.reply_text(reply, reply_markup=back_menu() if u["stage"] != "menu" else main_menu(), parse_mode="HTML")

# ==================== CALLBACKS ====================
async def mood_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = update.effective_chat.id
    uid = q.from_user.id
    u = get_user(uid)
    score = int(q.data.split("_")[1])
    labels = {5:"Ajoyib 🤩", 4:"Yaxshi 🙂", 3:"O'rtacha 😐", 2:"Yomon 😟", 1:"Juda yomon 😭"}
    
    if "moods" not in u:
        u["moods"] = []
    u["moods"].append({"score": score, "label": labels[score], "date": datetime.now().strftime("%d.%m.%Y %H:%M")})
    u["stage"] = "mood_chat"
    u["history"] = []
    save_data()
    
    if score >= 4:
        await send_bot_sticker(context, chat_id, "hello")
    elif score == 3:
        await send_bot_sticker(context, chat_id, "menu")
    else:
        await send_bot_sticker(context, chat_id, "dard")

    responses = {
        5: "🤩 <b>Ajoyib! Ichki olamingiz quyoshli ekanidan juda xursandman!</b>\n\nUshbu yuqori energiyani saqlab qolish va atrofdagilarga ham ulashish uchun bugun hayotingizdagi 3 ta eng katta shukronalik sababini yozing. Nima sizni bugun bunchalik baxtli qildi?",
        4: "🙂 <b>Yaxshi kayfiyat — bu xotirjam qalb belgisidir.</b>\n\nBugun kun davomida sodir bo'lgan aynan qaysi voqea yoki kichik bir e'tibor sizga tabassum hadya etdi? Men bilan bo'lishing.",
        3: "😐 <b>O'rtacha holat... Xuddi neytral zonada turgandeksiniz.</b>\n\nIchki muvozanatni to'liq quvonch tomonga o'tkazishga nima to'sqinlik qilyapti? Hozir sizni biroz o'ylantirayotgan narsaning o'zi nima?",
        2: "😟 <b>Kayfiyatingiz biroz tushibdi, lekin unutmang, bulutli kunlardan keyin albatta quyosh chiqadi.</b>\n\nBugun aynan qaysi holat, vaziyat yoki insonning gapi sizning ichki energiyangizni so'ndirdi? Keling, birga tahlil qilamiz.",
        1: "😭 <b>Siz juda og'ir va qorong'u ruhiy holatni boshdan kechiryapsiz...</b>\n\nMen sizni mutloq tushunaman va qoralamayman. Hozir ichingizda to'planib qolgan barcha alam, g'azab yoki og'riqni matnga to'kib soling. Men tinglashga to'liq tayyorman."
    }
    await q.edit_message_text(responses[score], parse_mode="HTML")

MEDS_DATA = [
    ("🧠 Tana skaneri (Mindfulness mashqi)", "<b>Maqsad:</b> Tanadagi barcha jismoniy zo'riqish va stress bloklarini bo'shashtirish.\n\n1️⃣ Ko'zlaringizni asta yuming va 3 marta burundan nafas olib, og'izdan chiqaring.\n2️⃣ Diqqatingizni oyoq barmoqlaringizga qarating, u yerdagi taranglikni his qiling va 'qo'yib yuboring'.\n3️⃣ Sekin-asta yuqoriga ko'tarilib — boldir, tizza, qorin, yelka va yuz mushaklaringizni navbat bilan bo'shashtiring.\n4️⃣ Tana to'liq bo'shashganda yengillikni his eting."),
    ("🌊 Ruhiy xotirjamlik daryosi", "<b>Maqsad:</b> Miyadagi tartibsiz fikrlardan qutulish.\n\n1️⃣ Tasavvuringizda sokin daryo va uning qirg'og'ida o'tirganingizni keltiring.\n2️⃣ Miya pufakchalari kabi kelayotgan har bir tashvishli fikrni daryo yuziga tushayotgan xazon (barg) deb biling.\n3️⃣ U fikrlar bilan urushmang, shunchaki oqib ketishini chetdan kuzating. Fikrlar keladi va oqib ketadi, siz esa joyingizdasiz."),
    ("☀️ Tonggi energiya zaryadi", "<b>Maqsad:</b> Kunni yuqori ishtiyoq va aniq maqsad bilan boshlash.\n\n1️⃣ Qodir bo'lsangiz qo'llaringizni yuqoriga cho'zing va ko'kragingizni keng oching.\n2️⃣ 5 marta juda tez va chuqur nafas oling.\n3️⃣ Ichingizda 'Bismillah, bugun yangi imkoniyatlar kuni va men eng yaxshi natijaga loyiqman' deb 3 marta qaytaring."),
    ("🌌 Kechki uyqu oldi tinchlanish", "<b>Maqsad:</b> Kunlik charchoqni yo'qotish va chuqur uyquga tayyorlanish.\n\n1️⃣ Yotoqda tekis yoting, butun vujudingizni erkin qo'ying.\n2️⃣ Bugun sodir bo'lgan, xoh u kichik bo'lsin, 3 ta eng yaxshi voqeani eslang va yaratganga shukr qiling.\n3️⃣ Fikrlaringizni o'chirib, faqatgina nafas olish maromingizga diqqat qaratgancha ko'zingizni yuming.")
]

async def med_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split("_")[1])
    await q.edit_message_text(f"🧘‍♂️ <b>{MEDS_DATA[idx][0]}</b>\n\n{MEDS_DATA[idx][1]}", parse_mode="HTML")

BREATHS_DATA = [
    ("😰 Tashvish uchun — 4-7-8 nafas texnikasi", "⏱ <b>Bajarish tartibi:</b>\n1. 4 soniya davomida burundan chuqur nafas oling.\n2. Nafasni ichingizda to'liq 7 soniya ushlab turing.\n3. 8 soniya davomida og'zingizdan sekin va ovoz chiqarib puflang.\n\n🔄 Buni ketma-ket 4 marta bajaring. Bu yurak urishini sekinlashtiradi va miyaga xavfsizlik signalini beradi."),
    ("😡 G'azab uchun — Quti (Box) nafasi", "⏱ <b>Bajarish tartibi:</b>\n1. 4 soniya nafas oling.\n2. 4 soniya nafasni ushlab turing.\n3. 4 soniya davomida nafasni chiqaring.\n4. 4 soniya nafas olmasdan kuting.\n\n🔄 Buni 5 marta aylantirib bajaring. Stress gormoni (kortizol) darajasini tezda tushiradi."),
    ("😴 Uyqusizlik uchun chuqur tinchlanish", "⏱ <b>Bajarish tartibi:</b>\nKo'zlarni yumgan holda, burundan sekin va chuqur nafas olib, onu 2 soniya ushlab, so'ng nafas olishdan ikki barobar uzoqroq vaqt davomida og'izdan sekin chiqaring. Faqat havoning o'pkaningizga kirib-chiqishiga diqqat qiling."),
    ("😮‍cv Stress uchun fiziologik xo'rsinish", "⏱ <b>Bajarish tartibi:</b>\n1. Burundan ketma-ket 2 marta chuqur nafas oling (biri uzun, ikkinchisi ketidan darhol qisqa o'pkani to'ldirish uchun).\n2. Og'izdan uzooo-o'q qilib xo'rsinish singari erkin chiqaring.\n\n🔄 3 marta bajarish kognitiv yukni darhol kamaytiruvchi ta'sir ko'rsatadi."),
    ("🍃 Umumiy diafragma nafasi", "⏱ <b>Bajarish tartibi:</b>\nBir qo'lingizni ko'kragingizga, ikkinchisini qoriningizga qo'ying. Nafas olganda ko'kragingiz emas, qoriningiz shishishi kerak. 4 soniya qorin bilan nafas olib, 4 soniya chiqaring. O'pkalarni kislorod bilan to'ydiradi.")
]

async def breath_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    idx = int(q.data.split("_")[1])
    u["stage"] = "nafas_chat"
    u["history"] = []
    save_data()
    await q.edit_message_text(f"🫁 <b>{BREATHS_DATA[idx][0]}</b>\n\n{BREATHS_DATA[idx][1]}\n\n<i>Mashqni bajarib bo'lgach, holatingiz qanday o'zgarganini matn ko'rinishida yozib qoldirishingiz mumkin, men tahlil qilaman...</i>", parse_mode="HTML")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(f"📊 <b>Botdan foydalanuvchilar jami soni:</b> {len(users)} ta", parse_mode="HTML")

# ==================== MAIN FUNKSIYA ====================
def main():
    load_data() 
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(mood_cb, pattern="^mood_"))
    app.add_handler(CallbackQueryHandler(med_cb, pattern="^med_"))
    app.add_handler(CallbackQueryHandler(breath_cb, pattern="^breath_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
         
