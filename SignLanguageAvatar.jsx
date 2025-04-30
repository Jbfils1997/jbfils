import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { initializeMediaPipe, processGestures } from '../utils/gestureProcessor';

const SignLanguageAvatar = ({ gestureSequence, language = 'fr' }) => {
  const [currentLanguage, setCurrentLanguage] = useState(language);
  const [animationQueue, setAnimationQueue] = useState([]);
  const [isAnimating, setIsAnimating] = useState(false);
  
  useEffect(() => {
    setCurrentLanguage(language);
  }, [language]);

  const processAnimationQueue = async () => {
    if (animationQueue.length === 0 || isAnimating) return;

    setIsAnimating(true);
    const currentGesture = animationQueue[0];

    try {
      await playGestureAnimation(currentGesture);
      setAnimationQueue(prev => prev.slice(1));
    } catch (error) {
      console.error('Erreur lors de l\'animation:', error);
    } finally {
      setIsAnimating(false);
    }
  };

  const playGestureAnimation = async (gesture) => {
    if (!mixerRef.current || !avatarRef.current) return;

    return new Promise((resolve) => {
      const action = mixerRef.current.clipAction(gesture);
      action.setLoop(THREE.LoopOnce);
      action.clampWhenFinished = true;
      
      action.reset()
        .setEffectiveTimeScale(1)
        .setEffectiveWeight(1)
        .fadeIn(0.5)
        .play();

      mixerRef.current.addEventListener('finished', () => {
        action.fadeOut(0.5);
        resolve();
      }, { once: true });
    });
  };

  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const avatarRef = useRef(null);
  const mixerRef = useRef(null);
  const clockRef = useRef(new THREE.Clock());
  const controlsRef = useRef(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [currentAnimation, setCurrentAnimation] = useState(null);

  useEffect(() => {
    const initScene = async () => {
      // Configuration de la scène
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xf0f0f0);
      sceneRef.current = scene;

      // Configuration de la caméra
      const camera = new THREE.PerspectiveCamera(
        45,
        containerRef.current.clientWidth / containerRef.current.clientHeight,
        0.1,
        1000
      );
      camera.position.set(0, 1.5, 3);
      camera.lookAt(0, 1, 0);
      cameraRef.current = camera;

      // Configuration du renderer
      const renderer = new THREE.WebGLRenderer({ 
        antialias: true,
        alpha: true
      });
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.setSize(
        containerRef.current.clientWidth,
        containerRef.current.clientHeight
      );
      renderer.shadowMap.enabled = true;
      containerRef.current.appendChild(renderer.domElement);
      rendererRef.current = renderer;

      // Configuration des contrôles
      const controls = new OrbitControls(camera, renderer.domElement);
      controls.target.set(0, 1, 0);
      controls.update();
      controlsRef.current = controls;

      // Éclairage amélioré
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
      scene.add(ambientLight);

      const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
      directionalLight.position.set(5, 5, 5);
      directionalLight.castShadow = true;
      scene.add(directionalLight);

      // Chargement du modèle 3D de l'avatar
      try {
        const loader = new GLTFLoader();
        const gltf = await loader.loadAsync('/models/avatar.glb');
        const avatar = gltf.scene;
        
        avatar.traverse((node) => {
          if (node.isMesh) {
            node.castShadow = true;
            node.receiveShadow = true;
          }
        });

        avatar.position.set(0, 0, 0);
        scene.add(avatar);
        avatarRef.current = avatar;

        // Configuration de l'animation
        const mixer = new THREE.AnimationMixer(avatar);
        mixerRef.current = mixer;

        setIsLoading(false);
      } catch (error) {
        console.error('Erreur lors du chargement du modèle:', error);
        setIsLoading(false);
      }
    };

    const animate = () => {
      requestAnimationFrame(animate);
      
      const delta = clockRef.current.getDelta();

      if (mixerRef.current) {
        mixerRef.current.update(delta);
      }

      if (controlsRef.current) {
        controlsRef.current.update();
      }

      rendererRef.current.render(sceneRef.current, cameraRef.current);
    };

    initScene();
    animate();

    // Gestion du redimensionnement
    const handleResize = () => {
      if (!containerRef.current || !cameraRef.current || !rendererRef.current) return;

      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;

      cameraRef.current.aspect = width / height;
      cameraRef.current.updateProjectionMatrix();

      rendererRef.current.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (containerRef.current && rendererRef.current) {
        containerRef.current.removeChild(rendererRef.current.domElement);
      }
    };
  }, []);

  // Gestion des animations basées sur la séquence de gestes
  useEffect(() => {
    if (gestureSequence && mixerRef.current && avatarRef.current) {
      setAnimationQueue(prevQueue => [...prevQueue, ...gestureSequence]);
    }
  }, [gestureSequence]);

  useEffect(() => {
    processAnimationQueue();
  }, [animationQueue, isAnimating]);

  useEffect(() => {
    const initializeAvatar = async () => {
      try {
        await initializeMediaPipe(currentLanguage);
      } catch (error) {
        console.error('Erreur lors de l\'initialisation de MediaPipe:', error);
      }
    };

    initializeAvatar();
  }, [currentLanguage]);

  return (
    <div className="avatar-container" ref={containerRef}>
      {isLoading && (
        <div className="loading-overlay">
          <p>Chargement de l'avatar...</p>
        </div>
      )}
    </div>
  );

};

export default SignLanguageAvatar;