import os
import re
import mysql.connector

from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivymd.app import MDApp
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.screen import MDScreen
from kivy.storage.jsonstore import JsonStore
from jnius import autoclass
from kivy.clock import Clock
from android.permissions import request_permissions, Permission
import json

with open('config.json') as config_file:
    config = json.load(config_file)

from kivy.core.window import Window
Window.size = (393, 852)


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
        '''Recorder object To access Android Hardware'''
        self.MediaRecorder = autoclass('android.media.MediaRecorder')
        self.AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
        self.OutputFormat = autoclass('android.media.MediaRecorder$OutputFormat')
        self.AudioEncoder = autoclass('android.media.MediaRecorder$AudioEncoder')

        # create out recorder
        self.mRecorder = self.MediaRecorder()
        self.mRecorder.setAudioSource(self.AudioSource.MIC)
        self.mRecorder.setOutputFormat(self.OutputFormat.THREE_GPP)

        # Используем безопасный путь для записи
        Context = autoclass('android.content.Context')
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        storage_path = activity.getExternalFilesDir(None).getAbsolutePath()
        if not storage_path:
            raise Exception("Не удалось получить путь для сохранения файла.")
        os.makedirs(storage_path, exist_ok=True)


        self.output_file = os.path.join(storage_path, "MYAUDIO.3gp")
        self.mRecorder.setOutputFile(self.output_file)
        self.mRecorder.setAudioEncoder(self.AudioEncoder.AMR_NB)
        self.mRecorder.prepare()

    def get_output_file(self):
        '''Возвращает путь к сохранённому аудиофайлу'''
        return self.output_file


class MyPlayer:
    def __init__(self):
        """Player object to play the audio file using Android hardware"""
        self.MediaPlayer = autoclass('android.media.MediaPlayer')

        # Создаём объект MediaPlayer
        self.mPlayer = self.MediaPlayer()

    def set_data_source(self, file_path):
        '''Устанавливает источник данных для воспроизведения'''
        self.mPlayer.setDataSource(file_path)

    def prepare(self):
        '''Готовит MediaPlayer к воспроизведению'''
        self.mPlayer.prepare()

    def start(self):
        '''Запускает воспроизведение'''
        self.mPlayer.start()

    def stop(self):
        '''Останавливает воспроизведение'''
        self.mPlayer.stop()

    def release(self):
        '''Освобождает ресурсы MediaPlayer'''
        self.mPlayer.release()

    def set_on_completion_listener(self, listener):
        '''Устанавливает слушатель завершения воспроизведения'''
        self.mPlayer.setOnCompletionListener(listener)


class App(MDApp):

    dialog = None
    password_visible = False  # Статус видимости пароля
    conn = None  # Атрибут для хранения соединения с БД
    store = None  # Хранилище для сохранения состояния входа

    # Флаг авторизации и данные пользователя
    is_logged_in = BooleanProperty(False)
    username = StringProperty("")
    email = StringProperty("")

    def build(self):

        self.theme_cls.theme_style = "Light"

        # Запрос разрешений при запуске приложения
        request_permissions([Permission.RECORD_AUDIO,
                             Permission.WRITE_EXTERNAL_STORAGE,
                             Permission.READ_EXTERNAL_STORAGE])

        # Инициализация локального хранилища
        self.store = JsonStore("user_data.json")

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

    def login_user(self, identifier, password):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM users WHERE (username = %s OR email = %s) AND password = %s
        """, (identifier, identifier, password))
        user = cursor.fetchone()

        if user:
            self.is_logged_in = True
            self.username = user[1]  # Имя пользователя
            self.email = user[2]  # Почта пользователя

            # Сохраняем состояние входа
            self.store.put("user", username=self.username, email=self.email)

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

    # def logout_user(self):
    #     """
    #     Метод для выхода из аккаунта.
    #     """
    #     self.is_logged_in = False
    #     self.username = ""
    #     self.email = ""
    #
    #     # Удаляем сохранённое состояние
    #     if self.store.exists("user"):
    #         self.store.delete("user")
    #
    #     # Возвращаемся на экран входа
    #     self.root.ids.screen_manager.current = "login"


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
        Проверяет валидность почтового адреса
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

    # МИКРОФОН

    def toggleRecording(self):
        '''Toggle recording state'''
        if self.is_recording:
            self.stopRecording()
        else:
            self.startRecording_clock()

    def startRecording_clock(self):
        Clock.schedule_once(self.startRecording)

    def startRecording(self, dt):
        self.r = MyRecorder()
        self.r.mRecorder.start()
        self.is_recording = True
        self.root.ids.action_button.text = 'Остановить запись'
        self.root.ids.play_button.disabled = True  # Отключаем кнопку во время записи
        self.root.ids.display_label.text = "Запись..."

    def stopRecording(self):
        self.r.mRecorder.stop()
        self.r.mRecorder.release()

        self.is_recording = False
        self.root.ids.action_button.text = 'Начать запись'
        self.root.ids.display_label.text = "Сообщение записано"

        # Активируем кнопку воспроизведения
        self.root.ids.play_button.disabled = False

    def playRecording(self):
        if not self.player:
            self.player = MyPlayer()
            self.player.set_data_source(self.r.get_output_file())  # Устанавливаем источник данных (путь к файлу)
            self.player.prepare()  # Подготавливаем для воспроизведения
        self.player.start()  # Запускаем воспроизведение

        # Событие по завершению воспроизведения
        self.player.set_on_completion_listener(lambda mp: self.onPlaybackComplete())

    def onPlaybackComplete(self):
        '''Сбрасываем состояние после завершения воспроизведения'''
        self.root.ids.display_label.text = "Запись прослушана!"
        self.player.release()
        self.player = None


if __name__ == '__main__':
    App().run()