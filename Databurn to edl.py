import cv2
import easyocr
import xml.etree.ElementTree as ET
import subprocess
import os
import shutil

def extract_frames(video_path, output_folder, fps=25):
    """Utilise FFmpeg pour extraire des images de la vidéo."""
    os.makedirs(output_folder, exist_ok=True)
    command = [
        'ffmpeg', '-i', video_path, '-vf', f'fps={fps}', f'{output_folder}/frame_%04d.png'
    ]
    result = subprocess.run(command)

    if result.returncode == 0:
        print("Frames extracted successfully.")
    if result.returncode != 0:
        print("FFmpeg error:", result.stderr.decode())
        raise RuntimeError("Failed to extract frames. Check the video file and FFmpeg installation.")

def preprocess_image(image_path, save_processed=True, processed_folder="processed_frames"):
    """Prépare l’image pour l’OCR en recadrant, inversant les couleurs et réduisant le bruit."""
    # Charger l'image en niveaux de gris
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # Définir les coordonnées de la zone à recadrer (ajustez selon vos besoins)
    x, y, w, h = 10, 900, 1200, 400  # Exemple : rectangle (x, y, largeur, hauteur)
    cropped_image = image[y:y+h, x:x+w]
    
    # Inverser les couleurs (texte noir sur fond blanc)
    inverted_image = cv2.bitwise_not(cropped_image)
    
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
    """Utilise EasyOCR pour extraire le texte d’une image."""
    reader = easyocr.Reader(['en'], gpu=True)  # Forcer l'utilisation du GPU
    results = reader.readtext(image_path)
    text = " ".join([result[1] for result in results])  # Concatène tous les textes détectés
    print(f"Extracted text from '{image_path}': {text}")
    return text.strip()

def timecode_to_milliseconds(timecode, fps=25):
    """Convertit un timecode en millisecondes."""
    hours, minutes, seconds, frames = map(int, timecode.split(":"))
    milliseconds = ((hours * 3600 + minutes * 60 + seconds) * 1000) + (frames * 1000 // fps)
    return milliseconds

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

def calculate_end_tc(start_tc, frame_count, fps):
    """Calcule le timecode de fin en fonction du timecode de début, du nombre d'images et de la fréquence d'images."""
    hours, minutes, seconds, frames = map(int, start_tc.replace(".", ":").split(":"))
    total_frames = hours * 3600 * fps + minutes * 60 * fps + seconds * fps + frames + frame_count
    new_hours = total_frames // (3600 * fps)
    new_minutes = (total_frames % (3600 * fps)) // (60 * fps)
    new_seconds = (total_frames % (60 * fps)) // fps
    new_frames = total_frames % fps
    return f"{new_hours:02}:{new_minutes:02}:{new_seconds:02}:{new_frames:02}"

def clean_frames_folder(folder_path):
    """Supprime le dossier contenant les frames extraites."""
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        print(f"Dossier '{folder_path}' purgé avec succès.")
    else:
        print(f"Dossier '{folder_path}' introuvable, aucune action nécessaire.")

def main(video_path):
    output_folder = "frames"
    fps = 25  # Fréquence d'images par seconde
    extract_frames(video_path, output_folder)
    
    timecode_data = []
    previous_filename = None
    start_tc = None
    frame_count = 0  # Compteur pour les occurrences consécutives du même fichier
    timeline_in = "10:00:00:00"  # Le premier timeline_in commence à 10:00:00:00
    previous_timecode = None  # Pour stocker le dernier timecode valide

    # Liste des fichiers triés
    image_files = sorted(os.listdir(output_folder))

    for idx, image_file in enumerate(image_files):
        image_path = os.path.join(output_folder, image_file)
        extracted_text = extract_text_from_image(image_path)
        
        # Extraction du timecode et du fichier
        lines = extracted_text.split("\n")
        timecode = next((line.split("SRC TC: ")[1][:11] for line in lines if "SRC TC: " in line and ":" in line), None)
        filename = next(
            (line.split("File name: ")[1].split()[0].split(".mp4")[0] + ".mp4" if ".mp4" in line.lower() else
             line.split("File name: ")[1].split()[0].split(".mov")[0] + ".mov"
             for line in lines if "File name: " in line and any(ext in line for ext in [".mp4", ".MP4", ".mov", ".MOV"])),
            "unknown.mov"
        )
        
        # Si le timecode est manquant
        if timecode is None:
            if previous_timecode is not None and filename == previous_filename:
                # Interpoler à partir du timecode précédent
                timecode = calculate_end_tc(previous_timecode, 1, fps)
            elif idx + 1 < len(image_files):
                # Interpoler à partir du timecode suivant
                next_image_path = os.path.join(output_folder, image_files[idx + 1])
                next_extracted_text = extract_text_from_image(next_image_path)
                next_lines = next_extracted_text.split("\n")
                next_timecode = next(
                    (line.split("SRC TC: ")[1][:11] for line in next_lines if "SRC TC: " in line and ":" in line), None
                )
                if next_timecode is not None:
                    timecode = calculate_end_tc(next_timecode, -1, fps)  # Soustraire une frame
        
        if filename == previous_filename:
            # Si le fichier est le même que le précédent, on incrémente le compteur
            frame_count += 1
        else:
            # Si le fichier change, on enregistre les données pour le fichier précédent
            if previous_filename is not None:
                # Calcul de `end_tc` et `timeline_out` pour le fichier précédent
                end_tc = calculate_end_tc(start_tc, frame_count, fps)
                timeline_out = calculate_end_tc(timeline_in, frame_count, fps)
                timecode_data.append({
                    "filename": previous_filename,
                    "start_tc": start_tc,
                    "end_tc": end_tc,
                    "timeline_in": timeline_in,
                    "timeline_out": timeline_out
                })
                # Mise à jour du prochain timeline_in
                timeline_in = timeline_out
            
            # Réinitialisation pour le nouveau fichier
            previous_filename = filename
            start_tc = timecode
            frame_count = 1  # On commence à compter pour le nouveau fichier
        
        # Mettre à jour le dernier timecode valide
        if timecode is not None:
            previous_timecode = timecode
    
    # Ajouter les données pour le dernier fichier
    if previous_filename is not None:
        # Si le timecode de la dernière image est manquant, on l'interpole
        if timecode is None and previous_timecode is not None:
            timecode = calculate_end_tc(previous_timecode, 1, fps)
        
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
    print("Fichier EDL généré : output.edl")
    clean_frames_folder(output_folder)

if __name__ == "__main__":
    main("video.mp4")
