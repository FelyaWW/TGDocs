import psycopg2
from psycopg2 import sql
import telebot
from telebot import types
from telebot.formatting import escape_markdown
import os
import shutil
from datetime import datetime


# Проверка на существование базы данных
def check_database_exists(db_name, user, password, host='localhost', port='5432'):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=user,
            password=password,
            host=host,
            port=port
        )
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}';")
        exists = cursor.fetchone()
        cursor.close()
        return exists is not None
    except psycopg2.Error as e:
        print(f"Ошибка при проверке базы данных: {e}")
        return False
    finally:
        if conn:
            conn.close()


# Создание базы данных
def create_database(db_name, user, password, host='localhost', port='5432'):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(
            sql.Identifier(db_name)
        ))
        print(f"База данных '{db_name}' успешно создана.")
        cursor.close()
    except psycopg2.Error as e:
        print(f"Ошибка при создании базы данных: {e}")
    finally:
        if conn:
            conn.close()


# Подключение к базе данных
def create_connection(db_name, user, password, host='localhost', port='5432'):
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=user,
            password=password,
            host=host,
            port=port
        )
        return conn
    except psycopg2.Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
    return conn


# Создание таблиц
def create_tables(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS docs (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            body TEXT,
            user_id INTEGER REFERENCES users (id) ON DELETE CASCADE,
            tag VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
        cursor.close()
    except psycopg2.Error as e:
        print(f"Ошибка при создании таблиц: {e}")


# Добавление нового пользователя в таблицу users
def insert_user(conn, username):
    sql_query = ''' INSERT INTO users(username) VALUES(%s) RETURNING id; '''
    cursor = conn.cursor()
    cursor.execute(sql_query, (username,))
    user_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return user_id


# Получение ID пользователя по имени
def get_user_id_by_username(conn, username):
    sql_query = ''' SELECT id FROM users WHERE username = %s; '''
    cursor = conn.cursor()
    cursor.execute(sql_query, (username,))
    user = cursor.fetchone()
    cursor.close()
    if user:
        return user[0]
    return None


# Добавление новой записи в таблицу docs
def insert_doc(conn, title, body, user_id, tag):
    sql_query = ''' INSERT INTO docs(title, body, user_id, tag) VALUES(%s, %s, %s, %s) RETURNING id; '''
    cursor = conn.cursor()
    cursor.execute(sql_query, (title, psycopg2.Binary(body), user_id, tag))
    doc_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return doc_id


# Получение всех документов пользователя
def get_all_docs(conn, user_id):
    sql_query = ''' SELECT id, title, body, tag, created_at FROM docs WHERE user_id = %s; '''
    cursor = conn.cursor()
    cursor.execute(sql_query, (user_id,))
    docs = cursor.fetchall()
    cursor.close()
    return docs


# Отправка документа и его данных пользователю
def send_document(bot, chat_id, file_path, doc_data, user_id):
    with open(file_path, 'rb') as file:
        # Отправка файла
        bot.send_document(chat_id, file)

    # Формирование и отправка информации о файле
    doc_info = (
        f"User ID: {user_id}\n"
        f"Tag: {doc_data[3]}\n"
        f"Created at: {doc_data[4]}\n"
    )
    bot.send_message(chat_id, doc_info)


# Инициализация бота с токеном API
bot = telebot.TeleBot("7249509284:AAHwJ4My3WRnNiRMthQSbtGD9vppaj2AGcI")

# Создаем глобальное соединение с базой данных
db_name = 'my_new_database'
user = 'postgres'
password = 'mypassword'

# Проверяем наличие базы данных, если ее нет - создаем
if not check_database_exists(db_name, user, password, host='localhost', port='5432'):
    create_database(db_name, user, password, host='localhost', port='5432')

# Устанавливаем соединение
conn = create_connection(db_name, user, password, host='localhost', port='5432')

if conn is not None:
    create_tables(conn)
else:
    print("Ошибка! Не удалось подключиться к базе данных.")
    exit()


# Команда /start для приветствия и выбора действия
@bot.message_handler(commands=['start'])
def start(message):
    # Стартовое сообщение с описанием функционала бота
    start_message = (
        "👋 Добро пожаловать в нашего бота!\n\n"
        "📂 Этот бот предназначен для хранения и быстрого доступа к вашим документам.\n"
        "📥 Загрузите документ и получите быстрый доступ к ранее загруженным.\n"
        "🏷️ К каждому документу можно добавить тег — специальное обозначение, которое поможет сгруппировать ваши документы.\n"
        "📑 В дальнейшем, вы сможете выгрузить все документы с этим тегом для удобства.\n"
        "💬 В боте есть кнопка обратной связи — будем рады любому фидбеку.\n\n"
        "⬇️ Используйте клавиатуру ниже, чтобы начать!"
    )

    bot.send_message(message.chat.id, start_message)

    user_id = get_user_id_by_username(conn, message.from_user.username)
    if user_id:
        bot.send_message(message.chat.id, f"Вы уже зарегистрированы! Ваш ID: {user_id}")
    else:
        user_id = insert_user(conn, message.from_user.username)
        bot.send_message(message.chat.id, f"Добро пожаловать, {message.from_user.username}! Ваш новый ID: {user_id}")

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("📤 Загрузить новый документ")
    item2 = types.KeyboardButton("📜 Получить список документов")
    item3 = types.KeyboardButton("🔍 Поиск по тегу")
    item4 = types.KeyboardButton("🗑️ Удалить документ")
    item5 = types.KeyboardButton("💬 Оставить отзыв")

    markup.add(item1, item2, item3, item4, item5)
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)


ADMIN_CHAT_ID = "-4278187489"


@bot.message_handler(func=lambda message: message.text in ["💬 Оставить отзыв"])
def feedback(message):
    bot.send_message(message.chat.id, "Пожалуйста, напишите свой отзыв:")
    bot.register_next_step_handler(message, process_feedback)

# Обработка кнопки "🔍 Поиск по тегу"
@bot.message_handler(func=lambda message: message.text == "🔍 Поиск по тегу")
def search_button_handler(message):
    bot.send_message(message.chat.id, "Введите тег для поиска:")
    bot.register_next_step_handler(message, process_search_tag)

# Обработка кнопки "🗑️ Удалить документ"
@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить документ")
def delete_button_handler(message):
    bot.send_message(message.chat.id, "Введите ID документа для удаления:")
    bot.register_next_step_handler(message, process_delete_document)

# Обработка кнопки "💬 Оставить отзыв"
def process_feedback(message):
    feedback_text = message.text
    bot.send_message(ADMIN_CHAT_ID, f"Обратная связь от @{message.from_user.username}: {feedback_text}")
    bot.send_message(message.chat.id, "Ваш отзыв был отправлен администратору. Спасибо!")


# Обработка выбора действия
@bot.message_handler(func=lambda message: message.text in ["📤 Загрузить новый документ", "📜 Получить список документов"])
def handle_action(message):
    user_id = get_user_id_by_username(conn, message.from_user.username)
    if user_id:
        if message.text == "📤 Загрузить новый документ":
            bot.send_message(message.chat.id, "Отправьте файл, который вы хотите загрузить.")
            bot.register_next_step_handler(message, upload_document, user_id)
        elif message.text == "📜 Получить список документов":
            docs = get_all_docs(conn, user_id)  # Получаем все документы пользователя
            if docs:
                for doc in docs:
                    # Путь к файлу (например, файл хранится в папке uploads)
                    file_path = os.path.join(os.getcwd(), 'uploads', doc[1])

                    # Проверка, что файл существует перед отправкой
                    if os.path.exists(file_path):
                        created_at = doc[4]
                        formatted_date = created_at.strftime('%d %B %Y, %H:%M')

                        # Проверка, чтобы тег не был None
                        tag = doc[3] if doc[3] is not None else "Без тега"

                        # Отправляем информацию о документе пользователю
                        doc_info = (
                            f"🆔 *ID документа:* {doc[0]}\n"
                            f"🏷️ *Тег:* {escape_markdown(tag)}\n"
                            f"📅 *Создан:* {escape_markdown(formatted_date)}\n"
                        )
                        bot.send_message(message.chat.id, doc_info, parse_mode='Markdown')

                        # Отправляем сам файл
                        with open(file_path, 'rb') as file:
                            bot.send_document(message.chat.id, file)
                    else:
                        bot.send_message(message.chat.id, f"Файл '{doc[1]}' не найден.")
            else:
                bot.send_message(message.chat.id, "У вас пока нет загруженных документов.")
    else:
        bot.send_message(message.chat.id, "Сначала зарегистрируйтесь, используя команду /start.")


# Обработка загрузки документа
def upload_document(message, user_id):
    if message.content_type == 'document':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        file_dir = os.path.join(os.getcwd(), 'uploads')
        file_path = os.path.join(file_dir, message.document.file_name)

        os.makedirs(file_dir, exist_ok=True)

        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)  # Сохраняем файл как бинарные данные

        bot.send_message(message.chat.id,
                         "Файл загружен. Хотите добавить тег к этому файлу? Если да, отправьте тег. Если нет, отправьте 'нет'.")
        bot.register_next_step_handler(message, process_tag, file_path, downloaded_file, user_id)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте документ.")


