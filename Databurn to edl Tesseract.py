import cv2
print(cv2.__version__)
import pytesseract
import os
import shutil
import subprocess
import re

def extract_frames(video_path, output_folder, fps=25):
    """Utilise FFmpeg pour extraire des images de la vidéo."""
    os.makedirs(output_folder, exist_ok=True)
    command = [
        'ffmpeg', '-i', video_path, '-vf', f'fps={fps}', f'{output_folder}/frame_%04d.png'
    ]
    result = subprocess.run(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    if result.returncode == 0:
        print("Frames extracted successfully.")
    else:
        print("FFmpeg error:", result.stderr.decode())
        raise RuntimeError("Failed to extract frames. Check the video file and FFmpeg installation.")

def preprocess_image(image_path, save_processed=True, processed_folder="processed_frames"):
    """Prépare l’image pour l’OCR en recadrant, inversant les couleurs et augmentant la résolution."""
    # Charger l'image en niveaux de gris
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # Définir les coordonnées de la zone à recadrer (ajustez selon vos besoins)
    x, y, w, h = 10, 950, 1400, 250  # Exemple : rectangle (x, y, largeur, hauteur)
    cropped_image = image[y:y+h, x:x+w]
    
    # Augmenter la résolution
    resized_image = cv2.resize(cropped_image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # Inverser les couleurs (texte noir sur fond blanc)
    inverted_image = cv2.bitwise_not(resized_image)
    
    # Appliquer un léger flou pour réduire le bruit
    processed_image = cv2.GaussianBlur(inverted_image, (3, 3), 0)
    
    # Sauvegarder l'image prétraitée si demandé
    if save_processed:
        os.makedirs(processed_folder, exist_ok=True)
        processed_image_path = os.path.join(processed_folder, os.path.basename(image_path))
        cv2.imwrite(processed_image_path, processed_image)
        print(f"Image prétraitée sauvegardée : {processed_image_path}")
    
    return processed_image

def extract_text_from_image(image_path):
    """Utilise Tesseract OCR pour extraire le texte d’une image."""
    try:
        processed_image = preprocess_image(image_path)
        config = '--psm 6 -c tessedit_char_whitelist=0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._'
        text = pytesseract.image_to_string(processed_image, config=config)
        if not text:
            print(f"Aucun texte extrait pour '{image_path}'.")
            return ""
        print(f"Extracted text from '{image_path}': {text}")
        return text.strip()
    except Exception as e:
        print(f"Erreur lors de l'extraction du texte pour '{image_path}': {e}")
        return ""

def calculate_end_tc(start_tc, frame_count, fps):
    """Calcule le timecode de fin en fonction du timecode de début, du nombre d'images et de la fréquence d'images."""
    hours, minutes, seconds, frames = map(int, start_tc.split(":"))
    total_frames = hours * 3600 * fps + minutes * 60 * fps + seconds * fps + frames + frame_count
    new_hours = total_frames // (3600 * fps)
    new_minutes = (total_frames % (3600 * fps)) // (60 * fps)
    new_seconds = (total_frames % (60 * fps)) // fps
    new_frames = total_frames % fps
    return f"{new_hours:02}:{new_minutes:02}:{new_seconds:02}:{new_frames:02}"

def clean_temporary_folders(folders):
    """Supprime les dossiers temporaires."""
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"Dossier '{folder}' purgé avec succès.")
        else:
            print(f"Dossier '{folder}' introuvable, aucune action nécessaire.")

def generate_edl(timecode_data, output_file):
    """Génère un fichier EDL à partir des données de timecode."""
    with open(output_file, "w") as edl_file:
        # En-tête du fichier EDL
        edl_file.write("TITLE: Generated Timeline\n")
        edl_file.write("FCM: NON-DROP FRAME\n\n")
        
        # Boucle sur les données pour ajouter les clips
        for idx, entry in enumerate(timecode_data, start=1):
            edl_file.write(f"{idx:03}  AX       V     C        "
                           f"{entry['start_tc']} {entry['end_tc']} "
                           f"{entry['timeline_in']} {entry['timeline_out']}\n")
            edl_file.write(f"* FROM CLIP NAME: {entry['filename']}\n\n")
    
    print(f"Fichier EDL généré : {output_file}")

def main(video_path):
    output_folder = "frames"
    processed_folder = "processed_frames"
    fps = 25  # Fréquence d'images par seconde

    # Vérifier si le fichier vidéo existe
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Le fichier vidéo '{video_path}' est introuvable.")
    
    # Extraire les frames
    extract_frames(video_path, output_folder, fps)
    
    timecode_data = []
    previous_filename = None
    start_tc = None
    frame_count = 0
    timeline_in = "10:00:00:00"
    previous_timecode = None

    # Boucle principale
    for idx, image_file in enumerate(sorted(os.listdir(output_folder))):
        image_path = os.path.join(output_folder, image_file)
        extracted_text = extract_text_from_image(image_path)
        
        if not extracted_text:
            print(f"Aucun texte valide extrait pour l'image : {image_path}")
            continue
        
        # Extraction du timecode
        timecode_match = re.search(r"TC:\s*(\d{2}:\d{2}:\d{2}:\d{2})", extracted_text)
        timecode = timecode_match.group(1) if timecode_match else None
        
        # Extraction du nom de fichier
        filename_match = re.search(r"Filename:\s*([\w\-.]+(?:\.mp4|\.MP4|\.mov|\.MOV))", extracted_text)
        filename = filename_match.group(1) if filename_match else "unknown.mov"
        
        if not timecode:
            print(f"[DEBUG] Aucun timecode trouvé pour l'image : {image_path}")
            timecode = "00:00:00:00"

        if not filename:
            print(f"[DEBUG] Aucun nom de fichier trouvé pour l'image : {image_path}")
            filename = "unknown.mov"
        
        if filename == previous_filename:
            frame_count += 1
        else:
            if previous_filename is not None:
                end_tc = calculate_end_tc(start_tc, frame_count, fps)
                timeline_out = calculate_end_tc(timeline_in, frame_count, fps)
                timecode_data.append({
                    "filename": previous_filename,
                    "start_tc": start_tc,
                    "end_tc": end_tc,
                    "timeline_in": timeline_in,
                    "timeline_out": timeline_out
                })
                timeline_in = timeline_out
            
            previous_filename = filename
            start_tc = timecode
            frame_count = 1
        
        if timecode is not None:
            previous_timecode = timecode

    # Ajouter les données pour le dernier fichier
    if previous_filename is not None:
        end_tc = calculate_end_tc(start_tc, frame_count, fps)
        timeline_out = calculate_end_tc(timeline_in, frame_count, fps)
        timecode_data.append({
            "filename": previous_filename,
            "start_tc": start_tc,
            "end_tc": end_tc,
            "timeline_in": timeline_in,
            "timeline_out": timeline_out
        })
    
    generate_edl(timecode_data, "output.edl")
    clean_temporary_folders([output_folder, processed_folder])

if __name__ == "__main__":
    main("video.mp4")
