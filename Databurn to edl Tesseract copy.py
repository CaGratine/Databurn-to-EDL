import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import os
import torch
import cv2
import pytesseract
import easyocr
import subprocess
import re
import shutil
from PIL import Image, ImageTk
from concurrent.futures import ThreadPoolExecutor

# Variable globale pour annuler le traitement
cancel_processing = False

# Variable globale pour la zone de recadrage
crop_coords = (10, 950, 1400, 250)  # Valeurs par défaut (x, y, w, h)

# Fonction pour extraire les frames
def extract_frames(video_path, output_folder, fps=25):
    os.makedirs(output_folder, exist_ok=True)
    command = [
        'ffmpeg', '-i', video_path, '-vf', f'fps={fps}', f'{output_folder}/frame_%04d.png'
    ]
    result = subprocess.run(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr.decode()}")

# Fonction pour sélectionner la zone de recadrage
def select_crop_area(video_path):
    global crop_coords
    output_folder = "temp_frames"
    os.makedirs(output_folder, exist_ok=True)

    # Extraire la première image
    extract_frames(video_path, output_folder, fps=1)
    first_frame_path = os.path.join(output_folder, "frame_0001.png")

    # Charger l'image avec Pillow
    image = Image.open(first_frame_path)

    # Créer une fenêtre Tkinter pour afficher l'image
    crop_window = tk.Toplevel(root)
    crop_window.title("Sélectionnez la zone à recadrer")

    # Convertir l'image pour Tkinter
    tk_image = ImageTk.PhotoImage(image)
    canvas = tk.Canvas(crop_window, width=image.width, height=image.height)
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)

    # Variables pour stocker les coordonnées de la sélection
    rect_id = None
    start_x = start_y = end_x = end_y = 0

    def on_mouse_press(event):
        nonlocal start_x, start_y, rect_id
        start_x, start_y = event.x, event.y
        rect_id = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline="red")

    def on_mouse_drag(event):
        nonlocal rect_id
        end_x, end_y = event.x, event.y
        canvas.coords(rect_id, start_x, start_y, end_x, end_y)

    def on_mouse_release(event):
        global crop_coords
        end_x, end_y = event.x, event.y
        crop_coords = (start_x, start_y, end_x - start_x, end_y - start_y)
        crop_window.destroy()
        log_text.insert(tk.END, f"Zone sélectionnée : {crop_coords}\n")
        log_text.see(tk.END)
        print(f"Zone sélectionnée : {crop_coords}")

    # Lier les événements de la souris
    canvas.bind("<ButtonPress-1>", on_mouse_press)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_release)

    # Lancer la boucle Tkinter pour cette fenêtre
    crop_window.mainloop()

    # Supprimer les frames temporaires
    shutil.rmtree(output_folder)

