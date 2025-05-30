import os
import time
import hmac
import hashlib
import base64
import requests
import tempfile
import warnings
import sqlite3
from pydub import AudioSegment
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
import logging
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = TeleBot(TOKEN)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

ffmpeg_bin_path = r"D:\abdulaziz\ffmpeg-7.1.1-essentials_build\bin"
os.environ["PATH"] += os.pathsep + ffmpeg_bin_path


AudioSegment.converter = os.path.join(ffmpeg_bin_path, "ffmpeg.exe")
AudioSegment.ffprobe = os.path.join(ffmpeg_bin_path, "ffprobe.exe")

warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv")


conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    username TEXT,
    phone TEXT
)
''')
conn.commit()


def save_user_data(chat_id, username, phone):
    try:
        cursor.execute('INSERT INTO users (chat_id, username, phone) VALUES (?, ?, ?)', (chat_id, username, phone))
        conn.commit()
    except sqlite3.IntegrityError:
        raise Exception("User already exists")

def get_user(chat_id):
    cursor.execute('SELECT username, phone FROM users WHERE chat_id = ?', (chat_id,))
    row = cursor.fetchone()
    if row:
        return {"username": row[0], "phone": row[1]}
    return None


def send_contact():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    button = KeyboardButton("Поделиться контактом", request_contact=True)
    keyboard.add(button)
    return keyboard


@bot.message_handler(commands=['start'])
def start_command(message: Message):
    chat_id = message.chat.id
    username = message.from_user.username
    user = get_user(chat_id)

    logger.info(f"Команда /start от {chat_id} (@{username})")

    if user:
        msg = f'Привет, {username}! Вас приветствует Бот Музыкант.'
        bot.send_message(chat_id, msg)
    else:
        bot.send_message(chat_id, 'Пройдите регистрацию, для использования Бота. Поделитесь контактом',
                         reply_markup=send_contact())


@bot.message_handler(content_types=['contact'])
def register_user(message: Message):
    chat_id = message.chat.id
    phone = message.contact.phone_number
    username = message.from_user.username
    try:
        save_user_data(chat_id, username, phone)
        bot.send_message(chat_id, 'Регистрация прошла успешно', reply_markup=ReplyKeyboardRemove())
    except:
        bot.send_message(chat_id, 'Вы уже зарегистрированны. Можете пользоваться Ботом Теперь Можете отправить голосовой И бот попытается Распознать')


def create_signature(access_secret, string_to_sign):
    sign = hmac.new(
        access_secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha1
    ).digest()
    return base64.b64encode(sign).decode()


def recognize_audio(file_path):
    access_key = "af4a09caf6fab93f5b73016dd57499e3"
    access_secret = "kYFWFeM0oHAHKGrdmGgZdl7yoDy22sWD9rZeWVnQ"
    host = "identify-ap-southeast-1.acrcloud.com"
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    string_to_sign = "\n".join([
        http_method,
        http_uri,
        access_key,
        data_type,
        signature_version,
        timestamp
    ])

    signature = create_signature(access_secret, string_to_sign)

    audio_segment = AudioSegment.from_wav(file_path)
    duration = int(audio_segment.duration_seconds)
    logger.info(f"Длительность аудио: {duration} сек")
    file_size = os.path.getsize(file_path)
    data = {
        'access_key': access_key,
        'timestamp': timestamp,
        'signature': signature,
        'data_type': data_type,
        'signature_version': signature_version,
        'sample_bytes': str(file_size),
        'audio_length_sec': duration  # Можно раскомментировать, если API поддержит
    }

    url = f"https://{host}{http_uri}"

    with open(file_path, 'rb') as f:
        files = {
            'sample': f
        }
        response = requests.post(url, files=files, data=data)

    return response.json()


@bot.message_handler(content_types=['voice'])
def handle_voice(message: Message):
    chat_id = message.chat.id
    username = message.from_user.username or "Пользователь"

    logger.info(f"Получено голосовое сообщение от {chat_id} (@{username})")

    try:
        file_info = bot.get_file(message.voice.file_id)
        file_path = file_info.file_path
        downloaded_file = bot.download_file(file_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_ogg:
            tmp_ogg.write(downloaded_file)
            ogg_path = tmp_ogg.name

        wav_path = ogg_path.replace('.ogg', '.wav')
        audio = AudioSegment.from_ogg(ogg_path)
        audio = audio.set_channels(2).set_frame_rate(44100)
        audio.export(wav_path, format="wav")

        logger.info(f"Файл сохранён и конвертирован: {wav_path}")

        result = recognize_audio(wav_path)

        os.remove(ogg_path)
        os.remove(wav_path)

        logger.info(f"Результат ACRCloud: {result}")

        status = result.get('status', {})
        if status.get('code') == 0:
            metadata = result.get('metadata', {})
            music = metadata.get('music', [])
            if music:
                track = music[0]
                title = track.get('title')
                artists = ", ".join(artist['name'] for artist in track.get('artists', []))
                msg = f"Я распознал:\n🎵 {title}\n👤 {artists}"
            else:
                msg = "Не смог распознать музыку."
        else:
            msg = f"Ошибка распознавания: {status.get('msg')}"
            logger.warning(f"Ошибка ACRCloud: {status}")

        bot.send_message(chat_id, msg)

    except Exception as e:
        logger.exception(f"Ошибка при обработке голосового от {chat_id} (@{username}): {e}")
        bot.send_message(chat_id, "Произошла ошибка при обработке аудио.")


logger.info(f"База данных расположена по пути: {os.path.abspath('users.db')}")
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
logger.info(f"Структура таблицы users: {columns}")

GENIUS_ACCESS_TOKEN = "Bearer z-O5cLnGbqRoK0Fg6VQyqye1IBTYKINZEsqfXXd9gyfVyhpX6SeLG-dfNE2ikQt2"

headers = {"Authorization": GENIUS_ACCESS_TOKEN}


def search_songs(query):
    url = "https://api.genius.com/search"
    params = {"q": query}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    hits = data.get("response", {}).get("hits", [])
    results = []
    for hit in hits[:5]:  # первые 5 результатов
        song = hit["result"]
        results.append({
            "id": song["id"],
            "title": song["title"],
            "artist": song["primary_artist"]["name"],
            "url": song["url"],
            "cover": song["song_art_image_thumbnail_url"]
        })
    return results

def get_song_details(song_id):
    url = f"https://api.genius.com/songs/{song_id}"
    response = requests.get(url, headers=headers)
    data = response.json()
    song = data.get("response", {}).get("song", {})
    return {
        "title": song.get("title"),
        "artist": song.get("primary_artist", {}).get("name"),
        "url": song.get("url"),
        "cover": song.get("song_art_image_thumbnail_url")
    }

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Отправь название песни или часть текста, я найду её для тебя.")

@bot.message_handler(func=lambda m: True)
def handle_search(message):
    query = message.text.strip()
    bot.send_chat_action(message.chat.id, 'typing')
    results = search_songs(query)
    if not results:
        bot.reply_to(message, "Ничего не найдено, попробуй другое название или текст.")
        return

    for song in results:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Выбрать эту песню", callback_data=str(song["id"])))

        caption = f"🎵 <b>{song['title']}</b>\n👤 {song['artist']}"
        bot.send_photo(message.chat.id, song['cover'], caption=caption, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    song_id = call.data
    bot.answer_callback_query(call.id)
    details = get_song_details(song_id)
    if not details:
        bot.send_message(call.message.chat.id, "Не удалось получить данные о песне.")
        return
    text = (
        f"🎵 <b>{details['title']}</b>\n"
        f"👤 Исполнитель: {details['artist']}\n"
        f"🔗 Ссылка: {details['url']}"
    )
    bot.send_photo(call.message.chat.id, details["cover"], caption=text, parse_mode='HTML')



conn.close()
bot.infinity_polling()