# Обработка добавления тега
def process_tag(message, file_path, downloaded_file, user_id):
    if message.text.lower() == 'нет':
        tag = None
    else:
        tag = message.text

    title = os.path.basename(file_path)

    try:
        # Преобразование содержимого файла в бинарный формат для сохранения в базе данных
        body = downloaded_file
    except Exception as e:
        print(f"Ошибка при обработке файла: {e}")
        body = None

    if body:
        # Сохраняем бинарные данные в базу данных
        doc_id = insert_doc(conn, title, body, user_id, tag)
        bot.send_message(message.chat.id, f"Документ добавлен с ID: {doc_id}")
    else:
        bot.send_message(message.chat.id, "Ошибка: файл пустой.")


# Обработчик команды /search для поиска документов по тегу
@bot.message_handler(commands=['search'])
def search_by_tag(message):
    bot.send_message(message.chat.id, "Введите тег для поиска:")
    bot.register_next_step_handler(message, process_search_tag)


# Обработка ввода тега пользователем и вывод списка документов
def process_search_tag(message):
    tag = message.text  # Тег, который ввел пользователь
    user_id = get_user_id_by_username(conn, message.from_user.username)

    if user_id:
        docs = get_docs_by_tag(conn, user_id, tag)
        if docs:
            bot.send_message(message.chat.id, f"Документы с тегом '{tag}':")
            for doc in docs:
                # Путь к файлу (например, файл хранится в папке uploads)
                file_path = os.path.join(os.getcwd(), 'uploads', doc[1])

                # Проверяем, существует ли файл перед отправкой
                if os.path.exists(file_path):
                    created_at = doc[4]
                    formatted_date = created_at.strftime('%d %B %Y, %H:%M')

                    # Отправляем информацию о документе
                    doc_info = (
                        f"🆔 *ID документа:* {doc[0]}\n"
                        f"🏷️ *Тег:* {escape_markdown(doc[3])}\n"
                        f"📅 *Создан:* {escape_markdown(formatted_date)}\n"
                    )
                    bot.send_message(message.chat.id, doc_info, parse_mode='Markdown')

                    with open(file_path, 'rb') as file:
                        bot.send_document(message.chat.id, file)
                else:
                    bot.send_message(message.chat.id, f"Файл '{doc[1]}' не найден.")
        else:
            bot.send_message(message.chat.id, f"Документов с тегом '{tag}' не найдено.")
    else:
        bot.send_message(message.chat.id, "Вы не зарегистрированы. Пожалуйста, используйте команду /start.")


