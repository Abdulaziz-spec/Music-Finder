from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def send_contact():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn = KeyboardButton(text='Подеится контактом ☎️', request_contact=True)
    markup.add(btn)
    return markup

