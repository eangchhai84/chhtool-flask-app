import http.client
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import urllib.parse
import json
import requests
import os
from datetime import datetime

def fetch_video_data():
    youtube_url = url_entry.get().strip()
    if not youtube_url:
        messagebox.showerror("Error", "Please enter a YouTube URL")
        return

    try:
        # Prepare the API request
        conn = http.client.HTTPSConnection("youtube-quick-video-downloader-free-api-downlaod-all-video.p.rapidapi.com")
        headers = {
            'x-rapidapi-key': "58a5d71ff2mshf540983a855b83dp175cb9jsna10838d4b972",
            'x-rapidapi-host': "youtube-quick-video-downloader-free-api-downlaod-all-video.p.rapidapi.com"
        }
        encoded_url = urllib.parse.quote(youtube_url)
        conn.request("GET", f"/videodownload.php?url={encoded_url}", headers=headers)

        # Get and decode response
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()

        # Display raw response
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, data)

        # Parse JSON and populate quality options
        try:
            json_data = json.loads(data)
            quality_combobox['values'] = []  # Clear previous options
            quality_var.set("")  # Clear selection
            download_button.config(state=tk.DISABLED)
            available_streams.clear()

            # Check if json_data is a list and extract the first item (assuming it's the main response)
            if isinstance(json_data, list) and json_data:
                streams = json_data[0].get('urls', [])
            else:
                streams = json_data.get('urls', [])

            # Extract streams with direct URLs (prioritize bundled streams with audio)
            for stream in streams:
                if stream.get('url', '').startswith('https://') and not stream.get('audio', False):
                    if stream.get('isBundle', False):  # Prioritize bundled streams (video + audio)
                        quality = f"{stream.get('name', stream['extension'])} {stream.get('subName', '')} (itag={stream['itag']})"
                        available_streams[quality] = {
                            'url': stream['url'],
                            'extension': stream['extension'],
                            'is_bundle': stream.get('isBundle', False)
                        }

            if available_streams:
                quality_combobox['values'] = list(available_streams.keys())
                quality_var.set(quality_combobox['values'][0])  # Select first quality
                download_button.config(state=tk.NORMAL)
                result_text.insert(tk.END, "\n\nSelect a quality to download.")
            else:
                result_text.insert(tk.END, "\n\nNo bundled video streams found. Try a different URL.")
                download_button.config(state=tk.DISABLED)

        except json.JSONDecodeError:
            result_text.insert(tk.END, "\n\nAPI response is not valid JSON. Cannot download.")
            download_button.config(state=tk.DISABLED)

    except Exception as e:
        messagebox.showerror("Error", f"API request failed: {str(e)}")
        download_button.config(state=tk.DISABLED)

def download_with_api():
    selected_quality = quality_var.get()
    if not selected_quality:
        messagebox.showerror("Error", "Please select a video quality")
        return

    stream = available_streams.get(selected_quality)
    if not stream:
        messagebox.showerror("Error", "Invalid stream selected")
        return

    try:
        # Ask user where to save the video
        file_type_name = stream.get('name', stream['extension']).capitalize()
        save_path = filedialog.asksaveasfilename(
            defaultextension=f".{stream['extension']}",
            filetypes=[(f"{file_type_name} files", f"*.{stream['extension']}"), ("All files", "*.*")],
            title="Save Video As",
            initialfile=f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        if not save_path:
            return

        # Download the video
        status_label.config(text="Downloading...")
        root.update()
        response = requests.get(stream['url'], stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            messagebox.showinfo("Success", f"Video downloaded to {save_path}")
            status_label.config(text="Download complete!")
        else:
            messagebox.showerror("Error", f"Download failed: HTTP {response.status_code}")
            status_label.config(text="Download failed.")

    except Exception as e:
        messagebox.showerror("Error", f"Download failed: {str(e)}")
        status_label.config(text="Download failed.")

# Create the main Tkinter window
root = tk.Tk()
root.title("YouTube Video Downloader")
root.geometry("600x450")
root.resizable(False, False)

# Store available streams
available_streams = {}

# Create and place widgets
tk.Label(root, text="YouTube Video Downloader", font=("Arial", 14, "bold")).pack(pady=10)
tk.Label(root, text="Enter YouTube URL:").pack()
url_entry = tk.Entry(root, width=50)
url_entry.pack(pady=5)

fetch_button = tk.Button(root, text="Fetch Video Data", command=fetch_video_data)
fetch_button.pack(pady=5)

tk.Label(root, text="Select Quality:").pack()
quality_var = tk.StringVar()
quality_combobox = ttk.Combobox(root, textvariable=quality_var, state="readonly", width=47)
quality_combobox.pack(pady=5)

download_button = tk.Button(root, text="Download Video", state=tk.DISABLED, command=download_with_api)
download_button.pack(pady=5)

tk.Label(root, text="API Response:").pack()
result_text = tk.Text(root, height=10, width=60)
result_text.pack(pady=10)

status_label = tk.Label(root, text="Ready", font=("Arial", 10))
status_label.pack(pady=5)

# Start the Tkinter event loop
root.mainloop()