# Пример функции для получения документов по тегу из базы данных
def get_docs_by_tag(conn, user_id, tag):
    sql_query = ''' SELECT id, title, body, tag, created_at FROM docs WHERE user_id = %s AND tag = %s; '''
    cursor = conn.cursor()
    cursor.execute(sql_query, (user_id, tag))
    docs = cursor.fetchall()
    cursor.close()
    return docs


# Команда для удаления документа
@bot.message_handler(commands=['delete'])
def delete_document(message):
    bot.send_message(message.chat.id, "Введите ID документа для удаления:")
    bot.register_next_step_handler(message, process_delete_document)


# Обработка удаления документа
def process_delete_document(message):
    doc_id = message.text  # Пользователь вводит ID документа
    user_id = get_user_id_by_username(conn, message.from_user.username)

    if user_id:
        doc = get_doc_by_id(conn, user_id, doc_id)
        if doc:
            file_path = os.path.join(os.getcwd(), 'uploads', doc[1])

            # Удаляем файл с сервера, если он существует
            if os.path.exists(file_path):
                os.remove(file_path)
                bot.send_message(message.chat.id, f"Файл '{doc[1]}' был удален.")
            else:
                bot.send_message(message.chat.id, f"Файл '{doc[1]}' не найден на сервере.")

            # Удаляем запись из базы данных
            delete_doc_from_db(conn, doc_id)
            bot.send_message(message.chat.id, "Документ и тег удалены из базы данных.")
        else:
            bot.send_message(message.chat.id, "Документ с таким ID не найден.")
    else:
        bot.send_message(message.chat.id, "Вы не зарегистрированы. Пожалуйста, используйте команду /start.")


# Получение документа по его ID
def get_doc_by_id(conn, user_id, doc_id):
    sql_query = ''' SELECT id, title, body, tag, created_at FROM docs WHERE id = %s AND user_id = %s; '''
    cursor = conn.cursor()
    cursor.execute(sql_query, (doc_id, user_id))
    doc = cursor.fetchone()
    cursor.close()
    return doc


# Удаление записи из базы данных
def delete_doc_from_db(conn, doc_id):
    sql_query = ''' DELETE FROM docs WHERE id = %s; '''
    cursor = conn.cursor()
    cursor.execute(sql_query, (doc_id,))
    conn.commit()
    cursor.close()


# Запуск бота
bot.polling(none_stop=True, timeout=60)

# Закрытие соединения с базой данных после завершения работы
conn.close()