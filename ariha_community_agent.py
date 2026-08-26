
# -*- coding: utf-8 -*-

import json
import re
import time
import random
import csv
import os
import requests
import threading
import threading
from datetime import datetime, timedelta, time as dt_time
from openai import OpenAI
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ======================== НАСТРОЙКИ ========================
GROUP_TOKEN = "vk1.a.TQn_giOgaA_2rtgVAuKUbGRrBkppSGca0cx-wn9A0W-lND5nz-e3C3uq69l26AYnk5nfIWAPzL957EBnFL1ZXrkTB4yY2RN_Rxo6vyUGSY2RtogSVDqYJ89LO8vy8Q7fDcz8J--Z4dLtRPk-loKXiYuGu-aMH0cmSde_Laj1U-fBP2F5ldnmLIwY2ptCjYXMdbDwpMKqnwcMpAdOj78CHQ"
GROUP_ID = 24794761

OPENAI_API_BASE = "https://api.proxyapi.ru/openai/v1"
OPENAI_API_KEY = "sk-SxCSVAeWBwdT7E3Ad9bCNeklZYtAbV1S"
OPENAI_MODEL = "gpt-4.1"

MEMORY_LIMIT = 20

# ======================== ТЕСТОВЫЙ РЕЖИМ ========================
TEST_MODE = False
AUTO_ACTIVE = True

# ======================== ВЛАДЕЛЕЦ ========================
OWNER_USER_ID = 14394534

# ======================== ССЫЛКИ ========================
LINKS = {
    "link_video_age": "https://vkvideo.ru/video-24794761_456239340?list=ln-VYeGj4o3kb1qbUvXtW",
    "link_video_first": "https://vkvideo.ru/video-24794761_456239469",
    "link_video_wow": "https://vkvideo.ru/video-24794761_456239468?list=ln-0mHIzsuPzwiy51buoU",
    "link_course_main": "https://fyodorzheganin.getcourse.ru/page4707828",
    "link_course_basic": "https://fyodorzheganin.getcourse.ru/page4707585",
    "link_chat": "https://max.ru/join/ECvnr2EPX9_zM0U0lc2vuICKbz-K1BtEF7lDZo7irD8",
    "link_owner_page": "https://vk.com/id14394534",
    "link_free_lesson": "https://vkvideo.ru/video-24794761_456239406"
}

# ======================== ЧТЕНИЕ ПРОМТА ========================
def load_system_prompt():
    prompt_path = os.path.join(SCRIPT_DIR, "ariha_prompt.txt")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"✅ Промт загружен из файла: {prompt_path}")
        print(f"📄 Первые 200 символов промта:\n{content[:200]}...\n")
        return content
    except FileNotFoundError:
        print(f"❌ Файл {prompt_path} не найден! Убедись, что он лежит в той же папке.")
        return "Ты — Ариша, ИИ-администратор сообщества Фёдора Жеганина. Отвечай тепло и коротко."

BASE_SYSTEM_PROMPT = load_system_prompt()

# ======================== ПАМЯТЬ ========================
USERS_MEMORY_FILE = os.path.join(SCRIPT_DIR, 'community_users.json')

