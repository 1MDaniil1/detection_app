import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [detectionResult, setDetectionResult] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [currentStatus, setCurrentStatus] = useState('');
  const [selectedDetection, setSelectedDetection] = useState(null);
  
  const canvasRef = useRef(null);
  const imageRef = useRef(null);

  // Отрисовка bounding boxes на canvas
  useEffect(() => {
    if (resultImage && detectionResult && detectionResult.length > 0) {
      drawBoundingBoxes();
    }
  }, [resultImage, detectionResult]);

  const drawBoundingBoxes = () => {
    const canvas = canvasRef.current;
    const image = imageRef.current;
    
    if (!canvas || !image) return;

    const ctx = canvas.getContext('2d');
    
    // Ждем загрузки изображения
    image.onload = () => {
      // Устанавливаем размеры canvas как у изображения
      canvas.width = image.width;
      canvas.height = image.height;
      
      // Очищаем canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      // Рисуем bounding boxes
      detectionResult.forEach((detection, index) => {
        const { x, y, w, h, class: className, confidence } = detection;
        
        // Цвет в зависимости от класса и уверенности
        const color = getColorByConfidence(confidence);
        const isSelected = selectedDetection === index;
        
        // Рисуем bounding box
        ctx.strokeStyle = isSelected ? '#ff0000' : color;
        ctx.lineWidth = isSelected ? 4 : 2;
        ctx.strokeRect(x, y, w, h);
        
        // Рисуем фон для текста
        ctx.fillStyle = isSelected ? '#ff0000' : color;
        ctx.fillRect(x, y - 20, 120, 20);
        
        // Текст с классом и уверенностью
        ctx.fillStyle = 'white';
        ctx.font = '12px Arial';
        ctx.fillText(
          `${className} ${(confidence * 100).toFixed(1)}%`, 
          x + 5, 
          y - 5
        );
      });
    };
  };

  const getColorByConfidence = (confidence) => {
    if (confidence > 0.9) return '#00ff00'; // Зеленый - высокая уверенность
    if (confidence > 0.7) return '#ffff00'; // Желтый - средняя уверенность
    return '#ff0000'; // Красный - низкая уверенность
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    setFile(selectedFile);
    setError(null);
    setResultImage(null);
    setDetectionResult(null);
    setTaskId(null);
    setCurrentStatus('');
    setSelectedDetection(null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    
    if (!file) {
      setError('Пожалуйста, выберите файл');
      return;
    }

    setLoading(true);
    setError(null);
    setResultImage(null);
    setDetectionResult(null);
    setCurrentStatus('Отправка файла...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/detect', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { task_id } = response.data;
      setTaskId(task_id);
      setCurrentStatus('Обработка начата...');

      startPolling(task_id);

    } catch (error) {
      console.error('❌ Ошибка при отправке файла:', error);
      setLoading(false);
      setCurrentStatus('');
      setError(`Ошибка при отправке файла: ${error.response?.data?.detail || error.message}`);
    }
  };

  const startPolling = (taskId) => {
    let pollCount = 0;
    const maxPolls = 300;

    const poll = async () => {
      if (pollCount >= maxPolls) {
        setLoading(false);
        setError('Превышено время ожидания обработки');
        return;
      }

      pollCount++;

      try {
        const response = await axios.get(`http://localhost:8000/detect/status/${taskId}`);
        console.log('📊 Ответ сервера:', response.data);

        const { state, status, result } = response.data;

        setCurrentStatus(status || state || 'Обработка...');

        if (state === 'SUCCESS' || status === 'completed') {
          console.log('✅ Задача завершена успешно!');
          console.log('🎯 Результат:', result);
          
          setLoading(false);
          setCurrentStatus('Обработка завершена!');
          
          if (result) {
            setResultImage(result.processed_image_url || result.image_url);
            setDetectionResult(result.bounding_boxes || result.detections || []);
          }
          
        } else if (state === 'FAILURE' || status === 'failed') {
          setLoading(false);
          setCurrentStatus('Ошибка обработки');
          setError(result?.error || response.data?.error || 'Ошибка при обработке изображения');
          
        } else {
          setTimeout(poll, 2000);
        }

      } catch (error) {
        console.error('💥 Ошибка при опросе статуса:', error);
        if (pollCount < 10) {
          setTimeout(poll, 2000);
        } else {
          setLoading(false);
          setCurrentStatus('');
          setError(`Ошибка связи с сервером: ${error.message}`);
        }
      }
    };

    poll();
  };

  const handleReset = () => {
    setFile(null);
    setLoading(false);
    setError(null);
    setResultImage(null);
    setDetectionResult(null);
    setTaskId(null);
    setCurrentStatus('');
    setSelectedDetection(null);
    
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) fileInput.value = '';
  };

  const handleDetectionClick = (index) => {
    setSelectedDetection(index === selectedDetection ? null : index);
  };

  return (
    <div className="App">
      <div className="container">
        <header className="header">
          <h1 className="title">🔍 Детекция вен</h1>
          <p className="subtitle">Загрузите изображение для автоматического обнаружения вен</p>
        </header>

        {!loading && !resultImage && (
          <div className="upload-section">
            <form onSubmit={handleSubmit} className="upload-form">
              <div className="file-upload">
                <label htmlFor="file-input" className="file-label">
                  <div className="upload-icon">📁</div>
                  <div className="upload-text">
                    {file ? file.name : 'Выберите изображение'}
                  </div>
                  <div className="upload-hint">Нажмите для выбора файла</div>
                </label>
                <input
                  id="file-input"
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  disabled={loading}
                  className="file-input"
                />
              </div>
              <button 
                type="submit" 
                disabled={loading || !file} 
                className="submit-btn"
              >
                {loading ? '⏳ Обработка...' : '🚀 Начать детекцию'}
              </button>
            </form>
          </div>
        )}

        {error && (
          <div className="error-card">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <h3>Произошла ошибка</h3>
              <p>{error}</p>
            </div>
            <button onClick={handleReset} className="action-btn secondary">
              Попробовать снова
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-card">
            <div className="loading-spinner">⏳</div>
            <div className="loading-content">
              <h3>Обрабатываем изображение</h3>
              <p className="task-id">ID задачи: {taskId}</p>
              <p className="status">Статус: {currentStatus}</p>
              <div className="progress-text">
                Это может занять несколько минут...
              </div>
            </div>
          </div>
        )}

        {resultImage && (
          <div className="results-section">
            <div className="results-header">
              <h2>🎉 Результаты детекции</h2>
              <p>Найдено объектов: <strong>{detectionResult?.length || 0}</strong></p>
            </div>

            <div className="image-section">
              <div className="image-container">
                <h3>Обработанное изображение</h3>
                <div className="image-wrapper">
                  <img 
                    ref={imageRef}
                    src={resultImage} 
                    alt="Результат детекции" 
                    className="result-image"
                    onError={(e) => {
                      console.error('❌ Ошибка загрузки изображения:', resultImage);
                      e.target.style.border = '2px solid red';
                      e.target.alt = 'Ошибка загрузки изображения';
                    }}
                  />
                  <canvas 
                    ref={canvasRef}
                    className="bounding-boxes-canvas"
                  />
                </div>
              </div>

              {detectionResult && detectionResult.length > 0 && (
                <div className="detections-sidebar">
                  <h3>Найденные объекты</h3>
                  <div className="detections-list">
                    {detectionResult.map((detection, index) => (
                      <div 
                        key={index}
                        className={`detection-item ${selectedDetection === index ? 'selected' : ''}`}
                        onClick={() => handleDetectionClick(index)}
                      >
                        <div className="detection-header">
                          <span className="detection-number">#{index + 1}</span>
                          <span className="detection-class">{detection.class}</span>
                          <span 
                            className="confidence-badge"
                            style={{ 
                              backgroundColor: getColorByConfidence(detection.confidence) 
                            }}
                          >
                            {(detection.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="detection-details">
                          <div>Координаты: ({detection.x.toFixed(0)}, {detection.y.toFixed(0)})</div>
                          <div>Размер: {detection.w.toFixed(0)}×{detection.h.toFixed(0)}px</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="actions">
              <button onClick={handleReset} className="action-btn primary">
                📸 Анализировать другое изображение
              </button>
            </div>
          </div>
        )}

        {/* Отладочная информация */}
        {process.env.NODE_ENV === 'development' && (
          <div className="debug-info">
            <strong>Отладка:</strong> 
            {taskId && ` ID: ${taskId}`} 
            {currentStatus && ` | Статус: ${currentStatus}`}
            {resultImage && ` | Изображение: ✓`}
            {detectionResult && ` | Объекты: ${detectionResult.length}`}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;