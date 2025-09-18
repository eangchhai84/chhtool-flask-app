from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
import uuid
import subprocess
import sys
import time
import random
import re

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ========================
# CHECK IF FFMPEG IS AVAILABLE
# ========================
def is_ffmpeg_installed():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False

FFMPEG_AVAILABLE = is_ffmpeg_installed()

if not FFMPEG_AVAILABLE:
    print("WARNING: ffmpeg not found. Video quality may be reduced.", file=sys.stderr)
else:
    print("SUCCESS: ffmpeg is available. Full quality downloads enabled.")

# ========================
# USER AGENTS FOR BROWSER SIMULATION
# ========================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Android 14; Mobile; rv:126.0) Gecko/126.0 Firefox/126.0',
]

# ========================
# ROUTES
# ========================

@app.route('/')
def index():
    return render_template('index.html')


# ✅ NEW: Get video info + available formats — now robust for ALL platforms
@app.route('/get_info', methods=['POST'])
def get_video_info():
    url = request.form.get('url')
    platform_hint = request.form.get('platform', '').lower()

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    # Normalize URLs
    url = url.replace('x.com', 'twitter.com').replace('instagr.am', 'instagram.com')
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Detect if it's a Facebook video (numeric ID or /watch/?v=...)
    is_facebook = any(pattern in url.lower() for pattern in [
        'facebook.com/watch',
        'facebook.com/reel',
        'fb.watch',
        'facebook.com/video',
        '/video/',
        '/reel/',
    ])

    # Extract numeric ID from common FB patterns
    fb_id_match = re.search(r'(?:v=|/reel/|/video/)(\d+)', url)
    fb_numeric_id = fb_id_match.group(1) if fb_id_match else None

    ydl_opts = {
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': False,
        'user_agent': random.choice(USER_AGENTS),
        'referer': 'https://www.facebook.com',
        'headers': {
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Upgrade-Insecure-Requests': '1',
        },
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if is_facebook and fb_numeric_id:
                # KEY FIX: Force yt-dlp to skip page parsing and extract directly
                ydl_opts.update({
                    'force_generic_extractor': True,
                    'extractor_args': {
                        'facebook': {
                            'skip_download': True,
                        }
                    },
                })

                # Try extracting using direct ID mode
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f'https://www.facebook.com/watch/?v={fb_numeric_id}', download=False)

                    title = info.get('title', 'Unknown Video').strip()
                    thumbnail = info.get('thumbnail', '')

                    formats = []
                    seen_format_ids = set()

                    for f in info.get('formats', []):
                        if f.get('format_id') in seen_format_ids:
                            continue
                        seen_format_ids.add(f.get('format_id'))

                        label_parts = []

                        height = f.get('height')
                        fps = f.get('fps')
                        ext = f.get('ext', '')
                        filesize = f.get('filesize')
                        vcodec = f.get('vcodec')
                        acodec = f.get('acodec')

                        if 'adaptive' in str(f.get('format_id', '')).lower() or 'dash' in str(f.get('format_id', '')).lower() or 'hls' in str(f.get('format_id', '')).lower():
                            if vcodec != 'none' and acodec != 'none':
                                label_parts.append("Adaptive (MP4/DASH)")
                            elif vcodec != 'none':
                                label_parts.append("Video Only")
                            elif acodec != 'none':
                                label_parts.append("Audio Only")

                        else:
                            if height is not None:
                                label_parts.append(f"{height}p")
                            if fps:
                                label_parts.append(f"{fps}fps")
                            if ext and ext != 'mp4':
                                label_parts.append(f"({ext})")

                            if filesize:
                                size_mb = round(filesize / (1024*1024), 1)
                                label_parts.append(f"{size_mb}MB")

                            if vcodec == 'none' and acodec == 'none':
                                continue
                            elif vcodec == 'none':
                                label_parts.insert(0, "Audio Only")
                                if acodec:
                                    label_parts.append(f"({acodec})")
                            elif acodec == 'none':
                                label_parts.insert(0, "Video Only")
                                if vcodec:
                                    label_parts.append(f"({vcodec})")
                            else:
                                label_parts.insert(0, "Video + Audio")
                                if vcodec:
                                    label_parts.append(f"({vcodec})")
                                if acodec:
                                    label_parts.append(f"({acodec})")

                        full_label = " ".join(label_parts).strip()
                        if not full_label:
                            full_label = f"Format ID: {f.get('format_id', 'unknown')}"[:50]

                        formats.append({
                            'format_id': f['format_id'],
                            'label': full_label,
                            'height': height,
                            'ext': ext,
                            'filesize': filesize,
                            'is_audio_only': vcodec == 'none',
                            'is_video_only': acodec == 'none',
                            'is_combined': vcodec != 'none' and acodec != 'none'
                        })

                    def sort_key(fmt):
                        h = fmt['height'] or 0
                        priority = 2 if fmt['is_combined'] else (1 if fmt['is_video_only'] else 0)
                        return (-h, -priority)

                    formats.sort(key=sort_key)

                    formats.insert(0, {
                        'format_id': 'best',
                        'label': 'Best Quality (Auto-Merge Video & Audio)',
                        'height': 9999,
                        'ext': 'mp4',
                        'filesize': None,
                        'is_audio_only': False,
                        'is_video_only': False,
                        'is_combined': True
                    })

                    formats.insert(1, {
                        'format_id': 'mp3',
                        'label': 'Convert to MP3 (Extract Audio Only)',
                        'height': 0,
                        'ext': 'mp3',
                        'filesize': None,
                        'is_audio_only': True,
                        'is_video_only': False,
                        'is_combined': False
                    })

                    return jsonify({
                        "title": title,
                        "thumbnail": thumbnail,
                        "url": url,
                        "formats": formats,
                        "has_formats": len(formats) > 0
                    })

            else:
                # For non-Facebook or failed direct extraction, try normal way
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    title = info.get('title', 'Unknown Video').strip()
                    thumbnail = info.get('thumbnail', '')

                    formats = []
                    seen_format_ids = set()

                    for f in info.get('formats', []):
                        if f.get('format_id') in seen_format_ids:
                            continue
                        seen_format_ids.add(f.get('format_id'))

                        label_parts = []

                        height = f.get('height')
                        fps = f.get('fps')
                        ext = f.get('ext', '')
                        filesize = f.get('filesize')
                        vcodec = f.get('vcodec')
                        acodec = f.get('acodec')

                        if 'adaptive' in str(f.get('format_id', '')).lower() or 'dash' in str(f.get('format_id', '')).lower() or 'hls' in str(f.get('format_id', '')).lower():
                            if vcodec != 'none' and acodec != 'none':
                                label_parts.append("Adaptive (MP4/DASH)")
                            elif vcodec != 'none':
                                label_parts.append("Video Only")
                            elif acodec != 'none':
                                label_parts.append("Audio Only")

                        else:
                            if height is not None:
                                label_parts.append(f"{height}p")
                            if fps:
                                label_parts.append(f"{fps}fps")
                            if ext and ext != 'mp4':
                                label_parts.append(f"({ext})")

                            if filesize:
                                size_mb = round(filesize / (1024*1024), 1)
                                label_parts.append(f"{size_mb}MB")

                            if vcodec == 'none' and acodec == 'none':
                                continue
                            elif vcodec == 'none':
                                label_parts.insert(0, "Audio Only")
                                if acodec:
                                    label_parts.append(f"({acodec})")
                            elif acodec == 'none':
                                label_parts.insert(0, "Video Only")
                                if vcodec:
                                    label_parts.append(f"({vcodec})")
                            else:
                                label_parts.insert(0, "Video + Audio")
                                if vcodec:
                                    label_parts.append(f"({vcodec})")
                                if acodec:
                                    label_parts.append(f"({acodec})")

                        full_label = " ".join(label_parts).strip()
                        if not full_label:
                            full_label = f"Format ID: {f.get('format_id', 'unknown')}"[:50]

                        formats.append({
                            'format_id': f['format_id'],
                            'label': full_label,
                            'height': height,
                            'ext': ext,
                            'filesize': filesize,
                            'is_audio_only': vcodec == 'none',
                            'is_video_only': acodec == 'none',
                            'is_combined': vcodec != 'none' and acodec != 'none'
                        })

                    def sort_key(fmt):
                        h = fmt['height'] or 0
                        priority = 2 if fmt['is_combined'] else (1 if fmt['is_video_only'] else 0)
                        return (-h, -priority)

                    formats.sort(key=sort_key)

                    formats.insert(0, {
                        'format_id': 'best',
                        'label': 'Best Quality (Auto-Merge Video & Audio)',
                        'height': 9999,
                        'ext': 'mp4',
                        'filesize': None,
                        'is_audio_only': False,
                        'is_video_only': False,
                        'is_combined': True
                    })

                    formats.insert(1, {
                        'format_id': 'mp3',
                        'label': 'Convert to MP3 (Extract Audio Only)',
                        'height': 0,
                        'ext': 'mp3',
                        'filesize': None,
                        'is_audio_only': True,
                        'is_video_only': False,
                        'is_combined': False
                    })

                    return jsonify({
                        "title": title,
                        "thumbnail": thumbnail,
                        "url": url,
                        "formats": formats,
                        "has_formats": len(formats) > 0
                    })

        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e).lower()
            if attempt < max_retries - 1:
                time.sleep(3 + random.randint(0, 2))
                continue
            else:
                # SMART ERROR HANDLING — NO EMOJIS, PLAIN TEXT ONLY
                if 'cannot parse data' in err_msg or 'cannot extract' in err_msg:
                    msg = "Facebook video extraction failed. Try these steps:\n\n1. Open this link in your browser: \n   " + url + "\n2. Log in to Facebook if prompted\n3. Refresh the page\n4. Copy the URL again from the address bar\n5. Disable ad blockers (uBlock Origin, Privacy Badger)\n6. Try again here"
                elif 'privacy' in err_msg or 'login' in err_msg or 'authentication' in err_msg:
                    msg = "This video requires login. Please open it in a browser first, then try again."
                elif 'instagram' in err_msg or '無法訪問' in err_msg or '很抱歉' in err_msg or 'blocked' in err_msg:
                    msg = "Instagram has blocked access. Try these steps:\n\n1. Open this link in your browser\n2. Log in if prompted\n3. Refresh and copy the URL again\n4. Try disabling ad blockers or using a VPN"
                elif 'x.com' in err_msg or 'twitter' in err_msg:
                    msg = "Twitter/X may block automated access. Try these steps:\n\n1. Disable browser extensions (uBlock Origin, Privacy Badger)\n2. Open an incognito/private window\n3. Visit the link manually\n4. Copy the URL from the address bar\n5. Try again here"
                elif 'geolocation' in err_msg or 'geo' in err_msg:
                    msg = "This video is geo-restricted. Try using a VPN located in the same region."
                elif 'not found' in err_msg or 'deleted' in err_msg or 'removed' in err_msg:
                    msg = "The video was deleted or the link is broken."
                elif '403' in err_msg or 'forbidden' in err_msg:
                    msg = "Access forbidden. The content may require authentication or is temporarily unavailable."
                elif '404' in err_msg:
                    msg = "Page not found. The video may have been moved or removed."
                else:
                    msg = "Failed to fetch video information. The link may be invalid or unsupported."

                return jsonify({"error": msg}), 400

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3 + random.randint(0, 2))
                continue
            else:
                return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


