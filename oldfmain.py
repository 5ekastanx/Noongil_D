from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.graphics.texture import Texture  # Добавлен этот импорт
import requests
import base64
from PIL import Image as PILImage
from io import BytesIO
from threading import Thread
from gtts import gTTS
import os
import pygame
import tempfile
import time
from kivy.uix.scrollview import ScrollView
from kivy.utils import get_color_from_hex
from googletrans import Translator
from collections import defaultdict
import cv2
import numpy as np

# Настройки стиля
PRIMARY_COLOR = get_color_from_hex('#1976D2')
SECONDARY_COLOR = get_color_from_hex('#F5F5F5')
FONT_SIZE_TITLE = 24
FONT_SIZE_TEXT = 18

class StyledButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = PRIMARY_COLOR
        self.color = [1, 1, 1, 1]
        self.font_size = FONT_SIZE_TEXT
        self.bold = True
        self.size_hint_y = None
        self.height = 60
        with self.canvas.before:
            Color(*PRIMARY_COLOR)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[15,])
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class VoiceAssistant:
    def __init__(self):
        pygame.mixer.init()
        self.current_file = None

    def speak(self, text):
        try:
            if self.current_file and os.path.exists(self.current_file):
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                os.remove(self.current_file)
            
            self.current_file = os.path.join(tempfile.gettempdir(), f"voice_{time.time()}.mp3")
            tts = gTTS(text=text, lang='ru')
            tts.save(self.current_file)
            pygame.mixer.music.load(self.current_file)
            pygame.mixer.music.play()
        except Exception as e:
            print("Ошибка голосового движка:", e)

class ObjectDetectionApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.voice = VoiceAssistant()
        self.last_results = []
        Window.clearcolor = SECONDARY_COLOR
        self.capture = None

        self.correction_dict = {
            "челоек": "человек",
            "персон": "человек",
            "авто": "автомобиль",
            "машина": "автомобиль",
            "бутылк": "бутылка",
            "телефон": "смартфон",
            "экран": "монитор",
            "компьютер": "компьютер",
            "стол": "стол",
            "стул": "стул",
            "окно": "окно",
            "дверь": "дверь"
        }

    def build(self):
        self.layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        # Заголовок приложения
        header = BoxLayout(size_hint=(1, 0.1))
        title = Label(text='[b]Vision Assistant[/b]', 
                     font_size=FONT_SIZE_TITLE,
                     markup=True,
                     color=[0, 0, 0, 1],
                     halign='center')
        header.add_widget(title)
        self.layout.add_widget(header)
        
        # Камера с использованием OpenCV
        camera_container = BoxLayout(size_hint=(1, 0.6), 
                                 padding=5,
                                 orientation='vertical')
        
        self.camera_widget = Image()
        camera_container.add_widget(self.camera_widget)
        self.layout.add_widget(camera_container)
        
        # Запускаем обновление камеры
        self.capture = cv2.VideoCapture(0)
        Clock.schedule_interval(self.update_camera, 1.0/30.0)

        # Кнопка сканирования
        self.btn = StyledButton(text="Сканировать объекты")
        self.btn.bind(on_press=self.detect_objects)
        self.layout.add_widget(self.btn)

        # Панель результатов
        results_container = BoxLayout(orientation='vertical',
                                   size_hint=(1, 0.3),
                                   padding=10,
                                   spacing=5)
         
        results_title = Label(text='[b]Результаты:[/b]',
                            font_size=FONT_SIZE_TEXT,
                            color=[0, 0, 0, 1],
                            markup=True,
                            size_hint=(1, 0.1),
                            halign='center')
        results_container.add_widget(results_title)
        
        self.result_label = Label(text="Наведите камеру на объект...", 
                                font_size=FONT_SIZE_TEXT,
                                color=[0, 0, 0, 1],
                                size_hint=(1, 0.9),
                                halign='center',
                                valign='middle',
                                text_size=(Window.width - 20, None),
                                markup=True)
        
        scroll_view = ScrollView(size_hint=(1, 0.9))
        scroll_view.add_widget(self.result_label)
        results_container.add_widget(scroll_view)
        
        with results_container.canvas.before:
            Color(*PRIMARY_COLOR)
            self.results_border = RoundedRectangle(size=results_container.size,
                                                 pos=results_container.pos,
                                                 radius=[15,])
        self.layout.add_widget(results_container)
        results_container.bind(pos=self.update_border, size=self.update_border)

        return self.layout

    def update_border(self, instance, value):
        """Обновляет позицию и размер границы контейнера результатов"""
        self.results_border.pos = instance.pos
        self.results_border.size = instance.size

    def update_camera(self, dt):
        ret, frame = self.capture.read()
        if ret:
            # Конвертируем кадр в текстуру Kivy
            frame = cv2.flip(frame, 0)
            buf = frame.tostring()
            texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            self.camera_widget.texture = texture

    def detect_objects(self, instance):
        if self.capture:
            self.btn.text = "Сканирование..."
            self.btn.background_color = (0.8, 0.2, 0.2, 1)
            
            ret, frame = self.capture.read()
            if ret:
                # Конвертируем в PIL Image
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = PILImage.fromarray(frame)
                
                Thread(target=self.process_image, args=(pil_image,)).start()

    def correct_translation(self, text):
        """Исправляет распространённые ошибки перевода"""
        text_lower = text.lower()
        for wrong, correct in self.correction_dict.items():
            if wrong in text_lower:
                return correct
        return text
    
    def translate_object(self, obj):
        """Переводит объект на русский с исправлением ошибок"""
        try:
            # Сначала проверяем, нет ли перевода в нашем словаре
            obj_lower = obj.lower()
            if obj_lower in self.correction_dict:
                return self.correction_dict[obj_lower]
            
            # Если нет, используем автоматический перевод
            translator = Translator()
            translated = translator.translate(obj_lower, src='en', dest='ru').text
            
            # Исправляем возможные ошибки
            corrected = self.correct_translation(translated)
            
            # Приводим к правильному регистру
            return corrected.capitalize()
        except Exception as e:
            print(f"Translation error: {e}")
            return obj.capitalize()

    def process_image(self, image):
        try:
            # Оптимизация размера изображения
            new_width = 1024
            new_height = int(image.size[1] * (new_width / image.size[0]))
            optimized_image = image.resize((new_width, new_height))
            
            buffered = BytesIO()
            optimized_image.save(buffered, format="JPEG", quality=85)
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            response = requests.post(
                "https://vision.googleapis.com/v1/images:annotate?key=AIzaSyCFR3Vmz0-hpm26OMo6NeAtrdgmigpqueU",
                json={
                    "requests": [{
                        "image": {"content": img_base64},
                        "features": [
                            {"type": "OBJECT_LOCALIZATION", "maxResults": 10},
                            {"type": "LABEL_DETECTION", "maxResults": 10}
                        ]
                    }]
                },
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                object_counts = defaultdict(int)
                
                # Считаем количество каждого объекта
                for obj in data.get('responses', [{}])[0].get('localizedObjectAnnotations', []):
                    if obj['score'] > 0.7:
                        name = obj['name'].lower()
                        object_counts[name] += 1
                
                for label in data.get('responses', [{}])[0].get('labelAnnotations', []):
                    if label['score'] > 0.7:
                        name = label['description'].lower()
                        if name not in object_counts:
                            object_counts[name] = 1
                
                # Формируем список результатов с учетом количества
                results = []
                for obj, count in object_counts.items():
                    translated = self.translate_object(obj)
                    
                    # Формируем правильную форму слова
                    if count == 1:
                        results.append(translated)
                    elif count > 1:
                        if translated.endswith(('а', 'я')):
                            plural = translated[:-1] + 'и'
                        elif translated.endswith('ь'):
                            plural = translated[:-1] + 'и'
                        else:
                            plural = translated + 'ы'
                        results.append(f"{count} {plural}")
                
                self.last_results = results[:4]
            else:
                print("Ошибка API:", response.text)
                self.last_results = []

        except Exception as e:
            print("Ошибка:", e)
            self.last_results = []

        Clock.schedule_once(lambda dt: self.update_results())

    def update_results(self):
        if self.last_results:
            display_text = "[b]Обнаружены:[/b]\n" + "\n".join(f"- {obj}" for obj in self.last_results)
            self.result_label.text = display_text
            self.voice.speak("Обнаружены: " + ", ".join(self.last_results))
        else:
            self.result_label.text = "[b]Объекты не найдены[/b]"
            self.voice.speak("Объекты не обнаружены")
        
        self.btn.text = "Сканировать объекты"
        self.btn.background_color = PRIMARY_COLOR

    def on_stop(self):
        if self.capture:
            self.capture.release()

if __name__ == '__main__':
    ObjectDetectionApp().run()