def load_users_memory():
    try:
        with open(USERS_MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users_memory(data):
    with open(USERS_MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_memory(user_id):
    users = load_users_memory()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "name": "",
            "stage": "выявление_боли",
            "history": [],
            "status": "new",
            "temperature": "cold",
            "source": "direct",
            "first_message_sent_at": None,
            "first_message_id": None,
            "last_activity_at": None,
            "reminder_sent": False,
            "reminder_sent_at": None,
            "last_message_at": None,
            "last_read_state": None,
            "purchased": False,
            "welcome_sent": False,
            "welcome_sent_at": None,
            "pain_done": False,
            "pain_done_at": None,
            "gave_weight_height": False,
            "probe_lesson_sent": False,
            "probe_lesson_sent_at": None,
            "probe_lesson_responded": False,
            "probe_followup_stage": 0
        }
        save_users_memory(users)
        print(f"🆕 Создана новая запись для пользователя {uid}")
    return users[uid]

def update_user_memory(user_id, data):
    users = load_users_memory()
    uid = str(user_id)
    if uid in users:
        users[uid].update(data)
        save_users_memory(users)
        print(f"💾 Обновлена запись для пользователя {uid}: {data}")

# ======================== ВРЕМЯ ========================
def is_active_time():
    now = datetime.now().time()
    start = dt_time(6, 0)
    end = dt_time(20, 30)
    return start <= now <= end

# ======================== ОБРАБОТКА ОТВЕТА ИИ ========================
def extract_stage(text):
    match = re.search(r'STAGE:\s*([а-яА-Яa-zA-Z_]+)', text)
    return match.group(1).lower() if match else None

def clean_response(text):
    return re.sub(r'STAGE:\s*[а-яА-Яa-zA-Z_]+\s*', '', text).strip()

def get_ai_answer(user_id, user_message):
    user_data = get_user_memory(user_id)
    current_stage = user_data.get('stage', 'выявление_боли')
    name = user_data.get('name', '')
    history = user_data.get('history', [])[-MEMORY_LIMIT:]

    system_prompt = BASE_SYSTEM_PROMPT.format(
        stage=current_stage,
        name=name if name else 'Неизвестно',
        link_video_age=LINKS["link_video_age"],
        link_video_first=LINKS["link_video_first"],
        link_video_wow=LINKS["link_video_wow"],
        link_course_main=LINKS["link_course_main"],
        link_course_basic=LINKS["link_course_basic"],
        link_chat=LINKS["link_chat"],
        link_free_lesson=LINKS["link_free_lesson"]
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        if isinstance(h, dict):
            messages.append(h)
        elif isinstance(h, str):
            messages.append({"role": "user", "content": h})
    messages.append({"role": "user", "content": user_message})

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=800,
            timeout=30
        )
        ai_text = response.choices[0].message.content
        print(f"🤖 ИИ ответил:\n{ai_text}\n")
    except Exception as e:
        print(f"[ERROR] Ошибка OpenAI: {e}")
        return "Извините, технический сбой. Попробуйте позже.", None

    new_stage = extract_stage(ai_text)
    cleaned = clean_response(ai_text)
    print(f"🏁 Этап после ответа: {new_stage}")
    return cleaned, new_stage

# ======================== ОТПРАВКА СООБЩЕНИЙ ========================
def send_vk_message(vk_session, user_id=None, peer_id=None, message=""):
    if user_id:
        print(f"📤 Отправляю сообщение пользователю {user_id}:\n{message}\n")
    elif peer_id:
        print(f"📤 Отправляю сообщение в чат {peer_id}:\n{message}\n")

    if TEST_MODE:
        fake_message_id = random.randint(1000000, 9999999)
        return fake_message_id

    try:
        if user_id:
            response = vk_session.get_api().messages.send(
                user_id=user_id,
                random_id=random.randint(1, 2**31),
                message=message
            )
        elif peer_id:
            response = vk_session.get_api().messages.send(
                peer_id=peer_id,
                random_id=random.randint(1, 2**31),
                message=message
            )
        print(f"✅ Сообщение отправлено пользователю {user_id or peer_id}")
        return response

    except vk_api.exceptions.ApiError as e:
        code = getattr(e, 'code', None)
        if code in (901, 902, 903, 917):
            print(f"❌ Невозможно отправить сообщение пользователю {user_id or peer_id}. Код {code}. Помечаем как unavailable.")
            return False
        else:
            print(f"[ERROR] Ошибка VK API: {e}")
            return None

    except Exception as e:
        print(f"[ERROR] Ошибка отправки: {e}")
        return None

# ======================== ЧАТ-РЕЖИМ ========================
CHAT_STATE_FILE = os.path.join(SCRIPT_DIR, 'chat_state.json')

def load_chat_state():
    try:
        with open(CHAT_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"last_message_time": None, "last_direct_time": None, "messages_sent_today": 0, "date": str(datetime.now().date()), "last_welcome_time": None}

def save_chat_state(state):
    with open(CHAT_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def is_direct_mention(text):
    return text.strip().lower().startswith("ариша")

def can_send_in_chat(direct=False):
    state = load_chat_state()
    today = str(datetime.now().date())
    if state.get("date") != today:
        state = {"last_message_time": None, "last_direct_time": None, "messages_sent_today": 0, "date": today, "last_welcome_time": state.get("last_welcome_time")}
        save_chat_state(state)

    if state.get("messages_sent_today", 0) >= 9:
        return False

    if direct:
        interval = timedelta(minutes=3)
        last_time_key = "last_direct_time"
    else:
        interval = timedelta(minutes=8)
        last_time_key = "last_message_time"

    if state.get(last_time_key):
        last = datetime.fromisoformat(state[last_time_key])
        if datetime.now() - last < interval:
            return False

    return True

def update_chat_state_after_send(direct=False):
    state = load_chat_state()
    if direct:
        state["last_direct_time"] = datetime.now().isoformat()
    else:
        state["last_message_time"] = datetime.now().isoformat()
    state["messages_sent_today"] = state.get("messages_sent_today", 0) + 1
    state["date"] = str(datetime.now().date())
    save_chat_state(state)

def is_chat_relevant_message(text):
    lowered = text.lower()
    if "ариша" in lowered:
        return True
    keywords = ["живот", "отек", "отёк", "усталость", "вес", "дыхание", "похудение"]
    return any(word in lowered for word in keywords)

def get_chat_reply(text):
    system_prompt = """Ты — Ариша, ИИ-администратор сообщества Фёдора Жеганина.
Ты в общем чате. Отвечай коротко, по-дружески, 1–2 предложения.
Если вопрос не по теме, мягко скажи, что лучше написать в личные сообщения сообщества."""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=200,
            timeout=30
        )
        reply = response.choices[0].message.content.strip()
        print(f"💬 Ответ для чата:\n{reply}\n")
        return reply
    except Exception as e:
        print(f"[ERROR] Ошибка OpenAI для чата: {e}")
        return None

# ======================== ПРИВЕТСТВИЕ В ЧАТЕ ========================
def can_send_welcome():
    state = load_chat_state()
    last = state.get('last_welcome_time')
    if not last:
        return True
    last_dt = datetime.fromisoformat(last)
    return datetime.now() - last_dt >= timedelta(minutes=10)

def send_chat_welcome(vk_session, peer_id):
    if not can_send_welcome():
        print("⏳ Чат: приветствие недавно уже отправлялось.")
        return
    welcome_text = (
        "Здравствуйте! Я Ариша, виртуальный помощник Фёдора Александровича. "
        "Если хотите со мной пообщаться, напишите сообщение, которое начинается с моего имени. "
        "Например: «Ариша, подскажи, когда ближайший эфир?» И я вам отвечу. "
        "Рада знакомству 🙂"
    )
    if send_vk_message(vk_session, peer_id=peer_id, message=welcome_text):
        state = load_chat_state()
        state['last_welcome_time'] = datetime.now().isoformat()
        save_chat_state(state)
        print(f"👋 Приветствие отправлено в чат {peer_id}")

# ======================== АНАЛИТИКА ========================
ANALYTICS_FILE = os.path.join(SCRIPT_DIR, 'community_analytics.csv')

def log_event(user_id, event):
    with open(ANALYTICS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), user_id, event])
    print(f"📊 Событие: {event} для пользователя {user_id}")

