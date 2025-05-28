import os
import sys
import subprocess

def extract_frames(video_path, output_folder):
    if not os.path.exists(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        sys.exit(1)
    
    if not shutil.which("ffmpeg"):
        print("Error: 'ffmpeg' is not installed or not in PATH.")
        sys.exit(1)
    
    os.makedirs(output_folder, exist_ok=True)
    command = ["ffmpeg", "-i", video_path, os.path.join(output_folder, "frame_%04d.png")]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        print("Error: Failed to execute the command. Ensure 'ffmpeg' is installed.")
        sys.exit(1)

def main(video_path):
    output_folder = "frames"
    extract_frames(video_path, output_folder)
    # ...existing code...

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <video_path>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    main(video_path)
