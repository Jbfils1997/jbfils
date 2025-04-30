import React, { useState } from 'react';
import VideoInput from './components/VideoInput';
import TranscriptionPanel from './components/TranscriptionPanel';
import SignLanguageAvatar from './components/SignLanguageAvatar';

function App() {
  const [videoFile, setVideoFile] = useState(null);
  const [transcription, setTranscription] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleVideoUpload = async (file) => {
    try {
      setVideoFile(file);
      setIsProcessing(true);
      
      // Traitement de la vidéo et obtention de la transcription
      const transcriptionResult = await processVideo(file);
      setTranscription(transcriptionResult);

      // Conversion du texte en séquence de gestes pour l'avatar
      const gestureSequence = await textToGestureSequence(transcriptionResult);
      // TODO: Animer l'avatar avec la séquence de gestes
      
    } catch (error) {
      console.error('Erreur lors du traitement:', error);
      alert('Une erreur est survenue lors du traitement de la vidéo');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Traducteur en Langue des Signes</h1>
      </header>
      
      <main className="main-content">
        <VideoInput onVideoUpload={handleVideoUpload} />
        
        {isProcessing && (
          <div className="processing-message">
            <p>Traitement en cours...</p>
          </div>
        )}

        <div className="translation-container">
          <TranscriptionPanel text={transcription} />
          <SignLanguageAvatar />
        </div>
      </main>
    </div>
  );
}

export default App;