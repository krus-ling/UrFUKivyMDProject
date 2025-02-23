"""
Тестовое приложение, копия main.py
Для добавления доп функциональности.
Классы для микрофона работают только на андроиде.

    !!!    Не работает на ПК    !!!

"""
import subprocess

from kivy.uix.scrollview import ScrollView

# buildozer.spec
"""

source.include_exts = py,png,jpg,kv,atlas,ttf,json

requirements = python3,
    kivy,
    kivymd,
    materialyoucolor,
    exceptiongroup,
    asyncgui,
    asynckivy,
    jnius,
    mysql-connector-python
    
presplash.filename = assets/img/icon2.png

icon.filename = assets/img/icon2.png
    
106 строка
android.permissions = RECORD_AUDIO, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, INTERNET

"""


import os
import re
import mysql.connector
import json

from kivy.uix.image import Image
from kivymd.uix.gridlayout import MDGridLayout
from datetime import datetime
from kivy.metrics import dp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import OneLineListItem
from kivymd.uix.screen import MDScreen
from kivy.storage.jsonstore import JsonStore
from jnius import autoclass
from kivy.clock import Clock
from android.permissions import request_permissions, Permission


with open('config.json') as config_file:
    config = json.load(config_file)


class LoginScreen(MDScreen):
    pass


class RegisterScreen(MDScreen):
    pass


class WelcomeScreen(MDScreen):
    pass


class SettingsScreen(MDScreen):
    pass


class AccountScreen(MDScreen):
    pass


class MyRecorder:
    def __init__(self):
        """Recorder object To access Android Hardware"""
        self.MediaRecorder = autoclass('android.media.MediaRecorder')
        self.AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
        self.OutputFormat = autoclass('android.media.MediaRecorder$OutputFormat')
        self.AudioEncoder = autoclass('android.media.MediaRecorder$AudioEncoder')

        # Создаем MediaRecorder
        self.mRecorder = self.MediaRecorder()
        self.mRecorder.setAudioSource(self.AudioSource.MIC)
        self.mRecorder.setOutputFormat(self.OutputFormat.DEFAULT)  # Изменяем на DEFAULT для записи в WAV
        self.mRecorder.setAudioEncoder(self.AudioEncoder.AAC)  # Используем кодек AAC (но это для m4a)

        # Для WAV можно использовать сторонние библиотеки или дополнительно конвертировать файл

        # Используем безопасный путь для сохранения файла
        Context = autoclass('android.content.Context')
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        storage_path = activity.getExternalFilesDir(None).getAbsolutePath()
        if not storage_path:
            raise Exception("Не удалось получить путь для сохранения файла.")
        os.makedirs(storage_path, exist_ok=True)

        # Указываем путь и формат файла
        self.output_file = os.path.join(storage_path, "MY.wav")  # Меняем на .wav
        self.mRecorder.setOutputFile(self.output_file)
        self.mRecorder.prepare()


    def get_output_file(self):
        """Возвращает путь к сохранённому аудиофайлу"""
        return self.output_file



class MyPlayer:
    def __init__(self):
        """Player object to play the audio file using Android hardware"""
        self.MediaPlayer = autoclass('android.media.MediaPlayer')

        # Создаём объект MediaPlayer
        self.mPlayer = self.MediaPlayer()

    def set_data_source(self, file_path):
        """Устанавливает источник данных для воспроизведения"""
        self.mPlayer.setDataSource(file_path)

    def prepare(self):
        """Готовит MediaPlayer к воспроизведению"""
        self.mPlayer.prepare()

    def start(self):
        """Запускает воспроизведение"""
        self.mPlayer.start()

    def stop(self):
        """Останавливает воспроизведение"""
        self.mPlayer.stop()

    def release(self):
        """Освобождает ресурсы MediaPlayer"""
        self.mPlayer.release()

    def set_on_completion_listener(self, listener):
        """Устанавливает слушатель завершения воспроизведения"""
        self.mPlayer.setOnCompletionListener(listener)


