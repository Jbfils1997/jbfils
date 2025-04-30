import React, { useState, useEffect, useRef } from 'react';
import './TranscriptionPanel.css';

const TranscriptionPanel = ({ text, currentTime = 0, isProcessing = false }) => {
  const [visibleText, setVisibleText] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const contentRef = useRef(null);
  const wordsPerPage = 100;

  useEffect(() => {
    if (text) {
      setVisibleText(text);
      setCurrentPage(1);
    }
  }, [text]);

  const handleScroll = () => {
    if (contentRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = contentRef.current;
      if (scrollTop + clientHeight >= scrollHeight - 20) {
        loadMoreContent();
      }
    }
  };

  const loadMoreContent = () => {
    const words = text.split(' ');
    const startIndex = (currentPage - 1) * wordsPerPage;
    const endIndex = currentPage * wordsPerPage;
    
    if (endIndex < words.length) {
      setCurrentPage(prev => prev + 1);
      setVisibleText(words.slice(0, endIndex).join(' '));
    }
  };

  return (
    <div className="transcription-panel">
      <div className="transcription-header">
        <h2>Transcription</h2>
        {isProcessing && (
          <div className="processing-indicator">
            <div className="spinner"></div>
            <span>Traitement en cours...</span>
          </div>
        )}
      </div>

      <div 
        ref={contentRef}
        className="transcription-content"
        onScroll={handleScroll}
      >
        {visibleText ? (
          <p className="transcription-text">{visibleText}</p>
        ) : (
          <p className="placeholder-text">
            La transcription apparaîtra ici une fois la vidéo traitée
          </p>
        )}
      </div>
    </div>
  );
};

export default TranscriptionPanel;