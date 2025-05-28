import cv2
import pytesseract
import os
import shutil
import subprocess
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
from tkinter import ttk
from tqdm import tqdm
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor

def log_message(message, log_widget):
    """Affiche un message dans la zone de log."""
    if log_widget is not None:
        log_widget.insert(tk.END, message + "\n")
        log_widget.see(tk.END)
    else:
        print(message)  # Affiche le message dans la console si log_widget est None

def extract_frames(video_path, output_folder, fps=25, log_widget=None):
    """Utilise FFmpeg pour extraire des images de la vidéo."""
    os.makedirs(output_folder, exist_ok=True)
    command = [
        'ffmpeg', '-i', video_path, '-vf', f'fps={fps}', f'{output_folder}/frame_%04d.png'
    ]
    result = subprocess.run(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    if result.returncode == 0:
        log_message("Frames extracted successfully.", log_widget)
    else:
        log_message("FFmpeg error: " + result.stderr.decode(), log_widget)
        raise RuntimeError("Failed to extract frames. Check the video file and FFmpeg installation.")

def preprocess_image(image_path, save_processed=True, processed_folder="processed_frames", log_widget=None):
    """Prépare l’image pour l’OCR en recadrant, inversant les couleurs et augmentant la résolution."""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    x, y, w, h = 10, 1000, 1400, 150
    cropped_image = image[y:y+h, x:x+w]
    resized_image = cv2.resize(cropped_image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    inverted_image = cv2.bitwise_not(resized_image)
    processed_image = cv2.GaussianBlur(inverted_image, (3, 3), 0)

    if save_processed:
        os.makedirs(processed_folder, exist_ok=True)
        processed_image_path = os.path.join(processed_folder, os.path.basename(image_path))
        cv2.imwrite(processed_image_path, processed_image)
        log_message(f"Image prétraitée sauvegardée : {processed_image_path}", log_widget)
    
    return processed_image

def preprocess_and_extract(image_path):
    """Prétraite l'image et extrait le texte."""
    processed_image = preprocess_image(image_path)
    return extract_text_from_image(processed_image)

def extract_text_from_image(image_path, log_widget=None):
    """Utilise Tesseract OCR pour extraire le texte d’une image."""
    try:
        processed_image = preprocess_image(image_path, log_widget=log_widget)
        config = '--psm 6 -c tessedit_char_whitelist=0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._'
        text = pytesseract.image_to_string(processed_image, config=config)
        if not text:
            log_message(f"Aucun texte extrait pour '{image_path}'.", log_widget)
            return ""
        log_message(f"Extracted text from '{image_path}': {text}", log_widget)
        return text.strip()
    except Exception as e:
        log_message(f"Erreur lors de l'extraction du texte pour '{image_path}': {e}", log_widget)
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

def clean_temporary_folders(folders, log_widget=None):
    """Supprime les dossiers temporaires."""
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            log_message(f"Dossier '{folder}' purgé avec succès.", log_widget)
        else:
            log_message(f"Dossier '{folder}' introuvable, aucune action nécessaire.", log_widget)

def generate_edl(timecode_data, output_file, log_widget=None):
    """Génère un fichier EDL à partir des données de timecode."""
    with open(output_file, "w") as edl_file:
        edl_file.write("TITLE: Generated Timeline\n")
        edl_file.write("FCM: NON-DROP FRAME\n\n")
        for idx, entry in enumerate(timecode_data, start=1):
            edl_file.write(f"{idx:03}  AX       V     C        "
                           f"{entry['start_tc']} {entry['end_tc']} "
                           f"{entry['timeline_in']} {entry['timeline_out']}\n")
            edl_file.write(f"* FROM CLIP NAME: {entry['filename']}\n\n")
    log_message(f"Fichier EDL généré : {output_file}", log_widget)

def process_video_thread(log_widget, progress):
    """Lance le traitement de la vidéo dans un thread séparé."""
    global cancel_processing
    cancel_processing = False  # Réinitialiser le flag d'annulation

    video_path = video_path_var.get()
    output_folder = "frames"
    processed_folder = "processed_frames"
    fps = 25
    edl_output = edl_output_var.get()

    if not video_path or not os.path.exists(video_path):
        messagebox.showerror("Erreur", "Veuillez sélectionner un fichier vidéo valide.")
        return

    if not edl_output:
        messagebox.showerror("Erreur", "Veuillez sélectionner un fichier de sortie pour l'EDL.")
        return

    try:
        extract_frames(video_path, output_folder, fps, log_widget)
        timecode_data = []
        previous_filename = None
        start_tc = None
        frame_count = 0
        timeline_in = "10:00:00:00"

        # Préparer la barre de progression
        image_files = sorted(os.listdir(output_folder))
        progress["maximum"] = len(image_files)

        # Fonction pour traiter une seule image
        def process_single_image(image_file):
            if cancel_processing:
                return None

            image_path = os.path.join(output_folder, image_file)
            extracted_text = extract_text_from_image(image_path, log_widget)

            # Analyse du texte extrait
            timecode_match = re.search(r"TC:\s*(\d{2}:\d{2}:\d{2}:\d{2})", extracted_text)
            timecode = timecode_match.group(1) if timecode_match else "00:00:00:00"

            filename_match = re.search(r"Filename:\s*([\w\-.]+(?:\.mp4|\.MP4|\.mov|\.MOV))", extracted_text)
            filename = filename_match.group(1) if filename_match else "unknown.mov"

            return {
                "image_file": image_file,
                "timecode": timecode,
                "filename": filename,
                "text": extracted_text
            }

        # Traiter les images en parallèle
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(process_single_image, image_files))

        # Traiter les résultats
        for idx, result in enumerate(results):
            if result is None:
                continue

            progress["value"] = idx + 1
            root.update_idletasks()

            filename = result["filename"]
            timecode = result["timecode"]

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

        generate_edl(timecode_data, edl_output, log_widget)
        clean_temporary_folders([output_folder, processed_folder], log_widget)
        messagebox.showinfo("Succès", "Traitement terminé avec succès.")
    except Exception as e:
        messagebox.showerror("Erreur", f"Une erreur est survenue : {e}")

def process_video():
    """Démarre le traitement dans un thread séparé."""
    threading.Thread(target=process_video_thread, args=(log_text, progress)).start()

def select_video():
    """Ouvre une boîte de dialogue pour sélectionner une vidéo."""
    video_path = filedialog.askopenfilename(filetypes=[("Fichiers vidéo", "*.mp4 *.mov")])
    video_path_var.set(video_path)

def select_edl_output():
    """Ouvre une boîte de dialogue pour sélectionner le fichier de sortie EDL."""
    edl_output = filedialog.asksaveasfilename(defaultextension=".edl", filetypes=[("Fichiers EDL", "*.edl")])
    edl_output_var.set(edl_output)

def cancel_video_processing():
    """Annule le traitement de la vidéo."""
    global cancel_processing
    if messagebox.askyesno("Confirmation", "Voulez-vous vraiment annuler le traitement ?"):
        cancel_processing = True
        log_message("Annulation demandée par l'utilisateur.", log_text)

if __name__ == "__main__":
    # Création de la fenêtre principale
    root = tk.Tk()
    root.title("Databurn to EDL")

    # Variables pour les chemins
    video_path_var = tk.StringVar()
    edl_output_var = tk.StringVar()

    # Widgets
    tk.Label(root, text="Vidéo :").grid(row=0, column=0, sticky="e")
    tk.Entry(root, textvariable=video_path_var, width=50).grid(row=0, column=1, padx=5, pady=5)
    tk.Button(root, text="Parcourir", command=select_video).grid(row=0, column=2, padx=5, pady=5)

    tk.Label(root, text="Fichier EDL :").grid(row=1, column=0, sticky="e")
    tk.Entry(root, textvariable=edl_output_var, width=50).grid(row=1, column=1, padx=5, pady=5)
    tk.Button(root, text="Parcourir", command=select_edl_output).grid(row=1, column=2, padx=5, pady=5)

    tk.Button(root, text="Lancer le traitement", command=process_video).grid(row=2, column=0, columnspan=3, pady=10)
    tk.Button(root, text="Annuler", command=cancel_video_processing).grid(row=2, column=2, padx=5, pady=10)

    log_text = scrolledtext.ScrolledText(root, width=80, height=20)
    log_text.grid(row=3, column=0, columnspan=3, padx=10, pady=10)

    # Barre de progression
    progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
    progress.grid(row=4, column=0, columnspan=3, pady=10)

    # Lancement de l'application
    root.mainloop()