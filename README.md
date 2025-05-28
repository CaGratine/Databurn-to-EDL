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

```bash
pip install opencv-python
pip install pytesseract
```

Assurez-vous d'avoir [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) et [FFmpeg](https://ffmpeg.org/download.html) installés sur votre système.

## Utilisation

Pour utiliser le script en ligne de commande :

```python
python "Databurn to edl Tesseract.py"
```

Ou lancez l'interface graphique :

```python
python Databurn_to_edl_GUI.py
```

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou à soumettre une pull request.