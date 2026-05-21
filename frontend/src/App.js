import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

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

  const getColorByConfidence = (confidence) => {
    if (confidence > 0.9) return '#00a651';
    if (confidence > 0.7) return '#d9a300';
    return '#d93025';
  };

  useEffect(() => {
    if (!resultImage || !detectionResult || detectionResult.length === 0) return;

    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image) return;

    const draw = () => {
      const ctx = canvas.getContext('2d');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      detectionResult.forEach((detection, index) => {
        const { x, y, w, h, class: className, confidence } = detection;
        const color = selectedDetection === index ? '#d93025' : getColorByConfidence(confidence);

        ctx.strokeStyle = color;
        ctx.lineWidth = selectedDetection === index ? 4 : 2;
        ctx.strokeRect(x, y, w, h);

        const label = `${className} ${(confidence * 100).toFixed(1)}%`;
        ctx.font = '12px Arial';
        const labelWidth = Math.max(ctx.measureText(label).width + 10, 80);
        ctx.fillStyle = color;
        ctx.fillRect(x, Math.max(y - 22, 0), labelWidth, 20);
        ctx.fillStyle = 'white';
        ctx.fillText(label, x + 5, Math.max(y - 7, 15));
      });
    };

    if (image.complete && image.naturalWidth > 0) {
      draw();
    } else {
      image.onload = draw;
    }
  }, [resultImage, detectionResult, selectedDetection]);

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
      setError('Выберите файл');
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
      const response = await axios.post(`${API_BASE_URL}/detect`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { task_id } = response.data;
      setTaskId(task_id);
      setCurrentStatus('Обработка начата...');
      startPolling(task_id);
    } catch (requestError) {
      setLoading(false);
      setCurrentStatus('');
      setError(`Ошибка при отправке файла: ${requestError.response?.data?.detail || requestError.message}`);
    }
  };

  const startPolling = (pollTaskId) => {
    let pollCount = 0;
    const maxPolls = 300;

    const poll = async () => {
      if (pollCount >= maxPolls) {
        setLoading(false);
        setError('Превышено время ожидания обработки');
        return;
      }

      pollCount += 1;

      try {
        const response = await axios.get(`${API_BASE_URL}/detect/status/${pollTaskId}`);
        const { state, status, result } = response.data;
        setCurrentStatus(status || state || 'Обработка...');

        if (state === 'SUCCESS' || status === 'completed') {
          setLoading(false);
          setCurrentStatus('Обработка завершена');

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
      } catch (pollError) {
        if (pollCount < 10) {
          setTimeout(poll, 2000);
        } else {
          setLoading(false);
          setCurrentStatus('');
          setError(`Ошибка связи с сервером: ${pollError.message}`);
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
          <h1 className="title">Детекция вен</h1>
          <p className="subtitle">Загрузите изображение для автоматического обнаружения вен</p>
        </header>

        {!loading && !resultImage && (
          <div className="upload-section">
            <form onSubmit={handleSubmit} className="upload-form">
              <div className="file-upload">
                <label htmlFor="file-input" className="file-label">
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
                {loading ? 'Обработка...' : 'Начать детекцию'}
              </button>
            </form>
          </div>
        )}

        {error && (
          <div className="error-card">
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
            <div className="loading-content">
              <h3>Обрабатываем изображение</h3>
              <p className="task-id">ID задачи: {taskId}</p>
              <p className="status">Статус: {currentStatus}</p>
              <div className="progress-text">
                Это может занять несколько минут
              </div>
            </div>
          </div>
        )}

        {resultImage && (
          <div className="results-section">
            <div className="results-header">
              <h2>Результаты детекции</h2>
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
                    onError={(event) => {
                      event.target.style.border = '2px solid #d93025';
                      event.target.alt = 'Ошибка загрузки изображения';
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
                              backgroundColor: getColorByConfidence(detection.confidence),
                            }}
                          >
                            {(detection.confidence * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="detection-details">
                          <div>Координаты: ({detection.x.toFixed(0)}, {detection.y.toFixed(0)})</div>
                          <div>Размер: {detection.w.toFixed(0)}x{detection.h.toFixed(0)} px</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="actions">
              <button onClick={handleReset} className="action-btn primary">
                Анализировать другое изображение
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
