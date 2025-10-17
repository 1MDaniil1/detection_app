import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [error, setError] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/detect', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',  // For image response
      });
      const imageUrl = URL.createObjectURL(response.data);
      setResultImage(imageUrl);
      setError(null);
    } catch (err) {
      setError('Error during detection');
    }
  };

  return (
    <div>
      <h1>Object Detection App</h1>
      <form onSubmit={handleSubmit}>
        <input type="file" accept="image/*" onChange={handleFileChange} />
        <button type="submit">Upload and Detect</button>
      </form>
      {error && <p>{error}</p>}
      {resultImage && <img src={resultImage} alt="Detected Objects" style={{ maxWidth: '100%' }} />}
    </div>
  );
}

export default App;