# ✅ Download route — handles MP3, best, custom format
@app.route('/download', methods=['POST'])
def download_video():
    url = request.form.get('url')
    format_type = request.form.get('format', 'mp4')
    format_id = request.form.get('format_id', None)

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    url = url.replace('x.com', 'twitter.com').replace('instagr.am', 'instagram.com')
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{file_id}.%(ext)s")

    ydl_opts = {
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'ignore_no_formats_error': False,
        'user_agent': random.choice(USER_AGENTS),
        'referer': 'https://www.facebook.com',
        'headers': {
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Upgrade-Insecure-Requests': '1',
        },
    }

    try:
        if format_type == "mp3":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        elif format_type == "best":
            if FFMPEG_AVAILABLE:
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                })
            else:
                ydl_opts.update({
                    'format': 'best[ext=mp4]/best',
                })
        elif format_type == "custom" and format_id:
            ydl_opts.update({
                'format': format_id,
            })
        else:
            if FFMPEG_AVAILABLE:
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                })
            else:
                ydl_opts.update({
                    'format': 'best[ext=mp4]/best',
                })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if format_type == "mp3":
                mp3_filename = os.path.splitext(filename)[0] + ".mp3"
                if os.path.exists(mp3_filename):
                    filename = mp3_filename
                else:
                    return jsonify({"error": "Failed to convert to MP3. Is ffmpeg installed?"}), 500

        response = send_file(
            filename,
            as_attachment=True,
            download_name=os.path.basename(filename),
            mimetype='application/octet-stream'
        )

        return response

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower():
            error_msg += " -> Please install ffmpeg: https://ffmpeg.org/download"
        return jsonify({"error": error_msg}), 500

    except Exception as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower():
            error_msg += " -> Please install ffmpeg: https://ffmpeg.org/download"
        return jsonify({"error": error_msg}), 500


if __name__ == '__main__':
    print("="*70)
    if FFMPEG_AVAILABLE:
        print("[OK] FULL QUALITY MODE - ffmpeg is available")
        print("   Supported: HEVC, AV1, VP9, ProRes, Vulkan decoding, AAC, MP3, and more")
    else:
        print("[!] LOW QUALITY MODE - Install ffmpeg for best results")
        print("   Install: https://ffmpeg.org/download")
    print("="*70 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5000)