# Fonction pour prétraiter une image
def preprocess_image(image_path):
    global crop_coords
    processed_folder = "processed_frames"
    os.makedirs(processed_folder, exist_ok=True)  # Créer le dossier s'il n'existe pas

    # Charger l'image en niveaux de gris
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    x, y, w, h = map(int, crop_coords)
    cropped_image = image[y:y+h, x:x+w]

    # Augmenter la résolution
    resized_image = cv2.resize(cropped_image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # Inverser les couleurs (texte noir sur fond blanc)
    inverted_image = cv2.bitwise_not(resized_image)

    # Appliquer un léger flou pour réduire le bruit
    processed_image = cv2.GaussianBlur(inverted_image, (3, 3), 0)

    # Sauvegarder l'image prétraitée
    processed_image_path = os.path.join(processed_folder, os.path.basename(image_path))
    cv2.imwrite(processed_image_path, processed_image)
    print(f"Image prétraitée sauvegardée : {processed_image_path}")

    return processed_image

# Fonction pour extraire le texte avec Tesseract
def extract_text_with_tesseract(image_path):
    processed_image = preprocess_image(image_path)
    config = '--psm 6 -c tessedit_char_whitelist=0123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._'
    return pytesseract.image_to_string(processed_image, config=config).strip()

# Fonction pour extraire le texte avec EasyOCR
def extract_text_with_easyocr(image_path, reader):
    """Utilise EasyOCR pour extraire le texte d'une image avec le prétraitement."""
    try:
        # Appliquer le prétraitement
        processed_image = preprocess_image(image_path)

        # Sauvegarder l'image prétraitée temporairement
        temp_path = "temp_processed_image.png"
        cv2.imwrite(temp_path, processed_image)

        # Utiliser EasyOCR sur l'image prétraitée
        results = reader.readtext(temp_path, detail=0)  # `detail=0` retourne uniquement le texte

        # Supprimer l'image temporaire
        os.remove(temp_path)

        # Retourner le texte extrait
        text = " ".join(results)
        print(f"Texte extrait avec EasyOCR : {text}")
        return text.strip()
    except Exception as e:
        print(f"Erreur lors de l'extraction du texte avec EasyOCR : {e}")
        return ""

# Fonction pour extraire le texte en fonction du choix de l'OCR
def extract_text_from_image(image_path, ocr_tool, reader=None):
    """Extrait le texte d'une image en fonction de l'outil OCR sélectionné."""
    if ocr_tool == "tesseract":
        return extract_text_with_tesseract(image_path)
    elif ocr_tool == "easyocr":
        return extract_text_with_easyocr(image_path, reader)
    else:
        raise ValueError("Invalid OCR tool selected.")

# Fonction pour générer un fichier EDL
def generate_edl(timecode_data, output_file):
    with open(output_file, "w") as edl_file:
        edl_file.write("TITLE: Generated Timeline\n")
        edl_file.write("FCM: NON-DROP FRAME\n\n")
        for idx, entry in enumerate(timecode_data, start=1):
            edl_file.write(f"{idx:03}  AX       V     C        "
                           f"{entry['start_tc']} {entry['end_tc']} "
                           f"{entry['timeline_in']} {entry['timeline_out']}\n")
            edl_file.write(f"* FROM CLIP NAME: {entry['filename']}\n\n")

# Fonction pour nettoyer les dossiers temporaires
def clean_temporary_folders(folders):
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder)

# Fonction pour calculer le timecode de fin
# en fonction du timecode de début, du nombre d'images et de la fréquence d'images
def calculate_end_tc(start_tc, frame_count, fps):
    """Calcule le timecode de fin en fonction du timecode de début, du nombre d'images et de la fréquence d'images."""
    hours, minutes, seconds, frames = map(int, start_tc.split(":"))
    total_frames = hours * 3600 * fps + minutes * 60 * fps + seconds * fps + frames + frame_count
    new_hours = total_frames // (3600 * fps)
    new_minutes = (total_frames % (3600 * fps)) // (60 * fps)
    new_seconds = (total_frames % (60 * fps)) // fps
    new_frames = total_frames % fps
    return f"{new_hours:02}:{new_minutes:02}:{new_seconds:02}:{new_frames:02}"

