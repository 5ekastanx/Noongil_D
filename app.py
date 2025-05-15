from flask import Flask, request, jsonify, render_template
import base64
import io
import os
from PIL import Image
import requests
from collections import defaultdict
from flask_cors import CORS
from googletrans import Translator

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

CORS(app, resources={
    r"/api/*": {
        "origins": ["https://*.railway.app"],  # Разрешите домены Railway
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Словарь для коррекции перевода
CORRECTION_DICT = {
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

# Инициализация переводчика
translator = Translator()

def correct_translation(text):
    """Исправляет ошибки перевода"""
    text_lower = text.lower()
    for wrong, correct in CORRECTION_DICT.items():
        if wrong in text_lower:
            return correct
    return text

@app.route('/')
def index():
    return render_template('index.html')

def translate_object(obj):
    """Переводит объект на русский с исправлением ошибок"""
    try:
        # Сначала проверяем, нет ли перевода в нашем словаре
        obj_lower = obj.lower()
        for wrong, correct in CORRECTION_DICT.items():
            if wrong in obj_lower:
                return correct
        
        # Если нет, используем автоматический перевод
        translated = translator.translate(obj_lower, src='en', dest='ru').text
        
        # Исправляем возможные ошибки
        corrected = correct_translation(translated)
        
        # Приводим к правильному регистру
        return corrected.capitalize()
    except Exception as e:
        print(f"Translation error: {e}")
        return obj.capitalize()

@app.route('/api/detect', methods=['POST'])
def detect_objects():
    try:
        # Проверка данных
        if not request.json or 'image' not in request.json:
            return jsonify({"error": "No image data"}), 400
            
        # Декодирование изображения
        try:
            image_data = base64.b64decode(request.json['image'])
            image = Image.open(io.BytesIO(image_data))
        except Exception as e:
            return jsonify({"error": f"Invalid image data: {str(e)}"}), 400
            
        # Проверка размера
        if image.size[0] < 100 or image.size[1] < 100:
            return jsonify({"error": "Image too small"}), 400
            
        # Конвертация в RGB если нужно
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Оптимизация размера
        max_size = 1024
        if image.size[0] > max_size or image.size[1] > max_size:
            image.thumbnail((max_size, max_size))
            
        # Сохранение для отладки
        os.makedirs('debug_images', exist_ok=True)
        debug_path = os.path.join('debug_images', 'last_debug.jpg')
        image.save(debug_path, quality=85)
        print(f"Debug image saved to {debug_path}")

        # Конвертируем в base64 для Google Vision API
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # Здесь должен быть ваш реальный API ключ
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
            
            # Обработка результатов
            for obj in data.get('responses', [{}])[0].get('localizedObjectAnnotations', []):
                if obj['score'] > 0.7:
                    name = obj['name'].lower()
                    object_counts[name] += 1
            
            for label in data.get('responses', [{}])[0].get('labelAnnotations', []):
                if label['score'] > 0.7:
                    name = label['description'].lower()
                    if name not in object_counts:
                        object_counts[name] = 1
            
            # Форматируем результаты
            results = []
            for obj, count in object_counts.items():
                translated = translate_object(obj)
                
                if count == 1:
                    results.append({"name": translated, "count": 1})
                else:
                    if translated.endswith(('а', 'я')):
                        plural = translated[:-1] + 'и'
                    elif translated.endswith('ь'):
                        plural = translated[:-1] + 'и'
                    else:
                        plural = translated + 'ы'
                    results.append({"name": plural, "count": count})
            
            return jsonify(results[:4])
        
        # Если API не доступен, возвращаем тестовые данные
        test_results = [
            {"name": "человек", "count": 1},
            {"name": "стол", "count": 2}
        ]
        return jsonify(test_results)
        
    except Exception as e:
        print(f"Error in detect_objects: {str(e)}")
        return jsonify([{"name": "ошибка", "count": 1}])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)