# ======================== ОПРЕДЕЛЕНИЕ НЕГАТИВА ========================
def is_negative_reply(text):
    negative_phrases = [
        "иди нафиг", "пошел нафиг", "отстань", "достали", "надоело", "хватит",
        "прекратите", "забаньте меня", "я на вас пожалуюсь",
        "жулики", "обманщики", "лохотрон", "развод", "кидалово", "всё враньё",
        "не верю", "враньё",
        "не пишите мне", "удалите меня из базы", "сколько можно",
        "нет", "не интересно", "не надо", "не актуально", "спам"
    ]
    lowered = text.lower()
    return any(phrase in lowered for phrase in negative_phrases)

# ======================== ОПРЕДЕЛЕНИЕ ГОРЯЧЕГО НАМЕРЕНИЯ ========================
def is_purchase_intent(text):
    purchase_phrases = [
        "хочу купить", "хочу записаться", "хочу на курс", "готова оплатить",
        "как оплатить", "свяжитесь с фёдором", "хочу лично пообщаться",
        "хочу пообщаться", "давайте созвонимся", "можно консультацию",
        "хочу консультацию", "хочу заниматься", "записаться на интенсив",
        "записаться на курс", "как записаться", "передайте фёдору",
        "можно телефон", "как связаться"
    ]
    lowered = text.lower()
    return any(phrase in lowered for phrase in purchase_phrases)

