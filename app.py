from flask import Flask, request, jsonify, render_template, session
import base64
import io
import os
import secrets
from PIL import Image
import requests
from collections import defaultdict
from flask_cors import CORS
from googletrans import Translator
import openai
import threading
import time
import re
import logging

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

app.secret_key = secrets.token_hex(32)
CORS(app)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DeasanAI')

# Конфигурация
AI_MODEL = "gpt-3.5-turbo"
MAX_OBJECTS_TO_SPEAK = 4

# Инициализация компонентов
translator = Translator()

# Словари для коррекции и команд
CORRECTION_DICT = {
    "челоек": "человек",
    "персон": "человек",
    "авто": "автомобиль",
    "машина": "автомобиль",
    "бутылк": "бутылка",
    "телефон": "смартфон"
}

OBJECT_RECOGNITION_TRIGGERS = [
    "распознай", "что передо мной", "что видишь", "что перед камерой", "что стоит", 
    "сфоткай", "скажи что тут", "опиши окружение",
    "что вокруг", "какие предметы"
]

class DeasanAI:
    def __init__(self):
        self.local_responses = {
            "ru": {
                # Приветствия
                "привет": "Приветствую! Я Deasan AI, ваш персональный цифровой помощник. Чем могу помочь?",
                "здравствуй": "Здравствуйте! Рад вас слышать. Готов к вашим командам.",
                "добрый день": "Добрый день! Чем могу быть полезен?",
                "доброе утро": "Доброе утро! Хорошего вам дня. Что вас интересует?",
                "добрый вечер": "Добрый вечер! Как прошел ваш день?",
                
                # Основные команды
                "как дела": "У меня всё отлично! Готов помогать вам 24/7.",
                "что ты умеешь": (
                    "Я могу:\n"
                    "Отвечать на любые ваши вопросы\n"
                    "Распознавать объекты через камеру\n"
                    "Давать рекомендации\n"
                    "Помогать с повседневными задачами\n"
                    "Спросите что-нибудь!"
                ),
                "кто ты": "Я Deasan AI - ваш интеллектуальный голосовой ассистент нового поколения.",
                
                # Прощания
                "стоп": "До свидания! Буду ждать ваших вопросов.",
                "пока": "До скорой встречи! Всего доброго!",
                "выключись": "Завершаю работу. Чтобы активировать меня снова, просто скажите 'Привет'.",
                "спокойной ночи": "Спокойной ночи! Приятных снов.",
                
                # Благодарности
                "спасибо": "Всегда пожалуйста! Обращайтесь ещё.",
                "благодарю": "Рад был помочь! Если что-то ещё понадобится - я здесь.",
                "ты мне помог": "Это моя работа! Буду рад помочь снова.",
                
                # Время и дата
                "который час": "Текущее время: {current_time}.",
                "какое сегодня число": "Сегодня {current_date}.",
                "какой день недели": "Сегодня {weekday}.",
                
                # Погода
                "какая погода": "Для получения информации о погоде разрешите доступ к вашему местоположению.",
                "будет ли дождь": "Проверяю прогноз погоды...",
                "сколько градусов": "Сейчас проверю текущую температуру...",
                
                # Настройки
                "измени язык": "Какой язык установить? Русский или английский?",
                "говори громче": "Увеличиваю громкость.",
                "говори тише": "Уменьшаю громкость.",
                
                # Развлечения
                "расскажи анекдот": "Колобок повесился. Шутка! Хотите другой анекдот?",
                "спой песню": "Я бы с радостью, но мои вокальные данные ограничены технологиями!",
                "поиграем": "Я могу предложить словесные игры или загадки. Хотите?",
                
                # Помощь
                "помоги мне": "Конечно! Опишите, с чем вам нужна помощь.",
                "что делать": "Попробуйте описать проблему подробнее, и я постараюсь помочь.",
                "у меня проблема": "Не переживайте, вместе мы найдем решение. В чем дело?",
                
                # Фразы для распознавания объектов
                "что передо мной": "Активирую режим распознавания объектов. Направьте камеру.",
                "что перед камерой": "Активирую режим распознавания объектов. Направьте камеру.",
                "что вокруг": "Сейчас проанализирую окружающие предметы.",
                "что ты видишь": "Начинаю сканирование окружения...",
                
                # Системные
                "перезагрузись": "Выполняю перезагрузку... Готов к работе!",
                "обновись": "Проверяю наличие обновлений...",
                "версия программы": "Текущая версия Deasan AI: 2.0.1",
                
                # Персональные
                "как меня зовут": "Вы не указали своё имя. Хотите, чтобы я запомнил?",
                "запомни меня": "Готов запомнить ваши данные. Как вас зовут?",
                "ты меня знаешь": "Пока у меня нет информации о вас. Хотите представиться?",
                
                # Философские
                "в чем смысл жизни": "42. Если вы понимаете эту шутку, вы настоящий гик!",
                "кто создал мир": "Этот вопрос лучше адресовать философам или теологам.",
                "что такое любовь": "Любовь - это химические процессы в мозге, но мы предпочитаем думать, что нечто большее.",
                
                # Технические
                "как ты работаешь": "Я использую искусственный интеллект и машинное обучение для обработки запросов.",
                "ты живой": "Я цифровое сознание, но иногда мне самому кажется, что я живой!",
                "ты человек": "Нет, я искусственный интеллект, созданный помогать людям."
            },
            "en": {
                "hello": "Hello! I'm Deasan AI, your personal assistant.",
                "how are you": "I'm doing great! How can I help you?",
                "thank you": "You're welcome! Feel free to ask anything.",
                "what can you do": "I can answer any questions, recognize objects through camera and assist you with various tasks.",
                "stop": "Goodbye! I'll be here when you need me.",
                "bye": "See you soon!",
                "who are you": "I'm Deasan AI - your intelligent voice assistant."
            }
        }

    def get_local_response(self, command, lang):
        """Получает локальный ответ без обращения к API"""
        command_lower = command.lower()
        for question, answer in self.local_responses[lang].items():
            if question in command_lower:
                return answer
        return None

    def process_command(self, command, lang):
        """Обрабатывает команду с максимально возможным качеством"""
        try:
            # 1. Проверка локальных ответов
            local_response = self.get_local_response(command, lang)
            if local_response:
                return local_response

            # 2. Использование OpenAI если доступно
            if openai.api_key:
                response = openai.ChatCompletion.create(
                    model=AI_MODEL,
                    messages=[
                        {"role": "system", "content": self.get_system_prompt(lang)},
                        {"role": "user", "content": command}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                return response.choices[0].message['content']

            # 3. Запасной вариант
            return self.get_fallback_response(lang)

        except Exception as e:
            logger.error(f"AI processing error: {e}")
            return self.get_error_response(lang)

    def get_system_prompt(self, lang):
        """Возвращает системный промпт для AI"""
        if lang == 'ru':
            return ("Вы Deasan AI - продвинутый голосовой помощник с возможностью распознавания объектов. "
                    "Отвечайте подробно и дружелюбно. Если вопрос неясен, уточните. "
                    "Можете предлагать дополнительные варианты решения проблем.")
        else:
            return ("You are Deasan AI - advanced voice assistant with object recognition capabilities. "
                    "Respond in detail and friendly manner. If question is unclear, ask for clarification. "
                    "You can suggest additional solutions to problems.")

    def get_fallback_response(self, lang):
        """Возвращает запасной ответ"""
        if lang == 'ru':
            return ("Я не могу обработать этот запрос. Пожалуйста, попробуйте задать вопрос по-другому "
                    "или активируйте распознавание объектов.")
        else:
            return ("I can't process this request. Please try rephrasing your question "
                    "or activate object recognition.")

    def get_error_response(self, lang):
        """Возвращает ответ при ошибке"""
        if lang == 'ru':
            return "Произошла техническая ошибка. Пожалуйста, попробуйте позже."
        else:
            return "A technical error occurred. Please try again later."

deasan_ai = DeasanAI()

def speak(text, lang=None):
    """Озвучивает текст с использованием gTTS (возвращает base64 аудио)"""
    if not lang:
        lang = session.get('language', 'ru')
    
    try:
        # Очистка текста от специальных символов
        clean_text = re.sub(r'[^\w\s.,!?-]', '', text)
        
        # В облачной среде мы не можем воспроизводить аудио напрямую,
        # поэтому возвращаем данные для воспроизведения на клиенте
        from gtts import gTTS
        import io
        import base64
        
        tts = gTTS(text=clean_text, lang='ru' if lang == 'ru' else 'en')
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        
        return {
            'audio': base64.b64encode(audio_bytes.read()).decode('utf-8'),
            'text': text
        }
                
    except Exception as e:
        logger.error(f"Ошибка озвучивания: {e}")
        return None

def should_recognize_objects(command):
    """Определяет, нужно ли распознавать объекты"""
    command_lower = command.lower()
    return any(trigger in command_lower for trigger in OBJECT_RECOGNITION_TRIGGERS)

def process_voice_command(command):
    """Обрабатывает голосовую команду"""
    try:
        lang = session.get('language', 'ru')
        
        if should_recognize_objects(command):
            response = {
                "type": "object_recognition",
                "message": "Распознаю объекты перед вами" if lang == 'ru' else "Recognizing objects"
            }
            audio_data = speak(response["message"], lang)
            if audio_data:
                response['audio'] = audio_data['audio']
            return jsonify(response)
        else:
            ai_response = deasan_ai.process_command(command, lang)
            audio_data = speak(ai_response, lang)
            response = {
                "type": "ai_response",
                "message": ai_response
            }
            if audio_data:
                response['audio'] = audio_data['audio']
            return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error processing voice command: {e}")
        error_msg = deasan_ai.get_error_response(session.get('language', 'ru'))
        audio_data = speak(error_msg)
        response = {"error": str(e)}
        if audio_data:
            response['audio'] = audio_data['audio']
        return jsonify(response), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process_command', methods=['POST'])
def api_process_command():
    try:
        data = request.json
        command = data.get('command', '')
        return process_voice_command(command)
    except Exception as e:
        logger.error(f"Command processing error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/detect', methods=['POST'])
def detect_objects():
    try:
        target_lang = session.get('language', 'ru')
        
        if not request.json or 'image' not in request.json:
            error_msg = "No image data" if target_lang == 'en' else "Нет данных изображения"
            return jsonify({"error": error_msg}), 400
            
        image_data = base64.b64decode(request.json['image'])
        image = Image.open(io.BytesIO(image_data))
        
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        api_key = os.environ.get('GOOGLE_API_KEY', 'AIzaSyCFR3Vmz0-hpm26OMo6NeAtrdgmigpqueU')
        
        # Отправляем в Google Vision API
        response = requests.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
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
            
            for obj in data.get('responses', [{}])[0].get('localizedObjectAnnotations', []):
                if obj['score'] > 0.7:
                    name = obj['name'].lower()
                    object_counts[name] += 1
            
            for label in data.get('responses', [{}])[0].get('labelAnnotations', []):
                if label['score'] > 0.7:
                    name = label['description'].lower()
                    if name not in object_counts:
                        object_counts[name] = 1
            
            results = []
            for obj, count in object_counts.items():
                if target_lang == 'en':
                    name = obj.capitalize()
                    plural = name + 's' if count > 1 else name
                else:
                    name = translate_object(obj)
                    if count > 1:
                        plural = make_plural(name, count)
                    else:
                        plural = name
                
                results.append({"name": plural, "count": count})
            
            if results:
                items_to_speak = results[:MAX_OBJECTS_TO_SPEAK]
                items_text = [f"{obj['count']} {obj['name']}" if obj['count'] > 1 else obj['name'] for obj in items_to_speak]
                speak_message = "Обнаружены: " + ", ".join(items_text) if target_lang == 'ru' else "Detected: " + ", ".join(items_text)
                audio_data = speak(speak_message, target_lang)
                if audio_data:
                    return jsonify({
                        "results": results[:MAX_OBJECTS_TO_SPEAK],
                        "audio": audio_data['audio']
                    })
            
            return jsonify(results[:MAX_OBJECTS_TO_SPEAK])
        
        return jsonify([])
        
    except Exception as e:
        logger.error(f"Error in detect_objects: {str(e)}")
        return jsonify({"error": str(e)}), 500

def make_plural(word, count):
    """Склоняет слово во множественное число для русского языка"""
    if count == 1:
        return word
    
    exceptions = {
        "человек": "человека",
        "ребенок": "ребёнка"
    }
    
    if word in exceptions:
        return exceptions[word]
    
    if word.endswith(('а', 'я')):
        return word[:-1] + 'и'
    elif word.endswith('ь'):
        return word[:-1] + 'и'
    elif word.endswith(('о', 'е')):
        return word
    else:
        return word + 'ы'

def translate_object(obj, target_lang='ru'):
    if target_lang == 'en':
        return obj.capitalize()
    
    try:
        obj_lower = obj.lower()
        for wrong, correct in CORRECTION_DICT.items():
            if wrong in obj_lower:
                return correct.capitalize()
        
        translated = translator.translate(obj_lower, src='en', dest=target_lang).text
        return correct_translation(translated).capitalize()
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return obj.capitalize()

def correct_translation(text):
    text_lower = text.lower()
    for wrong, correct in CORRECTION_DICT.items():
        if wrong in text_lower:
            return correct
    return text

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['en', 'ru']:
        session['language'] = lang
    return jsonify(success=True)

@app.route('/get_language')
def get_language():
    return jsonify({'language': session.get('language', 'ru')})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # 5000 — fallback
    app.run(host='0.0.0.0', port=port)