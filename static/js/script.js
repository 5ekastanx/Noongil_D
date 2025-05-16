const cameraView = document.getElementById('camera-view');
const captureBtn = document.getElementById('capture-btn');
const resultsContent = document.getElementById('results-content');
const statusEl = document.getElementById('status');
const statusIndicator = statusEl.querySelector('.status-indicator');
const voiceBtn = document.getElementById('voice-btn');
const aiResponseEl = document.getElementById('ai-response');

let stream = null;
let isProcessing = false;
let recognition = null;

async function initCamera() {
    try {
        updateStatus('Инициализация камеры...', 'processing');
        
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
            updateStatus('Deasan AI готов', 'ready');
        };
        
    } catch (err) {
        console.error("Camera error:", err);
        updateStatus('Ошибка камеры', 'error');
        showError('Разрешите доступ к камере');
    }
}

function updateStatus(text, state) {
    statusEl.querySelector('span:last-child').textContent = text;
    statusIndicator.className = 'status-indicator ' + state;
}

function showError(message) {
    resultsContent.innerHTML = `
        <div class="empty-state error">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#D32F2F">
                <path d="M0 0h24v24H0z" fill="none"/>
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            <p>${message}</p>
        </div>
    `;
}

function initVoiceRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showError('Браузер не поддерживает голосовой ввод');
        return null;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = document.documentElement.lang === 'ru' ? 'ru-RU' : 'en-US';
    
    recognition.onstart = () => {
        voiceBtn.classList.add('active');
        updateStatus('Слушаю...', 'processing');
        if (aiResponseEl) aiResponseEl.textContent = '';
    };
    
    recognition.onend = () => {
        voiceBtn.classList.remove('active');
        updateStatus('Готов к работе', 'ready');
    };
    
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        if (aiResponseEl) aiResponseEl.textContent = `Вы: ${transcript}`;
        processVoiceCommand(transcript);
    };
    
    recognition.onerror = (event) => {
        console.error('Recognition error:', event.error);
        showError('Ошибка распознавания');
        if (aiResponseEl) aiResponseEl.textContent = 'Ошибка распознавания голоса';
    };
    
    return recognition;
}

async function processVoiceCommand(command) {
    try {
        updateStatus('Обработка...', 'processing');
        
        const response = await fetch('/api/process_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ command: command })
        });
        
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
        
        const data = await response.json();
        
        if (data.type === 'object_recognition') {
            setTimeout(captureAndDetect, 1000);
        } else if (aiResponseEl) {
            aiResponseEl.innerHTML += `<br>Deasan AI: ${data.message}`;
        }
        
    } catch (err) {
        console.error("Command error:", err);
        showError('Ошибка обработки');
        if (aiResponseEl) aiResponseEl.textContent = 'Ошибка обработки команды';
    } finally {
        updateStatus('Готов к работе', 'ready');
    }
}

async function captureAndDetect() {
    if (isProcessing || !stream) return;
    
    isProcessing = true;
    captureBtn.disabled = true;
    updateStatus('Анализ изображения...', 'processing');
    
    try {
        const canvas = document.createElement('canvas');
        canvas.width = cameraView.videoWidth;
        canvas.height = cameraView.videoHeight;
        const ctx = canvas.getContext('2d');
        
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
        showError('Ошибка обработки');
    } finally {
        isProcessing = false;
        captureBtn.disabled = false;
        updateStatus('Готов к работе', 'ready');
    }
}

function displayResults(objects) {
    if (!objects || objects.error) {
        showError(objects?.error || 'Нет результатов');
        return;
    }
    
    if (objects.length === 0) {
        resultsContent.innerHTML = `
            <div class="empty-state">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#999">
                    <path d="M0 0h24v24H0z" fill="none"/>
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
                </svg>
                <p>Объекты не найдены</p>
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
}

function toggleVoiceInput() {
    if (!recognition) {
        recognition = initVoiceRecognition();
    }
    
    try {
        recognition.start();
    } catch (e) {
        console.error("Voice recognition error:", e);
    }
}

function setLanguage(lang) {
    fetch(`/set_language/${lang}`)
        .then(response => {
            if (response.ok) {
                location.reload();
            }
        })
        .catch(err => console.error("Language switch error:", err));
}

document.addEventListener('DOMContentLoaded', () => {
    initCamera();
    
    captureBtn.addEventListener('click', captureAndDetect);
    voiceBtn.addEventListener('click', toggleVoiceInput);
    
    document.querySelectorAll('.language-switcher button').forEach(btn => {
        btn.addEventListener('click', function() {
            const lang = this.dataset.lang;
            setLanguage(lang);
        });
    });
});

window.addEventListener('beforeunload', () => {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    if (recognition) {
        recognition.stop();
    }
});