# ======================== ГЕНЕРАЦИЯ АКТИВНОГО СООБЩЕНИЯ ========================
def generate_active_first_message():
    first_line = "Здравствуйте! Я Ариша, я новый ИИ-администратор Фёдора Александровича."
    prompt = (
        "Ты — Ариша, ИИ-администратор сообщества Фёдора Жеганина. "
        "Напиши продолжение первого сообщения для старого клиента, который когда-то писал в сообщество. "
        "Продолжение должно состоять из 2-4 предложений. "
        "Упомяни, что ты видишь его прошлое сообщение, и мягко спроси, актуальна ли тема дыхания и снижения веса. "
        "Не используй ссылки. Не дави. Пиши тепло и по-человечески."
    )
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Сгенерируй продолжение первого сообщения."}
            ],
            temperature=0.7,
            max_tokens=200,
            timeout=30
        )
        continuation = response.choices[0].message.content.strip()
        continuation = continuation.strip('"').strip("«").strip("»").strip()
        return f"{first_line}\n{continuation}"
    except Exception as e:
        print(f"[ERROR] Ошибка генерации активного сообщения: {e}")
        return (
            first_line + "\n"
            "Вижу, вы когда-то писали в наше сообщество. "
            "Если тема дыхания и весовой коррекции ещё актуальна, я с радостью расскажу о новых онлайн-программах. "
            "Хотите узнать подробнее?"
        )

# ======================== НОВЫЕ ПОДПИСЧИКИ (ПРИВЕТСТВИЕ) ========================
def check_newbie_welcome(vk_session):
    users = load_users_memory()
    now = datetime.now()
    changed = False

    for uid, data in users.items():
        if data.get('welcome_sent'):
            continue
        if data.get('status') not in ('new', 'in_dialog'):
            continue

        last_activity = data.get('last_activity_at')
        if not last_activity:
            continue

        last_activity_dt = datetime.fromisoformat(last_activity)
        diff = now - last_activity_dt

        if diff >= timedelta(minutes=12):
            message = (
                "Здравствуйте! Я Ариша, помощница Фёдора Александровича. "
                "Если у вас есть вопросы, пишите сюда — с удовольствием помогу. "
                "Если я не смогу ответить, передам ваш вопрос Фёдору Александровичу, и он с вами свяжется."
            )
            send_vk_message(vk_session, user_id=int(uid), message=message)
            update_user_memory(uid, {
                "welcome_sent": True,
                "welcome_sent_at": now.isoformat(),
                "temperature": "warm"
            })
            log_event(uid, "welcome_sent")
            print(f"👋 Приветствие отправлено пользователю {uid}")
            changed = True

    if changed:
        save_users_memory(users)

# ======================== ДОЖИМ ========================
def check_first_message_followups(vk_session):
    users = load_users_memory()
    now = datetime.now()
    changed = False

    for uid, data in users.items():
        status = data.get('status')
        if status != 'first_sent':
            continue
        first_sent_str = data.get('first_message_sent_at')
        if not first_sent_str:
            continue

        first_sent = datetime.fromisoformat(first_sent_str)
        diff = now - first_sent

        if diff >= timedelta(hours=24):
            reminder_sent = data.get('reminder_sent', False)
            if not reminder_sent:
                if data.get('first_message_id'):
                    is_read = is_message_read(vk_session, int(uid), data['first_message_id'])
                else:
                    is_read = False

                if is_read:
                    message = (
                        "Здравствуйте! Я вижу, вы прочитали моё сообщение, но не ответили. "
                        "Если тема ещё актуальна, я с радостью помогу. "
                        "Если нет — просто напишите «нет», и я больше не буду вас беспокоить. "
                        "Я не обижаюсь, я же робот-помощник 🙂"
                    )
                    if send_vk_message(vk_session, user_id=int(uid), message=message):
                        users[uid]['reminder_sent'] = True
                        users[uid]['reminder_sent_at'] = now.isoformat()
                        users[uid]['status'] = 'reminder_sent'
                        changed = True
                        print(f"🔔 Отправлено напоминание для {uid}")
                else:
                    print(f"⏳ Сообщение для {uid} ещё не прочитано, пропускаю.")

    if changed:
        save_users_memory(users)

