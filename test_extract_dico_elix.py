import unittest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
from extract_dico_elix import DicoElixExtractor, GestureData
import json
import os
import requests
from datetime import datetime

class TestDicoElixExtractor(unittest.TestCase):
    def setUp(self):
        """Initialisation des tests avec un mock du système de fichiers."""
        self.extractor = DicoElixExtractor(max_workers=1, requests_per_second=1)
        self.sample_html = """
        <html>
            <div class="rating-familiarite" data-value="4.5"></div>
            <div class="rating-concretude" data-value="3.8"></div>
            <div class="rating-iconicite" data-value="3.2"></div>
            <div class="rating-complexite" data-value="2.5"></div>
            <div class="rating-frequence" data-value="4.0"></div>
            <div class="video-container" data-motion="{\"sequence\": [{\"type\": \"hand\"}]}"></div>
        </html>
        """
        self.soup = BeautifulSoup(self.sample_html, 'html.parser')

    def test_extract_rating(self):
        """Test de l'extraction des notes psycholinguistiques."""
        self.assertEqual(self.extractor._extract_rating(self.soup, 'familiarite'), 4.5)
        self.assertEqual(self.extractor._extract_rating(self.soup, 'concretude'), 3.8)
        self.assertEqual(self.extractor._extract_rating(self.soup, 'iconicite'), 3.2)
        self.assertEqual(self.extractor._extract_rating(self.soup, 'complexite'), 2.5)
        self.assertEqual(self.extractor._extract_rating(self.soup, 'frequence'), 4.0)

        # Test avec une valeur manquante
        soup_invalid = BeautifulSoup('<html></html>', 'html.parser')
        self.assertEqual(self.extractor._extract_rating(soup_invalid, 'familiarite'), 0.0)

        # Test avec une valeur invalide (non numérique)
        soup_invalid_value = BeautifulSoup('<div class="rating-familiarite" data-value="invalid"></div>', 'html.parser')
        self.assertEqual(self.extractor._extract_rating(soup_invalid_value, 'familiarite'), 0.0)

        # Test avec un attribut manquant
        soup_missing_attr = BeautifulSoup('<div class="rating-familiarite"></div>', 'html.parser')
        self.assertEqual(self.extractor._extract_rating(soup_missing_attr, 'familiarite'), 0.0)

    def test_extract_motion_data(self):
        """Test de l'extraction des données de mouvement."""
        motion_data = self.extractor._extract_motion_data(self.soup)
        self.assertIsNotNone(motion_data)
        self.assertIn('sequence', motion_data)
        self.assertTrue(isinstance(motion_data['sequence'], list))
        self.assertEqual(len(motion_data['sequence']), 1)
        self.assertEqual(motion_data['sequence'][0]['type'], 'hand')

        # Test avec des données de mouvement invalides
        soup_invalid = BeautifulSoup('<html></html>', 'html.parser')
        motion_data_invalid = self.extractor._extract_motion_data(soup_invalid)
        self.assertIsNotNone(motion_data_invalid)
        self.assertIn('sequence', motion_data_invalid)

        # Test avec JSON invalide
        soup_invalid_json = BeautifulSoup('<div class="video-container" data-motion="{invalid_json}"></div>', 'html.parser')
        motion_data_invalid_json = self.extractor._extract_motion_data(soup_invalid_json)
        self.assertIsNotNone(motion_data_invalid_json)
        self.assertIn('sequence', motion_data_invalid_json)
        self.assertEqual(len(motion_data_invalid_json['sequence']), 0)

        # Test avec une séquence vide
        soup_empty_sequence = BeautifulSoup('<div class="video-container" data-motion="{\"sequence\": []}"></div>', 'html.parser')
        motion_data_empty = self.extractor._extract_motion_data(soup_empty_sequence)
        self.assertIsNotNone(motion_data_empty)
        self.assertEqual(len(motion_data_empty['sequence']), 0)

    @patch('requests.Session.get')
    def test_extract_gesture_data(self, mock_get):
        """Test de l'extraction complète des données d'un geste."""
        mock_get.return_value.text = self.sample_html
        mock_get.return_value.status_code = 200

        gesture_data = self.extractor.extract_gesture_data('https://dico.elix-lsf.fr/dictionnaire/test')
        
        self.assertIsNotNone(gesture_data)
        self.assertTrue(isinstance(gesture_data, GestureData))
        self.assertEqual(gesture_data.attributes['familiarite'], 4.5)
        self.assertEqual(gesture_data.attributes['complexite'], 2.5)
        self.assertTrue(isinstance(gesture_data.timestamp, str))

        # Test avec une erreur réseau
        mock_get.side_effect = requests.exceptions.RequestException()
        gesture_data_error = self.extractor.extract_gesture_data('https://dico.elix-lsf.fr/dictionnaire/error')
        self.assertIsNone(gesture_data_error)

        # Test avec un code de statut HTTP invalide
        mock_get.side_effect = None
        mock_get.return_value.status_code = 404
        gesture_data_404 = self.extractor.extract_gesture_data('https://dico.elix-lsf.fr/dictionnaire/not-found')
        self.assertIsNone(gesture_data_404)

        # Test avec un timeout
        mock_get.side_effect = requests.exceptions.Timeout()
        gesture_data_timeout = self.extractor.extract_gesture_data('https://dico.elix-lsf.fr/dictionnaire/timeout')
        self.assertIsNone(gesture_data_timeout)

        # Test avec une réponse HTML invalide
        mock_get.side_effect = None
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html>Invalid HTML</html>'
        gesture_data_invalid = self.extractor.extract_gesture_data('https://dico.elix-lsf.fr/dictionnaire/invalid')
        self.assertIsNone(gesture_data_invalid)

    def test_extract_word(self):
        """Test de l'extraction du mot depuis l'URL."""
        test_urls = [
            ('https://dico.elix-lsf.fr/dictionnaire/bonjour', 'bonjour'),
            ('https://dico.elix-lsf.fr/dictionnaire/au-revoir', 'au revoir'),
            ('https://dico.elix-lsf.fr/dictionnaire/merci', 'merci'),
            ('https://dico.elix-lsf.fr/dictionnaire/être-content', 'être content'),
            ('https://dico.elix-lsf.fr/dictionnaire/', 'mot_inconnu')
        ]
        
        for url, expected in test_urls:
            self.assertEqual(self.extractor._extract_word(url), expected)

    def test_gesture_data_validation(self):
        """Test de la validation des données du geste."""
        valid_data = GestureData(
            attributes={'familiarite': 4.5, 'concretude': 3.8, 'iconicite': 3.2, 'complexite': 2.5, 'frequence': 4.0},
            motion_data={'sequence': [{'type': 'hand'}]},
            metadata={'extraction_date': datetime.now().isoformat()},
            timestamp=datetime.now().isoformat(),
            url='https://dico.elix-lsf.fr/dictionnaire/test'
        )
        self.assertTrue(valid_data.is_valid())

        # Test avec des attributs invalides
        invalid_data = GestureData(
            attributes={'familiarite': 6.0, 'concretude': -1.0},
            motion_data={},
            metadata={},
            timestamp=datetime.now().isoformat(),
            url='https://test.com'
        )
        self.assertFalse(invalid_data.is_valid())

        # Test avec des données de mouvement manquantes
        invalid_motion_data = GestureData(
            attributes={'familiarite': 4.5},
            motion_data=None,
            metadata={},
            timestamp=datetime.now().isoformat(),
            url='https://test.com'
        )
        self.assertFalse(invalid_motion_data.is_valid())

        # Test avec des métadonnées invalides
        invalid_metadata = GestureData(
            attributes={'familiarite': 4.5},
            motion_data={'sequence': [{'type': 'hand'}]},
            metadata={'extraction_date': 'invalid_date'},
            timestamp=datetime.now().isoformat(),
            url='https://test.com'
        )
        self.assertFalse(invalid_metadata.is_valid())

        # Test avec un timestamp invalide
        invalid_timestamp = GestureData(
            attributes={'familiarite': 4.5},
            motion_data={'sequence': [{'type': 'hand'}]},
            metadata={'extraction_date': datetime.now().isoformat()},
            timestamp='invalid_timestamp',
            url='https://test.com'
        )
        self.assertFalse(invalid_timestamp.is_valid())

    @patch('requests.Session.get')
    def test_get_dictionary_urls(self, mock_get):
        """Test de la récupération des URLs du dictionnaire."""
        mock_html = """
        <html>
            <a class="word-link" href="/dictionnaire/bonjour">Bonjour</a>
            <a class="word-link" href="/dictionnaire/merci">Merci</a>
        </html>
        """
        mock_get.return_value.text = mock_html
        mock_get.return_value.status_code = 200

        urls = self.extractor._get_dictionary_urls()
        self.assertTrue(isinstance(urls, list))
        self.assertEqual(len(urls), 2)
        self.assertTrue(all(url.startswith('https://dico.elix-lsf.fr') for url in urls))

        # Test avec une erreur réseau
        mock_get.side_effect = requests.exceptions.RequestException()
        urls_error = self.extractor._get_dictionary_urls()
        self.assertEqual(urls_error, [])

    def test_rate_limiting(self):
        """Test de la limitation du taux de requêtes."""
        start_time = datetime.now()
        
        # Effectuer plusieurs requêtes rapidement
        for _ in range(3):
            self.extractor.extract_gesture_data('https://dico.elix-lsf.fr/dictionnaire/test')
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Vérifier que le temps d'exécution est conforme à la limitation de taux
        # (3 requêtes avec 1 requête par seconde = minimum 2 secondes)
        self.assertGreaterEqual(duration, 2.0)

if __name__ == '__main__':
    unittest.main()