# Fonction principale pour le traitement
def process_video_thread(video_path, ocr_tool, log_widget, progress):
    global cancel_processing
    try:
        log_widget.insert(tk.END, "Début du traitement...\n")
        log_widget.see(tk.END)
        root.update_idletasks()

        output_folder = "frames"
        processed_folder = "processed_frames"
        fps = 25
        edl_output = os.path.splitext(video_path)[0] + ".edl"

        # Extraction des frames
        extract_frames(video_path, output_folder, fps)
        log_widget.insert(tk.END, "Frames extraites avec succès.\n")
        log_widget.see(tk.END)

        image_files = sorted(os.listdir(output_folder))
        progress["maximum"] = len(image_files)

        timecode_data = []
        previous_filename = None
        start_tc = None
        frame_count = 0
        timeline_in = "10:00:00:00"

        # Initialiser le modèle EasyOCR une seule fois si nécessaire
        reader = None
        if ocr_tool == "easyocr":
            gpu_available = torch.cuda.is_available()
            reader = easyocr.Reader(['en'], gpu_available)
            log_widget.insert(tk.END, f"EasyOCR utilise le {'GPU' if gpu_available else 'CPU'}.\n")
            log_widget.see(tk.END)

        # Fonction pour traiter une seule image
        def process_single_image(image_file):
            if cancel_processing:
                return None

            image_path = os.path.join(output_folder, image_file)
            extracted_text = extract_text_from_image(image_path, ocr_tool, reader)

            # Afficher le texte extrait dans le log
            log_widget.insert(tk.END, f"Texte extrait de {image_file} : {extracted_text}\n")
            log_widget.see(tk.END)

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

        # Traiter les images
        if ocr_tool == "tesseract":
            # Traitement parallèle pour Tesseract
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(process_single_image, image_files))
        else:
            # Traitement séquentiel pour EasyOCR
            results = [process_single_image(image_file) for image_file in image_files]

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

        generate_edl(timecode_data, edl_output)
        log_widget.insert(tk.END, f"Fichier EDL généré : {edl_output}\n")
        log_widget.see(tk.END)

        clean_temporary_folders([output_folder, processed_folder])
        log_widget.insert(tk.END, "Dossiers temporaires nettoyés.\n")
        log_widget.see(tk.END)

        messagebox.showinfo("Succès", "Traitement terminé avec succès.")
    except Exception as e:
        log_widget.insert(tk.END, f"Erreur : {e}\n")
        log_widget.see(tk.END)
        messagebox.showerror("Erreur", f"Une erreur est survenue : {e}")

# Fonction pour démarrer le traitement dans un thread
def process_video():
    global cancel_processing
    cancel_processing = False  # Réinitialiser le flag d'annulation
    video_path = video_path_var.get()
    if not video_path:
        messagebox.showerror("Erreur", "Veuillez sélectionner un fichier vidéo.")
        return

    ocr_tool = ocr_choice.get()
    threading.Thread(target=process_video_thread, args=(video_path, ocr_tool, log_text, progress)).start()

# Fonction pour annuler le traitement
def cancel_video_processing():
    global cancel_processing
    if messagebox.askyesno("Confirmation", "Voulez-vous vraiment annuler le traitement ?"):
        cancel_processing = True

# Interface graphique
root = tk.Tk()
root.title("Databurn to EDL")

# Variables
video_path_var = tk.StringVar()
ocr_choice = tk.StringVar(value="tesseract")

# Widgets
tk.Label(root, text="Vidéo :").grid(row=0, column=0, sticky="e")
tk.Entry(root, textvariable=video_path_var, width=50).grid(row=0, column=1, padx=5, pady=5)
tk.Button(root, text="Parcourir", command=lambda: video_path_var.set(filedialog.askopenfilename(filetypes=[("Fichiers vidéo", "*.mp4 *.mov")]))).grid(row=0, column=2, padx=5, pady=5)

tk.Button(root, text="Sélectionner la zone", command=lambda: select_crop_area(video_path_var.get())).grid(row=1, column=0, columnspan=3, pady=5)

tk.Label(root, text="OCR :").grid(row=2, column=0, sticky="e")
tk.Radiobutton(root, text="Tesseract (better)", variable=ocr_choice, value="tesseract").grid(row=2, column=1, sticky="w")
tk.Radiobutton(root, text="EasyOCR (faster)", variable=ocr_choice, value="easyocr").grid(row=2, column=2, sticky="w")

tk.Button(root, text="Lancer le traitement", command=process_video).grid(row=3, column=0, pady=10)
tk.Button(root, text="Annuler", command=cancel_video_processing).grid(row=3, column=2, pady=10)

log_text = scrolledtext.ScrolledText(root, width=80, height=20)
log_text.grid(row=4, column=0, columnspan=3, padx=10, pady=10)

progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress.grid(row=5, column=0, columnspan=3, pady=10)

# Lancement de l'application
root.mainloop()