def is_message_read(vk_session, user_id, message_id):
    try:
        vk = vk_session.get_api()
        history = vk.messages.getHistory(
            user_id=user_id,
            offset=0,
            count=5
        )
        for msg in history.get('items', []):
            if msg.get('id') == int(message_id):
                return msg.get('read_state') == 1
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка проверки прочтения для {user_id}: {e}")
        return False

def check_probe_followups(vk_session):
    users = load_users_memory()
    now = datetime.now()
    changed = False

    for uid, data in users.items():
        if not data.get("probe_lesson_sent"):
            continue
        if data.get("probe_lesson_responded"):
            continue

        sent_at = data.get("probe_lesson_sent_at")
        if not sent_at:
            continue

        sent_dt = datetime.fromisoformat(sent_at)
        diff = now - sent_dt
        stage = data.get("probe_followup_stage", 1)

        if stage == 1 and diff >= timedelta(minutes=40):
            message = "Как вам пробный урок? Удалось позаниматься?"
        elif stage == 2 and diff >= timedelta(hours=3):
            message = "Если ещё не успели — ничего страшного. Попробуйте, это займёт 15 минут. Как будет результат, напишите мне 🙂"
        elif stage == 3 and diff >= timedelta(hours=24):
            message = "Не забыли про пробный урок? Если есть вопросы, я рядом."
        elif stage == 4 and diff >= timedelta(hours=72):
            message = "Последнее напоминание: если тема ещё актуальна, дайте знать, и я помогу выбрать программу."
        else:
            continue

        if send_vk_message(vk_session, user_id=int(uid), message=message):
            users[uid]['probe_followup_stage'] = stage + 1
            changed = True
            print(f"ℹ️ Отправлено напоминание о пробном уроке пользователю {uid}")

    if changed:
        save_users_memory(users)

def check_followups(vk_session):
    check_first_message_followups(vk_session)
    check_probe_followups(vk_session)

# ======================== АКТИВНЫЙ РЕЖИМ ========================
ACTIVE_QUEUE_FILE = os.path.join(SCRIPT_DIR, 'warm_dialogs.csv')
SENT_ANCIENT_FILE = os.path.join(SCRIPT_DIR, 'sent_ancient.json')

