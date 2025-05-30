import sqlite3

def create_table_users():
    db = sqlite3.connect('translate.db')
    cursor = db.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id BIGINT UNIQUE,
        username VARCHAR(50) DEFAULT "user",
        phone VARCHAR(30)
    );
    ''')
    db.commit()
    db.close()

# create_table_users()

def save_user_data(*args):
    db = sqlite3.connect('translate.db')
    cursor = db.cursor()
    cursor.execute('''
    INSERT INTO users(telegram_id, username, phone)
    VALUES(?, ?, ?)
    ''', args)
    db.commit()
    db.close()

# Функция для получения пользователя из БД по id
def get_user(telegram_id):
    db = sqlite3.connect('translate.db')
    cursor = db.cursor()
    cursor.execute('''
    SELECT * FROM users WHERE telegram_id = ?
    ''', (telegram_id,))
    user = cursor.fetchone()
    db.close()
    return user


def create_table_history():
    db = sqlite3.connect('translate.db')
    cursor = db.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id BIGINT,
        src VARCHAR(10),
        dest VARCHAR(10),
        text TEXT,
        result TEXT
    );
    ''')
    db.commit()
    db.close()

# create_table_history()

def save_history(*args):
    db = sqlite3.connect('translate.db')
    cursor = db.cursor()
    cursor.execute('''
    INSERT INTO history(telegram_id, src, dest, text, result)
    VALUES(? ,?, ?, ?, ?)
    ''', args)
    db.commit()
    db.close()



def get_history(telegram_id):
    db = sqlite3.connect('translate.db')
    cursor = db.cursor()
    cursor.execute('''
    SELECT src, dest, text, result FROM history
    WHERE telegram_id = ?
    ''', (telegram_id,))
    history = cursor.fetchall()[-5:]
    db.close()
    return history




