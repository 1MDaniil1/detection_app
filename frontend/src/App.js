import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detectionResult, setDetectionResult] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError(null);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      // Убираем responseType: 'blob' - теперь ожидаем JSON
      const response = await axios.post('http://localhost:8000/detect', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      // response.data теперь JSON с полем image_url
      const imageUrl = response.data.image_url;
      setResultImage(imageUrl);
      setDetectionResult(response.data);
      setError(null);
      
    } catch (err) {
      console.error('Detection error:', err);
      setError('Error during detection: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Vein Detection App</h1>
      <form onSubmit={handleSubmit}>
        <input type="file" accept="image/*" onChange={handleFileChange} />
        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Upload and Detect'}
        </button>
      </form>
      
      {error && <p style={{ color: 'red' }}>{error}</p>}
      
      {detectionResult && (
        <div>
          <h3>Detection Results:</h3>
          <p>Veins found: {detectionResult.veins_found}</p>
          <p>Detection ID: {detectionResult.detection_id}</p>
        </div>
      )}
      
      {resultImage && (
        <div>
          <h3>Processed Image:</h3>
          <img 
            src={resultImage} 
            alt="Detected Veins" 
            style={{ 
              maxWidth: '100%', 
              maxHeight: '500px',
              border: '1px solid #ccc',
              borderRadius: '5px'
            }} 
          />
        </div>
      )}
    </div>
  );
}

export default App;