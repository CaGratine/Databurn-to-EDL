import cv2
print(cv2.__version__)
import pytesseract
import xml.etree.ElementTree as ET
import subprocess
import os

def extract_frames(video_path, output_folder, fps=25):
    """Utilise FFmpeg pour extraire des images de la vidéo."""
    os.makedirs(output_folder, exist_ok=True)
    command = [
        'ffmpeg', '-i', video_path, '-vf', f'fps={fps}', f'{output_folder}/frame_%04d.png'
    ]
    # result = subprocess.run(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    result = subprocess.run(command)

    if result.returncode == 0:
        print("Frames extracted successfully.")
    if result.returncode != 0:
        print("FFmpeg error:", result.stderr.decode())
        raise RuntimeError("Failed to extract frames. Check the video file and FFmpeg installation.")

def preprocess_image(image_path):
    """Améliore l’image pour l’OCR (binarisation, filtre de contraste)."""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    _, thresh = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh

def extract_text_from_image(image_path):
    """Utilise Tesseract OCR pour extraire le texte d’une image."""
    processed_image = preprocess_image(image_path)
    text = pytesseract.image_to_string(processed_image, config='--psm 6')
    print(f"Extracted text from '{image_path}': {text}")
    return text.strip()

def timecode_to_milliseconds(timecode, fps=25):
    """Convertit un timecode en millisecondes."""
    hours, minutes, seconds, frames = map(int, timecode.split(":"))
    milliseconds = ((hours * 3600 + minutes * 60 + seconds) * 1000) + (frames * 1000 // fps)
    return milliseconds

def generate_fcpxml(timecode_data, output_file, video_path, output_folder):
    """Génère un fichier XML compatible avec DaVinci Resolve."""
    root = ET.Element("fcpxml", version="1.8")
    
    # Resources section
    resources = ET.SubElement(root, "resources")
    format_1080p = ET.SubElement(resources, "format", id="r0", frameDuration="1/25s", height="1080", name="FFVideoFormat1080p25", width="1920")
    format_4k = ET.SubElement(resources, "format", id="r1", frameDuration="1/25s", height="2160", name="FFVideoFormat3840x2160p25", width="3840")
    
    # Utiliser un ensemble pour éviter les doublons et un dictionnaire pour associer les noms aux IDs
    added_assets = {}
    
    for idx, entry in enumerate(timecode_data):
        if entry['filename'] not in added_assets:
            asset_id = f"r{idx + 2}"
            ET.SubElement(
                resources,
                "asset",
                hasAudio="1",
                id=asset_id,
                start=f"{entry['start']}/25s",
                # duration=f"{entry['duration']}/25s",
                name=entry['filename'],
                format="r1",
                src=f"file://localhost/{entry['filepath']}",
                audioChannels="2",
                audioSources="1",
                hasVideo="1"
            )
            added_assets[entry['filename']] = asset_id  # Associer le nom du fichier à l'ID
    
    # Library section
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name="Timeline 2 (Resolve)")
    project = ET.SubElement(event, "project", name="Timeline 2 (Resolve)")
    sequence = ET.SubElement(project, "sequence", duration="8/25s", format="r0", tcStart="3600/1s", tcFormat="NDF")
    spine = ET.SubElement(sequence, "spine")
    
    for idx, entry in enumerate(timecode_data):
        clip = ET.SubElement(
            spine,
            "clip",
            start=f"{entry['start']}/25s",
            duration=f"{entry['clip_duration']}/25s",
            name=entry['filename'],
            format="r1",
            offset=f"{entry['offset']}/1s",
            enabled="1",
            tcFormat="NDF"
        )
        ET.SubElement(clip, "adjust-transform", anchor="0 0", position="0 0", scale="1 1")
        ET.SubElement(
            clip,
            "video",
            start=f"{entry['start']}/25s",
            duration=f"{entry['duration']}/25s",
            offset=f"{entry['start']}/25s",
            ref=added_assets[entry['filename']]
        )
    
    # Write the XML to a file
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"Fichier XML généré : {output_file}")

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
    extract_frames(video_path, output_folder)
    
    timecode_data = []
    for image_file in sorted(os.listdir(output_folder)):
        image_path = os.path.join(output_folder, image_file)
        extracted_text = extract_text_from_image(image_path)
        
        # Extraction naïve du timecode et du fichier (ajuster selon format réel)
        lines = extracted_text.split("\n")
        timecode = next((line.split("SRC TC: ")[1][:11] for line in lines if "SRC TC: " in line and ":" in line), "00:00:00:00")
        filename = next((line.split()[0] for line in lines if any(ext in line for ext in [".mov", ".MOV", ".mp4", ".MP4"])), "unknown.mov")
        filepath = os.path.join(output_folder, filename)
        
        # Utilisation directe des timecodes extraits
        start_tc = timecode
        end_tc = "00:00:10:00"  # Placeholder pour le timecode de fin
        timeline_in = start_tc  # Placeholder pour l'entrée dans la timeline
        timeline_out = end_tc   # Placeholder pour la sortie dans la timeline
        
        timecode_data.append({
            "filename": filename,
            "start_tc": start_tc,
            "end_tc": end_tc,
            "timeline_in": timeline_in,
            "timeline_out": timeline_out
        })
    
    generate_fcpxml(timecode_data, "output.fcpxml", video_path, output_folder)
    print("Fichier XML généré : output.fcpxml")
    
    generate_edl(timecode_data, "output.edl")
    print("Fichier EDL généré : output.edl")

if __name__ == "__main__":
    main("video.mp4")
