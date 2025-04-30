import React, { useRef } from 'react';
import { processVideo } from '../utils/videoProcessor';

const VideoInput = ({ onVideoUpload }) => {
  const fileInputRef = useRef(null);
  const supportedFormats = ['video/mp4', 'video/avi', 'video/quicktime'];

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    if (!supportedFormats.includes(file.type)) {
      alert('Format vidéo non supporté. Veuillez utiliser MP4, AVI ou MOV.');
      return;
    }

    try {
      await onVideoUpload(file);
    } catch (error) {
      console.error('Erreur lors du traitement de la vidéo:', error);
      alert('Une erreur est survenue lors du traitement de la vidéo.');
    }
  };

  const handleDrop = async (event) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file && supportedFormats.includes(file.type)) {
      await onVideoUpload(file);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  return (
    <div 
      className="video-input-container"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
      <div className="upload-area">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="video/*"
          style={{ display: 'none' }}
        />
        <button 
          onClick={() => fileInputRef.current.click()}
          className="upload-button"
        >
          Sélectionner une vidéo
        </button>
        <p>ou glissez-déposez votre fichier ici</p>
        <p className="formats-info">Formats acceptés: MP4, AVI, MOV</p>
      </div>
    </div>
  );
};

export default VideoInput;