class MessageBubble(MDBoxLayout):
    def __init__(self, message, timestamp, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None  # Высота зависит от содержимого
        self.orientation = "vertical"  # Вертикальная ориентация для текста
        self.padding = [dp(20), dp(20), dp(20), dp(20)]  # Отступы внутри фона
        self.spacing = dp(15)  # Отступы между текстом и временной меткой

        # Добавляем фон
        self.md_bg_color = "#97ACD1"  # Светлый фон
        self.radius = [dp(30), dp(30), dp(30), dp(30)]  # Радиус углов


        # Добавляем текст
        label = MDLabel(
            text=message,
            size_hint_y=.8,
            pos_hint={"center_y": .5},
            markup=True,
            halign="left",
            valign="middle",
            text_size=(self.width, None),  # Учитываем отступы
            theme_text_color="Custom",
            text_color="#FFFFFF",
        )

        label.bind(
            texture_size=lambda instance, value: setattr(self, "height", instance.texture_size[1] + 100)
        )

        # Добавляем временную метку
        timestamp_label = MDLabel(
            text=timestamp,
            size_hint_y=None,
            height=dp(5),  # Фиксированная высота
            markup=True,
            halign="right",
            valign="middle",
            text_size=(self.width - 20, None),
            theme_text_color="Custom",
            text_color="#FFFFFF",
            font_style="Caption",
        )

        self.add_widget(label)
        self.add_widget(timestamp_label)


class App(MDApp):

    dialog = None
    password_visible = False  # Статус видимости пароля
    conn = None  # Атрибут для хранения соединения с БД
    store = None  # Хранилище для сохранения состояния входа
    messages_json = None  # Хранилище для сохранения сообщений

    # Флаг авторизации и данные пользователя
    is_logged_in = BooleanProperty(False)
    username = StringProperty("")
    email = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = None
        self.is_recording = None
        self.r = None
        self.user_id = None
        self.dialog = None
        self.selected_avatar = "assets/img/avatars/account.png"  # По умолчанию
        self.store = JsonStore("user_data.json")
        self.messages_json = JsonStore("messages.json")

    def build(self):

        self.theme_cls.theme_style = "Light"
        self.recording_time = 0  # Время записи в секундах

        # Запрос разрешений при запуске приложения
        request_permissions([Permission.RECORD_AUDIO,
                             Permission.WRITE_EXTERNAL_STORAGE,
                             Permission.READ_EXTERNAL_STORAGE])

        # Установить соединение с БД при запуске
        self.conn = mysql.connector.connect(
            host=config["host"],
            user = config["user"],
            password = config["password"],
            database = config["database"]
        )

        return Builder.load_file("test.kv")


    def on_start(self):

        self.is_recording = False  # Флаг для отслеживания состояния записи
        self.player = None  # Объект MediaPlayer

        # Проверить, сохранено ли состояние входа
        if self.store.exists("user"):
            user_data = self.store.get("user")
            self.username = user_data["username"]
            self.email = user_data["email"]
            self.is_logged_in = True

            # Переключаемся на экран Личного кабинета после загрузки интерфейса
            self.root.ids.screen_manager.current = "account"

            # Обновляем текст на экране Личного кабинета
            self.root.ids.screen_manager.get_screen('account').ids.username_label.text = self.username
            self.root.ids.screen_manager.get_screen('account').ids.useremail_label.text = self.email

        saved_messages = self.load_messages()

        if saved_messages["message"]:
            # Загрузка сохранённых сообщений
            for msg in reversed(saved_messages["message"]):
                self.send_message(msg["text"], timestamp=msg["timestamp"])

        # """Метод вызывается после завершения построения интерфейса"""
        # # Загружаем аватар из сохранённых данных
        # if self.store.exists("avatar"):
        #     avatar = self.store.get("avatar")["path"]
        #     self.selected_avatar = avatar
        #     if self.root:
        #         # Обновляем аватар только если root готов
        #         self.root.ids.avatar.source = avatar


    def login_user(self, identifier, password):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM users WHERE (username = %s OR email = %s) AND password = %s
        """, (identifier, identifier, password))
        user = cursor.fetchone()

        if user:
            self.is_logged_in = True
            self.user_id = user[0]
            self.username = user[1]  # Имя пользователя
            self.email = user[2]  # Почта пользователя

            # Сохраняем состояние входа
            self.store.put("user", id=self.user_id, username=self.username, email=self.email)

            # Обновляем текст на экране Личного кабинета
            self.root.ids.screen_manager.get_screen('account').ids.username_label.text = self.username  # Логин
            self.root.ids.screen_manager.get_screen('account').ids.useremail_label.text = self.email  # Почта

            self.show_dialog("Успех", f"Добро пожаловать, {user[1]}!")  # user[1] — имя пользователя
            self.root.ids.screen_manager.current = "account"  # Переход в личный кабинет

            self.conn.close()

        else:
            self.show_dialog("Ошибка", "Неверная почта или пароль.")


    def register_user(self, username, email, password, password_repeat):

        # Проверяем, что все поля заполнены
        if not username or not email or not password:
            self.show_dialog("Ошибка", "Заполните все поля.")
            return

        # Проверяем длину логина
        if len(username) > 20:
            self.show_dialog("Ошибка", "Логин должен быть не больше 20 символов.")
            return

        # Проверяем валидность почты
        if not self.is_valid_email(email):
            self.show_dialog("Ошибка", "Некорректная почта.")
            return

        # Если пароли не совпадают, выводим сообщение об ошибке
        if password != password_repeat:
            self.show_dialog("Ошибка", "Пароли не совпадают.")
            return

        cursor = self.conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
            self.conn.commit()
            self.show_dialog("Успех", "Регистрация успешна!")
            self.root.ids.screen_manager.current = "login"  # Переход ко входу

        except mysql.connector.IntegrityError:
            self.show_dialog("Ошибка", "Пользователь с таким именем или почтой уже существует.")


    def logout_user(self):

        """
        Метод для выхода из аккаунта.
        """

        if not self.conn or not self.conn.is_connected():
            self.conn = mysql.connector.connect(
                host=config["host"],
                user=config["user"],
                password=config["password"],
                database=config["database"]
            )

        self.is_logged_in = False
        self.username = ""
        self.email = ""

        # Удаляем сохранённое состояние
        if self.store.exists("user"):
            self.store.delete("user")

        # Очистить поля ввода на экране входа
        login_screen = self.root.ids.screen_manager.get_screen('login')
        login_screen.ids.identifier.text = ""  # Очищаем поле для имени пользователя или email
        login_screen.ids.password.text = ""  # Очищаем поле для пароля

        # Возвращаемся на экран входа
        self.root.ids.screen_manager.current = "login"


    def show_dialog(self, title, text):
        if not self.dialog:
            self.dialog = MDDialog(
                title=title,
                text=text,
                buttons=[MDFlatButton(text="OK", on_release=self.close_dialog)],
            )
        self.dialog.title = title
        self.dialog.text = text
        self.dialog.open()


    # Метод для переключения видимости пароля в регистрации
    def toggle_password_visibility_reg(self, password_field, repeat_password_field, button):
        self.password_visible = not self.password_visible
        password_field.password = not self.password_visible  # Меняем видимость пароля
        repeat_password_field.password = not self.password_visible  # Меняем видимость повторного пароля
        button.icon = "eye" if self.password_visible else "eye-off"  # Меняем иконку кнопки


    # Метод для переключения видимости пароля в авторизации
    def toggle_password_visibility_auth(self, textfield, button):
        self.password_visible = not self.password_visible
        textfield.password = not self.password_visible
        button.icon = "eye" if self.password_visible else "eye-off"


    @staticmethod
    def is_valid_email(email):
        """
        Проверяет валидность почтового адреса.
        Возвращает True, если адрес валидный, иначе False
        """
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return re.match(pattern, email) is not None


    def close_dialog(self, *args):
        self.dialog.dismiss()


    def on_switch_active(self, instance, value):
        """
        Меняет тему на темную или светлую в зависимости от состояния переключателя.
        """
        if value:  # Если переключатель активен, включаем темную тему
            self.theme_cls.theme_style = "Dark"
        else:  # Если переключатель не активен, включаем светлую тему
            self.theme_cls.theme_style = "Light"

    ############ МИКРОФОН ############


    def toggleRecording(self):
        """Toggle recording state"""
        if self.is_recording:
            self.stopRecording()
        else:
            self.startRecording_clock()

    def startRecording_clock(self):
        Clock.schedule_once(self.startRecording, 0)
        Clock.schedule_interval(self.updateRecordingTime, 1)  # Обновляем время каждую секунду


    def startRecording(self, dt):
        self.r = MyRecorder()
        self.r.mRecorder.start()
        self.is_recording = True
        button = self.root.ids.action_button
        button.icon = "assets/img/stop_record.png"
        self.root.ids.play_button.disabled = True  # Отключаем кнопку во время записи
        self.recording_time = 0  # Начинаем отсчет времени
        self.updateRecordingTime(dt)  # Обновляем текст времени сразу


    def updateRecordingTime(self, dt):
        """Обновляем время записи на экране"""
        if self.is_recording:
            self.recording_time += 1
            minutes, seconds = divmod(self.recording_time, 60)
            time_text = f"{minutes:02}:{seconds:02}"
            self.root.ids.recording_time.text = time_text


    def stopRecording(self):
        self.r.mRecorder.stop()
        self.r.mRecorder.release()

        self.is_recording = False
        button = self.root.ids.action_button
        button.icon = "assets/img/start_record.png"

        # Отключаем обновление времени
        Clock.unschedule(self.updateRecordingTime)

        # Активируем кнопку воспроизведения
        self.root.ids.play_button.disabled = False

        # Загрузим аудиофайл в базу данных
        self.upload_audio_to_db()

        # Переключаемся на вкладку "Чат" в нижней навигации
        self.root.ids.bottom_nav.switch_tab("screen 3")

        # Отправляем сообщение в чат
        self.send_message("""Транскрипция:\nТестовая запись раз два три""")
        self.send_message("С вашей речью все в порядке")

    def playRecording(self):
        if not self.player:
            self.player = MyPlayer()
            self.player.set_data_source(self.r.get_output_file())  # Устанавливаем источник данных (путь к файлу)
            self.player.prepare()  # Подготавливаем для воспроизведения
        self.player.start()  # Запускаем воспроизведение

        # Событие по завершению воспроизведения
        self.player.set_on_completion_listener(lambda mp: self.onPlaybackComplete())

    def onPlaybackComplete(self):
        """Сбрасываем состояние после завершения воспроизведения"""
        self.player.release()
        self.player = None

    def upload_audio_to_db(self):
        """Метод для загрузки аудиофайла в базу данных"""

        # Путь к файлу, который был записан на устройстве
        audio_file_path = self.r.get_output_file()

        # Прочитаем файл в бинарном режиме
        with open(audio_file_path, 'rb') as audio_file:
            audio_data = audio_file.read()

        user_data = self.store.get("user")
        user_id = user_data["id"]

        # Подключение к базе данных
        conn = mysql.connector.connect(
            host=config["host"],
            user=config["user"],
            password=config["password"],
            database=config["database"]
        )

        cursor = conn.cursor()

        # SQL-запрос для вставки записи в таблицу records
        insert_query = """
        INSERT INTO records (id_user, record) 
        VALUES (%s, %s)
        """

        try:
            # Выполнение запроса
            cursor.execute(insert_query, (user_id, audio_data))
            conn.commit()  # Сохраняем изменения в БД
        except mysql.connector.Error as err:
            print(f"Ошибка при загрузке файла в базу данных: {err}")
        finally:
            cursor.close()
            conn.close()

    def send_message(self, message="Тестовая запись раз два три.", timestamp=None):
        """Отправляет сообщение в чат"""
        chat_list = self.root.ids.chat_list

        # Если временная метка не передана, используем текущее время
        if not timestamp:
            timestamp = datetime.now().strftime("%H:%M")

        # Добавляем кастомный виджет для нового сообщения
        chat_list.add_widget(MessageBubble(message=message, timestamp=timestamp), index=0)

        # Добавляем отступ между сообщениями
        chat_list.add_widget(
            MDBoxLayout(size_hint_y=None, height=30)  # Пустое пространство
        )

        # Прокручиваем чат вниз
        chat_list.parent.scroll_to(chat_list.children[0])

        # Сохраняем все сообщения в хранилище
        self.save_messages()

    def load_messages(self):
        """Загружает сообщения из локального хранилища JsonStore."""
        if self.messages_json.exists("messages"):
            return self.messages_json.get("messages")
        return {"message": []}

    def save_messages(self):
        """Сохраняет сообщения в локальное хранилище JsonStore."""
        messages = {"message": []}
        for message in self.root.ids.chat_list.children:
            if isinstance(message, MessageBubble):
                messages["message"].append({
                    "text": message.children[1].text,
                    "timestamp": message.children[0].text,
                })

        # Сохраняем сообщения с ключом "messages"
        self.messages_json["messages"] = messages  # Используем этот способ записи


if __name__ == '__main__':
    App().run()
