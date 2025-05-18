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
import random
from datetime import datetime
from phrases import PHRASES, SCENARIOS

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

class ConversationManager:
    def __init__(self):
        self.conversation_history = defaultdict(list)
        self.current_topics = {}
        
    def add_to_history(self, user_id, role, text):
        """Добавляет реплику в историю диалога"""
        self.conversation_history[user_id].append({"role": role, "content": text})
        if len(self.conversation_history[user_id]) > 10:
            self.conversation_history[user_id].pop(0)
            
    def get_context(self, user_id):
        """Возвращает контекст диалога"""
        return self.conversation_history.get(user_id, [])
        
    def set_topic(self, user_id, topic):
        """Устанавливает текущую тему разговора"""
        self.current_topics[user_id] = topic
        
    def get_topic(self, user_id):
        """Получает текущую тему разговора"""
        return self.current_topics.get(user_id)

class DeasanAI:
    def __init__(self):
        self.local_responses = PHRASES
        self.context_scenarios = SCENARIOS
        
        self.current_context = None
        self.context_data = {}
        self.user_memory = defaultdict(dict)
    
    def get_local_response(self, command, lang):
        """Получает локальный ответ без обращения к API"""
        command_lower = command.lower()
        
        # 1. Проверка точных совпадений
        for question, answers in self.local_responses[lang].items():
            if question in command_lower:
                if isinstance(answers, list):
                    return random.choice(answers)
                return answers
                
        # 2. Проверка частичных совпадений
        for question, answers in self.local_responses[lang].items():
            if any(word in command_lower for word in question.split()):
                if isinstance(answers, list):
                    return random.choice(answers)
                return answers
                
        # 3. Контекстно-зависимые ответы
        if self.current_context:
            return self.handle_context(command, lang)
            
        return None
    
    def handle_context(self, command, lang):
        """Обработка контекстных сценариев"""
        command_lower = command.lower()
        scenario = self.context_scenarios[self.current_context]
        
        if self.current_context == "list_creation":
            if "закончи" in command_lower or "хватит" in command_lower:
                self.current_context = None
                count = len(self.context_data.get('items', []))
                return random.choice(scenario['complete']).format(count=count)
            else:
                self.context_data.setdefault('items', []).append(command)
                return random.choice(scenario['add_item']).format(item=command)
                
        elif self.current_context == "reminder":
            if not self.context_data.get('what'):
                self.context_data['what'] = command
                return random.choice(scenario['when'])
            else:
                self.context_data['when'] = command
                self.current_context = None
                return random.choice(scenario['confirm']).format(
                    text=self.context_data['what'],
                    time=self.context_data['when']
                )
        return None
    
    def process_personal_questions(self, command, lang, user_id):
        """Обработка персональных вопросов"""
        command_lower = command.lower()
        
        if "как меня зовут" in command_lower:
            name = self.user_memory[user_id].get('name')
            if name:
                return f"Вы говорили, что вас зовут {name}."
            return random.choice(self.local_responses[lang]["как меня зовут"])
            
        if "запомни мое имя" in command_lower or "меня зовут" in command_lower:
            name = re.search(r'(меня зовут|мое имя) ([\w\s]+)', command_lower)
            if name:
                name = name.group(2).strip().title()
                self.user_memory[user_id]['name'] = name
                return f"Очень приятно, {name}! Я запомнил ваше имя."
            return "Как именно вас зовут?"
            
        return None
    
    def process_command(self, command, lang, user_id='default'):
        """Обрабатывает команду с максимально возможным качеством"""
        try:
            # 1. Проверка персональных вопросов
            personal_response = self.process_personal_questions(command, lang, user_id)
            if personal_response:
                return personal_response

            # 2. Проверка локальных ответов
            local_response = self.get_local_response(command, lang)
            if local_response:
                # Заменяем динамические данные
                if "{current_time}" in local_response:
                    current_time = datetime.now().strftime("%H:%M")
                    local_response = local_response.format(current_time=current_time)
                elif "{current_date}" in local_response:
                    current_date = datetime.now().strftime("%d.%m.%Y")
                    local_response = local_response.format(current_date=current_date)
                elif "{weekday}" in local_response:
                    weekdays = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
                    weekday = weekdays[datetime.now().weekday()]
                    local_response = local_response.format(weekday=weekday)
                
                return local_response

            # 3. Использование OpenAI если доступно
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

            # 4. Запасной вариант
            return self.get_fallback_response(lang)

        except Exception as e:
            logger.error(f"AI processing error: {e}")
            return self.get_error_response(lang)

    def get_system_prompt(self, lang):
        """Возвращает системный промпт для AI"""
        if lang == 'ru':
            return ("Вы Deasan AI - продвинутый голосовой помощник с возможностью распознавания объектов. "
                    "Отвечайте подробно и дружелюбно. Если вопрос неясен, уточните. "
                    "Можете предлагать дополнительные варианты решения проблем. "
                    "Используйте информацию о пользователе если она доступна.")
        else:
            return ("You are Deasan AI - advanced voice assistant with object recognition capabilities. "
                    "Respond in detail and friendly manner. If question is unclear, ask for clarification. "
                    "You can suggest additional solutions to problems. "
                    "Use user information if available.")

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
conversation_manager = ConversationManager()

def speak(text, lang=None):
    """Озвучивает текст с использованием gTTS (возвращает base64 аудио)"""
    if not lang:
        lang = session.get('language', 'ru')
    
    try:
        # Очистка текста от специальных символов
        clean_text = re.sub(r'[^\w\s.,!?-]', '', text)
        
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

def process_voice_command(command, user_id='default'):
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
            return response
        else:
            ai_response = deasan_ai.process_command(command, lang, user_id)
            audio_data = speak(ai_response, lang)
            response = {
                "type": "ai_response",
                "message": ai_response
            }
            if audio_data:
                response['audio'] = audio_data['audio']
            return response
    
    except Exception as e:
        logger.error(f"Error processing voice command: {e}")
        error_msg = deasan_ai.get_error_response(session.get('language', 'ru'))
        audio_data = speak(error_msg)
        response = {"error": str(e)}
        if audio_data:
            response['audio'] = audio_data['audio']
        return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/toggle_voice_input', methods=['POST'])
def toggle_voice_input():
    """Включение/выключение голосового ввода"""
    data = request.json
    session['voice_input_enabled'] = data.get('enabled', False)
    return jsonify({'success': True, 'enabled': session['voice_input_enabled']})

@app.route('/api/process_command', methods=['POST'])
def api_process_command():
    try:
        if request.json.get('is_voice') and not session.get('voice_input_enabled', True):
            return jsonify({
                "error": "Голосовой ввод отключен",
                "message": "Пожалуйста, используйте текстовый ввод"
            }), 403
            
        data = request.json
        command = data.get('command', '')
        user_id = data.get('user_id', 'default')
        
        # Добавляем реплику пользователя в историю
        conversation_manager.add_to_history(user_id, "user", command)
        
        # Обработка команды
        response = process_voice_command(command)
        response['assistant_speaking'] = True
        
        # Обновляем историю диалога
        if 'message' in response:
            conversation_manager.add_to_history(user_id, "assistant", response['message'])
        
        return jsonify(response)
        
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

        api_key = os.environ.get('GOOGLE_API_KEY')
        
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)