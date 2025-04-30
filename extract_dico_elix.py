import json
import requests
from bs4 import BeautifulSoup
import time
import logging
import os
from typing import Dict, List, Any, Optional
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from dataclasses import dataclass
from datetime import datetime

@dataclass
class GestureData:
    attributes: Dict[str, float]
    motion_data: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: str
    url: str

    def is_valid(self) -> bool:
        """Valider les données du geste."""
        if not all(isinstance(v, float) and 0 <= v <= 5 for v in self.attributes.values()):
            return False
        if not self.motion_data or not isinstance(self.motion_data, dict):
            return False
        return True

class DicoElixExtractor:
    def __init__(self, max_workers: int = 4, requests_per_second: int = 2, retry_attempts: int = 3):
        """Initialiser l'extracteur avec des paramètres de configuration.
        
        Args:
            max_workers: Nombre maximum de workers pour le traitement parallèle
            requests_per_second: Nombre maximum de requêtes par seconde
            retry_attempts: Nombre de tentatives de réessai en cas d'échec
        """
        # Configuration du logging avancé
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Configuration du logger principal
        self.logger = logging.getLogger('DicoElixExtractor')
        self.logger.setLevel(logging.DEBUG)
        
        # Handler pour le fichier de log
        fh = logging.FileHandler(
            os.path.join(log_dir, f'extraction_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            encoding='utf-8'
        )
        fh.setLevel(logging.DEBUG)
        
        # Handler pour la console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formateurs
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        
        fh.setFormatter(file_formatter)
        ch.setFormatter(console_formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        self.base_url = "https://dico.elix-lsf.fr"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(os.path.dirname(script_dir), 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.output_file = os.path.join(data_dir, 'gestures-fr-dico-elix.json')
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Configuration des requêtes HTTP avec retry amélioré
        retry_strategy = Retry(
            total=retry_attempts,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=['GET'],
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=max_workers)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Paramètres de configuration
        self.retry_attempts = retry_attempts
        self.current_retries = {}
        self.failed_urls = set()
        
        # Configuration du traitement parallèle
        self.max_workers = max_workers
        self.request_interval = 1.0 / requests_per_second
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    @lru_cache(maxsize=1000)
    def extract_gesture_data(self, url: str) -> Optional[GestureData]:
        """Extraire les données d'un geste spécifique avec validation et mise en cache.
        
        Args:
            url: L'URL du geste à extraire
            
        Returns:
            GestureData si l'extraction réussit, None sinon
        """
        try:
            logging.info(f"Extraction des données pour l'URL: {url}")
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire les attributs psycholinguistiques avec validation
            attributes = {}
            for attr in ["familiarite", "concretude", "iconicite", "complexite", "frequence"]:
                value = self._extract_rating(soup, attr)
                if value is not None:
                    attributes[attr] = value
                else:
                    logging.warning(f"Attribut {attr} non trouvé pour {url}")
                    return None
            
            # Extraire les données de mouvement
            motion_data = self._extract_motion_data(soup)
            if not motion_data:
                logging.warning(f"Données de mouvement non trouvées pour {url}")
                return None
            
            # Créer et valider l'objet GestureData
            gesture_data = GestureData(
                attributes=attributes,
                motion_data=motion_data,
                metadata={
                    "extraction_date": datetime.now().isoformat(),
                    "source_url": url,
                    "version": "1.0"
                },
                timestamp=datetime.now().isoformat(),
                url=url
            )
            
            if not gesture_data.is_valid():
                logging.error(f"Données invalides pour {url}")
                return None
                
            logging.info(f"Extraction réussie pour {url}")
            return gesture_data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Erreur réseau pour {url}: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Erreur lors de l'extraction des données pour {url}: {str(e)}")
            return None

    def _extract_rating(self, soup: BeautifulSoup, attribute: str) -> float:
        """Extraire la note d'un attribut spécifique."""
        try:
            # Recherche de l'élément contenant la note de l'attribut
            rating_element = soup.find('div', {'class': f'rating-{attribute}'}) or \
                            soup.find('span', {'data-rating': attribute})
            
            if rating_element:
                # Extraction de la valeur numérique
                rating_text = rating_element.get('data-value') or rating_element.text.strip()
                return float(rating_text)
            return 0.0
        except Exception as e:
            print(f"Erreur lors de l'extraction de {attribute}: {str(e)}")
            return 0.0

    def _extract_motion_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extraire les données de mouvement de la vidéo avec validation avancée."""
        try:
            video_container = soup.find('div', {'class': 'video-container'})
            if not video_container:
                self.logger.warning("Container vidéo non trouvé")
                return {"sequence": []}

            motion_data_str = video_container.get('data-motion')
            if not motion_data_str:
                self.logger.warning("Données de mouvement non trouvées")
                return {"sequence": []}

            try:
                motion_data = json.loads(motion_data_str)
                if not isinstance(motion_data, dict) or 'sequence' not in motion_data:
                    self.logger.warning("Format de données de mouvement invalide")
                    return {"sequence": []}

                # Validation et enrichissement des données de mouvement
                for item in motion_data['sequence']:
                    if 'type' not in item:
                        item['type'] = 'hand'
                    if 'position' not in item:
                        item['position'] = {"x": 0.5, "y": 0.5, "z": 0}
                    if 'rotation' not in item:
                        item['rotation'] = {"x": 0, "y": 0, "z": 0}
                    if 'fingers' not in item:
                        item['fingers'] = [
                            {"id": finger, "flex": 0}
                            for finger in ["thumb", "index", "middle", "ring", "pinky"]
                        ]
                    if 'duration' not in item:
                        item['duration'] = 500

                return motion_data

            except json.JSONDecodeError as e:
                self.logger.error(f"Erreur de décodage JSON: {str(e)}")
                return {"sequence": []}

        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction des données de mouvement: {str(e)}")
            return {"sequence": []}
        except Exception as e:
            print(f"Erreur lors de l'extraction des données de mouvement: {str(e)}")
            return None

    def process_dictionary(self):
        """Traiter l'ensemble du dictionnaire Elix."""
        try:
            # Initialize or load the JSON file
            if not os.path.exists(self.output_file):
                data = {"metadata": {"totalGestures": 0}, "gestures": {}}
                self._save_data(data)
            else:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            # Liste des URLs à traiter (à implémenter)
            urls = self._get_dictionary_urls()

            # Traiter chaque URL
            for url in urls:
                word = self._extract_word(url)
                gesture_data = self.extract_gesture_data(url)
                
                if gesture_data:
                    data['gestures'][word] = gesture_data
                    data['metadata']['totalGestures'] = len(data['gestures'])
                    
                    # Sauvegarder régulièrement
                    self._save_data(data)
                    
                    # Pause pour éviter de surcharger le serveur
                    time.sleep(1)

        except Exception as e:
            print(f"Erreur lors du traitement du dictionnaire: {str(e)}")

    def _get_dictionary_urls(self) -> List[str]:
        """Obtenir la liste des URLs à traiter."""
        urls = []
        try:
            # Parcourir les pages du dictionnaire
            page = 1
            while True:
                response = requests.get(
                    f"{self.base_url}/dictionnaire?page={page}",
                    headers=self.headers
                )
                if response.status_code != 200:
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                # Rechercher les liens vers les définitions
                word_links = soup.find_all('a', {'class': 'word-link'}) or \
                            soup.find_all('a', href=lambda x: x and '/dictionnaire/' in x)
                
                if not word_links:
                    break
                    
                for link in word_links:
                    url = link.get('href')
                    if url:
                        if not url.startswith('http'):
                            url = f"{self.base_url}{url}"
                        urls.append(url)
                
                page += 1
                # Pause pour éviter de surcharger le serveur
                time.sleep(1.5)
                
        except Exception as e:
            print(f"Erreur lors de la récupération des URLs: {str(e)}")
        
        return urls

    def _extract_word(self, url: str) -> str:
        """Extraire le mot/concept à partir de l'URL."""
        try:
            # Extraire le dernier segment de l'URL qui contient généralement le mot
            word = url.rstrip('/').split('/')[-1]
            
            # Décodage de l'URL pour gérer les caractères spéciaux
            from urllib.parse import unquote
            word = unquote(word)
            
            # Nettoyage du mot (suppression des caractères spéciaux)
            word = word.replace('-', ' ').strip()
            
            return word if word else "mot_inconnu"
            
        except Exception as e:
            print(f"Erreur lors de l'extraction du mot depuis l'URL: {str(e)}")
            return "mot_inconnu"

    def _save_data(self, data: Dict[str, Any]):
        """Sauvegarder les données dans le fichier JSON."""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    extractor = DicoElixExtractor()
    extractor.process_dictionary()

if __name__ == "__main__":
    main()