// Элементы интерфейса
const cameraView = document.getElementById('camera-view');
const captureBtn = document.getElementById('capture-btn');
const resultsContent = document.getElementById('results-content');
const statusEl = document.getElementById('status');

// Состояние приложения
let stream = null;
let isProcessing = false;

// Инициализация камеры
async function initCamera() {
    try {
        statusEl.textContent = "Запуск камеры...";
        
        // Получаем список устройств
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === 'videoinput');
        console.log("Доступные камеры:", videoDevices);
        
        // Выбираем основную камеру (не виртуальную)
        const mainCamera = videoDevices.find(d => 
            !d.label.toLowerCase().includes('droidcam') && 
            !d.label.toLowerCase().includes('virtual'));
        
        const constraints = {
            video: {
                deviceId: mainCamera ? { exact: mainCamera.deviceId } : undefined,
                width: { ideal: 1280 },
                height: { ideal: 720 },
                facingMode: 'environment'
            },
            audio: false
        };
        
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        cameraView.srcObject = stream;
        
        // Ждем загрузки метаданных
        await new Promise((resolve) => {
            cameraView.onloadedmetadata = () => {
                cameraView.play();
                console.log(`Размер видео: ${cameraView.videoWidth}x${cameraView.videoHeight}`);
                resolve();
            };
        });
        
        statusEl.textContent = "Готово";
    } catch (err) {
        console.error("Camera error:", err);
        statusEl.textContent = "Ошибка камеры";
        resultsContent.textContent = "Пожалуйста, разрешите доступ к камере";
    }
}

// Захват изображения
async function captureAndDetect() {
    if (isProcessing || !stream) return;
    
    isProcessing = true;
    statusEl.textContent = "Обработка...";
    captureBtn.disabled = true;
    
    try {
        const canvas = document.createElement('canvas');
        canvas.width = cameraView.videoWidth;
        canvas.height = cameraView.videoHeight;
        const ctx = canvas.getContext('2d');
        
        // Рисуем изображение с учетом зеркального отражения
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(cameraView, 0, 0, canvas.width, canvas.height);
        
        // Конвертируем в base64
        const imageData = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
        
        // Отправка на сервер
        const response = await fetch('http://localhost:5000/api/detect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ image: imageData })
        });
        
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
        
        const results = await response.json();
        displayResults(results);
        
    } catch (err) {
        console.error("Detect error:", err);
        statusEl.textContent = "Ошибка обработки";
        resultsContent.textContent = "Попробуйте еще раз";
    } finally {
        isProcessing = false;
        statusEl.textContent = "Готово";
        captureBtn.disabled = false;
    }
}

// Отображение результатов
function displayResults(objects) {
    if (!objects || !Array.isArray(objects)) {
        resultsContent.innerHTML = "<div class='result-item'>Нет результатов</div>";
        return;
    }
    
    let html = objects.map(obj => 
        `<div class="result-item">${obj.count > 1 ? obj.count + ' ' : ''}${obj.name}</div>`
    ).join('');
    
    resultsContent.innerHTML = html;
    speakResults(objects);
}

// Озвучивание результатов
function speakResults(objects) {
    if ('speechSynthesis' in window) {
        const text = objects.map(obj => 
            obj.count > 1 ? `${obj.count} ${obj.name}` : obj.name
        ).join(', ');
        
        const utterance = new SpeechSynthesisUtterance("Обнаружены: " + text);
        utterance.lang = 'ru-RU';
        window.speechSynthesis.speak(utterance);
    }
}

// Инициализация при загрузке
window.addEventListener('DOMContentLoaded', () => {
    initCamera();
    captureBtn.addEventListener('click', captureAndDetect);
});

// Очистка при закрытии
window.addEventListener('beforeunload', () => {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
});