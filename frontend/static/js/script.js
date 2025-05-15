// Элементы интерфейса
const cameraView = document.getElementById('camera-view');
const captureBtn = document.getElementById('capture-btn');
const resultsContent = document.getElementById('results-content');
const statusEl = document.getElementById('status');
const statusIndicator = statusEl.querySelector('.status-indicator');

// Состояние приложения
let stream = null;
let isProcessing = false;

// Инициализация камеры
async function initCamera() {
    try {
        updateStatus('Инициализация камеры...', 'processing');
        
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === 'videoinput');
        
        // Выбираем заднюю камеру на мобильных устройствах
        const constraints = {
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        };
        
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        cameraView.srcObject = stream;
        
        cameraView.onloadedmetadata = () => {
            cameraView.play();
            updateStatus('Готов к работе', 'ready');
        };
        
        cameraView.onerror = () => {
            updateStatus('Ошибка видео', 'error');
        };
        
    } catch (err) {
        console.error("Camera error:", err);
        updateStatus('Ошибка доступа к камере', 'error');
        resultsContent.innerHTML = createErrorState('Пожалуйста, разрешите доступ к камере');
    }
}

// Обновление статуса
function updateStatus(text, state) {
    statusEl.querySelector('span:last-child').textContent = text;
    statusIndicator.className = 'status-indicator ' + state;
}

// Создание состояния ошибки
function createErrorState(message) {
    return `
        <div class="empty-state">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#D32F2F" width="48px" height="48px">
                <path d="M0 0h24v24H0z" fill="none"/>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            <p>${message}</p>
        </div>
    `;
}

// Захват изображения
async function captureAndDetect() {
    if (isProcessing || !stream) return;
    
    isProcessing = true;
    captureBtn.disabled = true;
    updateStatus('Обработка изображения...', 'processing');
    captureBtn.classList.add('pulse');
    
    try {
        const canvas = document.createElement('canvas');
        canvas.width = cameraView.videoWidth;
        canvas.height = cameraView.videoHeight;
        const ctx = canvas.getContext('2d');
        
        // Зеркальное отражение для естественного вида
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(cameraView, 0, 0, canvas.width, canvas.height);
        
        const imageData = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
        
        const response = await fetch('/api/detect', {
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
        updateStatus('Ошибка обработки', 'error');
        resultsContent.innerHTML = createErrorState('Не удалось обработать изображение');
    } finally {
        isProcessing = false;
        captureBtn.disabled = false;
        captureBtn.classList.remove('pulse');
        updateStatus('Готов к работе', 'ready');
    }
}

// Отображение результатов
function displayResults(objects) {
    if (!objects || !Array.isArray(objects)) {
        resultsContent.innerHTML = createErrorState('Нет результатов');
        return;
    }
    
    if (objects.length === 0) {
        resultsContent.innerHTML = `
            <div class="empty-state">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#999" width="48px" height="48px">
                    <path d="M0 0h24v24H0z" fill="none"/>
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
                </svg>
                <p>Объекты не обнаружены</p>
            </div>
        `;
        return;
    }
    
    let html = objects.map(obj => `
        <div class="result-item">
            <span class="result-name">${obj.name}</span>
            ${obj.count > 1 ? `<span class="result-count">${obj.count}</span>` : ''}
        </div>
    `).join('');
    
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