def load_sent_ancient():
    try:
        with open(SENT_ANCIENT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_sent_ancient(data):
    with open(SENT_ANCIENT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_active_queue():
    sent = set(load_sent_ancient())
    users = load_users_memory()
    queue = []
    try:
        with open(ACTIVE_QUEUE_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        print(f"❌ Файл {ACTIVE_QUEUE_FILE} не найден. Активный режим недоступен.")
        return []

    def sort_key(row):
        date_str = row.get('last_message_date', '').strip()
        if not date_str:
            return datetime.min
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        except:
            return datetime.min

    rows.sort(key=sort_key)

    for row in rows:
        uid = row.get('user_id')
        if not uid:
            continue
        uid_int = int(uid)
        if uid_int in sent:
            continue
        status = users.get(str(uid_int), {}).get('status')
        if status in ('negative', 'do_not_disturb', 'purchased', 'closed', 'purchase_intent', 'unavailable'):
            continue
        queue.append(uid_int)
    return queue

def send_active_messages(vk_session):
    if not is_active_time():
        print("⏰ Сейчас не время для активной рассылки (06:00–20:30).")
        return

    queue = get_active_queue()
    if not queue:
        print("✅ Активная очередь пуста. Все старые контакты обработаны.")
        return

    limit = 20
    to_send = queue[:limit]

    sent = load_sent_ancient()
    for uid in to_send:
        print(f"\n🔄 Активный режим: отправляю сообщение для {uid}")

        message = generate_active_first_message()
        message_id = send_vk_message(vk_session, user_id=uid, message=message)
        if message_id:
            sent.append(uid)
            save_sent_ancient(sent)
            user_data = get_user_memory(uid)
            update_user_memory(uid, {
                "status": "first_sent",
                "first_message_sent_at": datetime.now().isoformat(),
                "first_message_id": str(message_id)
            })
            log_event(uid, "first_message_sent")
            pause = random.randint(28*60, 32*60)
            print(f"⏳ Пауза {pause} секунд...")
            time.sleep(pause)
        else:
            update_user_memory(uid, {"status": "unavailable"})
            log_event(uid, "unavailable")
            print(f"❌ Сообщение не доставлено. Пользователь {uid} помечен как unavailable.")
# ======================== ФОНОВЫЕ ПРОВЕРКИ ========================
def background_checks(vk_session):
    last_welcome_check = datetime.now() - timedelta(minutes=10)
    last_followup_check = datetime.now() - timedelta(minutes=30)

    while True:
        now = datetime.now()

        if now - last_welcome_check >= timedelta(minutes=5):
            try:
                print("\n=== ПРОВЕРКА НОВЫХ (фон) ===")
                check_newbie_welcome(vk_session)
            except Exception as e:
                print(f"[ERROR] Ошибка проверки новых: {e}")
            last_welcome_check = now

        if now - last_followup_check >= timedelta(minutes=20):
            try:
                print("\n=== ПРОВЕРКА ДОЖИМА (фон) ===")
                check_followups(vk_session)
            except Exception as e:
                print(f"[ERROR] Ошибка проверки дожима: {e}")
            last_followup_check = now

        time.sleep(30)  # спим 30 секунд, чтобы не нагружать процессор
# ======================== ОСНОВНОЙ ЦИКЛ ========================
def main():
        # Запускаем фоновые проверки
    background_thread = threading.Thread(target=background_checks, args=(vk_session,), daemon=True)
    background_thread.start()
    vk_session = vk_api.VkApi(token=GROUP_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=GROUP_ID)

    print("🚀 Агент сообщества запущен (личные + чат + активный режим + дожим).")
    if TEST_MODE:
        print("🔔 ВНИМАНИЕ! Тестовый режим: реальные сообщения не отправляются.")

    if AUTO_ACTIVE:
        print("\n=== АКТИВНЫЙ РЕЖИМ (фоновый) ===")
        active_thread = threading.Thread(target=send_active_messages, args=(vk_session,), daemon=True)
        active_thread.start()
    print("\n=== ПАССИВНЫЙ РЕЖИМ ===")

    last_followup_time = datetime.now() - timedelta(minutes=30)
    last_welcome_time = datetime.now() - timedelta(minutes=10)

    while True:
        try:
            now = datetime.now()

            # Проверяем новых подписчиков каждые 5 минут
            if now - last_welcome_time >= timedelta(minutes=5):
                print("\n=== ПРОВЕРКА НОВЫХ ===")
                check_newbie_welcome(vk_session)
                last_welcome_time = now

            # Проверяем дожим каждые 20 минут
            if now - last_followup_time >= timedelta(minutes=20):
                print("\n=== ПРОВЕРКА ДОЖИМА ===")
                check_followups(vk_session)
                last_followup_time = now

            for event in longpoll.listen():
                if event.type == VkBotEventType.MESSAGE_NEW:
                    message = event.obj.message
                    from_id = message.get('from_id')
                    peer_id = message.get('peer_id')
                    text = message.get('text', '').strip()
                    action_type = message.get('action_type')

                    if from_id < 0:
                        print(f"🚫 Пропущено сообщение от сообщества (id={from_id})")
                        continue

                    if action_type in ('chat_invite_user', 'chat_join'):
                        if peer_id != from_id:
                            print(f"👋 Новый участник в чате {peer_id}, action_type={action_type}")
                            send_chat_welcome(vk_session, peer_id)
                        continue

                    if not text:
                        continue

                    print(f"📥 Получено: from_id={from_id}, peer_id={peer_id}, text={text}")

                    if peer_id == from_id:
                        log_event(from_id, "message_received")
                        user_data = get_user_memory(from_id)
                        update_user_memory(from_id, {"last_activity_at": datetime.now().isoformat()})

                        if user_data.get('status') in ('negative', 'do_not_disturb'):
                            print(f"🚫 Пользователь {from_id} в стоп-листе. Не отвечаю.")
                            continue

                        if is_negative_reply(text):
                            print(f"⚠️ Пользователь {from_id} прислал негатив/отказ: {text}")
                            update_user_memory(from_id, {"status": "negative", "temperature": "cold"})
                            log_event(from_id, "negative")
                            apology = "Понимаю, извините, если побеспокоила. Я больше не буду вам писать. Хорошего дня!"
                            send_vk_message(vk_session, user_id=from_id, message=apology)
                            continue

                        if is_purchase_intent(text):
                            print(f"🔥 Горячее намерение от {from_id}: {text}")
                            update_user_memory(from_id, {
                                "status": "purchase_intent",
                                "temperature": "burning"
                            })
                            log_event(from_id, "purchase_intent")

                            client_reply = (
                                "Спасибо за интерес! Я передам ваш контакт Фёдору Александровичу. "
                                "Он свяжется с вами лично. Если хотите, можете написать ему напрямую: "
                                f"{LINKS['link_owner_page']}"
                            )
                            send_vk_message(vk_session, user_id=from_id, message=client_reply)

                            owner_notification = (
                                f"🔥 Запрос на покупку или личное общение!\n"
                                f"Пользователь ID: {from_id}\n"
                                f"Имя: {user_data.get('name', 'неизвестно')}\n"
                                f"Сообщение: {text}\n"
                                f"Ссылка на профиль: https://vk.com/id{from_id}\n"
                                f"Отправьте ему личное сообщение или свяжитесь."
                            )
                            send_vk_message(vk_session, user_id=OWNER_USER_ID, message=owner_notification)
                            continue

                        if user_data.get('status') == 'purchase_intent':
                            print(f"👤 Пользователь {from_id} уже ждёт контакта Фёдора.")
                            wait_reply = "Спасибо! Фёдор Александрович скоро свяжется с вами лично. Ожидайте сообщения."
                            send_vk_message(vk_session, user_id=from_id, message=wait_reply)
                            continue

                        if not user_data.get('name'):
                            try:
                                info = vk.users.get(user_ids=[from_id])[0]
                                name = info.get('first_name', '')
                                if name:
                                    update_user_memory(from_id, {"name": name})
                                    user_data['name'] = name
                                    print(f"👤 Получено имя: {name}")
                            except Exception as e:
                                print(f"[ERROR] Ошибка получения имени: {e}")

                        if not user_data.get('history'):
                            ai_response = "Здравствуйте! Я Ариша, я новый ИИ-администратор Фёдора Александровича.\n\nЧто вас сейчас больше всего беспокоит: живот, отёки, усталость?"
                            new_stage = "выявление_боли"
                        else:
                            ai_response, new_stage = get_ai_answer(from_id, text)

                        history = user_data.get('history', [])
                        history.append({"role": "user", "content": text})
                        history.append({"role": "assistant", "content": ai_response})
                        if len(history) > MEMORY_LIMIT * 2:
                            history = history[-MEMORY_LIMIT * 2:]

                        update_data = {
                            "history": history,
                            "last_message_at": datetime.now().isoformat(),
                            "status": "in_dialog",
                            "temperature": "warm"
                        }
                        if new_stage:
                            update_data["stage"] = new_stage
                        update_user_memory(from_id, update_data)

                        send_vk_message(vk_session, user_id=from_id, message=ai_response)
                        log_event(from_id, "ai_reply_sent")

                        if LINKS["link_free_lesson"] in ai_response:
                            update_user_memory(from_id, {
                                "probe_lesson_sent": True,
                                "probe_lesson_sent_at": datetime.now().isoformat(),
                                "probe_followup_stage": 1
                            })
                            log_event(from_id, "free_lesson_sent")
                            print(f"🎁 Бесплатный урок отправлен пользователю {from_id}")

                    else:
                        direct = is_direct_mention(text)
                        if direct:
                            if can_send_in_chat(direct=True):
                                chat_reply = get_chat_reply(text)
                                if chat_reply:
                                    send_vk_message(vk_session, peer_id=peer_id, message=chat_reply)
                                    update_chat_state_after_send(direct=True)
                                    print(f"💬 Ответ в чат отправлен: {chat_reply[:80]}...")
                            else:
                                print("⏳ Чат: лимит на прямое обращение ещё не прошёл")
                        else:
                            if is_chat_relevant_message(text) and can_send_in_chat(direct=False):
                                chat_reply = get_chat_reply(text)
                                if chat_reply:
                                    send_vk_message(vk_session, peer_id=peer_id, message=chat_reply)
                                    update_chat_state_after_send(direct=False)
                                    print(f"💬 Ответ в чат отправлен: {chat_reply[:80]}...")
                            else:
                                print("⏳ Чат: сообщение не релевантно или лимит")

                    time.sleep(0.5)

        except requests.exceptions.ReadTimeout:
            print("⚠️ Таймаут LongPoll. Перезапускаю прослушивание...")
            time.sleep(5)
        except Exception as e:
            print(f"[ERROR] Ошибка в основном цикле: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
