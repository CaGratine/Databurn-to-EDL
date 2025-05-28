# Databurn to EDL

Ce projet permet d'extraire des informations de timecode (databurn) depuis des fichiers vidéo et de générer des fichiers EDL (Edit Decision List) ou FCPXML pour l'édition vidéo.

## Fonctionnalités

- Extraction de frames vidéo avec FFmpeg
- Reconnaissance de texte (OCR) des timecodes brûlés dans la vidéo avec Tesseract
- Génération de fichiers EDL compatibles avec les logiciels de montage
- Interface graphique pour faciliter l'utilisation

## Prérequis

- Python 3.6+
- OpenCV
- Tesseract OCR
- FFmpeg

## Installation

### 1. Installation des dépendances Python

```bash
pip install -r requirements.txt
```

### 2. Installation des dépendances externes obligatoires

Ce projet nécessite deux logiciels externes qui doivent être installés séparément:

- **FFmpeg**: [Télécharger FFmpeg](https://ffmpeg.org/download.html)
  - Assurez-vous que FFmpeg est accessible depuis la ligne de commande (dans le PATH système)
  
- **Tesseract OCR**: [Télécharger Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
  - Assurez-vous que Tesseract est accessible depuis la ligne de commande (dans le PATH système)

L'application vérifiera automatiquement au démarrage si ces dépendances sont correctement installées.

## Utilisation

Pour utiliser la version la plus récente avec interface graphique :

```python
python Databurn_to_edl_tesseract_parallele_GUI.py
```

Autres versions disponibles:
- Version ligne de commande : `python "Databurn to edl Tesseract.py"`
- Version GUI simple : `python Databurn_to_edl_GUI.py`

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou à soumettre une pull request.