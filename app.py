from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import threading
import time

app = Flask(__name__)
CORS(app)

# Configuration
DOWNLOAD_FOLDER = tempfile.gettempdir()
MAX_FILE_AGE = 3600  # 1 hour

def cleanup_old_files():
    """Remove old downloaded files"""
    while True:
        try:
            now = time.time()
            for filename in os.listdir(DOWNLOAD_FOLDER):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(filepath):
                    if now - os.path.getmtime(filepath) > MAX_FILE_AGE:
                        os.remove(filepath)
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(600)  # Run every 10 minutes

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'service': 'VidGet Backend API',
        'version': '1.0',
        'endpoints': {
            'info': '/api/get-info',
            'stream': '/api/get-stream-url',
            'download': '/api/download'
        }
    })

@app.route('/api/get-info', methods=['POST'])
def get_info():
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return jsonify({
                'success': True,
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'platform': info.get('extractor', 'Unknown'),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-stream-url', methods=['POST'])
def get_stream_url():
    try:
        url = request.form.get('url')
        quality = request.form.get('quality', '480')
        
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400

        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get('url', '')
            
            return jsonify({
                'success': True,
                'stream_url': stream_url
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        url = request.form.get('url')
        quality = request.form.get('quality', 'best')
        format_type = request.form.get('format_type', 'video')
        
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'}), 400

        # Generate unique filename
        timestamp = int(time.time())
        
        if format_type == 'audio':
            output_template = os.path.join(DOWNLOAD_FOLDER, f'audio_{timestamp}.%(ext)s')
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            expected_file = os.path.join(DOWNLOAD_FOLDER, f'audio_{timestamp}.mp3')
        else:
            output_template = os.path.join(DOWNLOAD_FOLDER, f'video_{timestamp}.%(ext)s')
            
            if quality == 'best':
                format_string = 'bestvideo+bestaudio/best'
            else:
                format_string = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best'
            
            ydl_opts = {
                'format': format_string,
                'outtmpl': output_template,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            }
            expected_file = os.path.join(DOWNLOAD_FOLDER, f'video_{timestamp}.mp4')

        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the downloaded file
        downloaded_file = None
        for file in os.listdir(DOWNLOAD_FOLDER):
            if file.startswith(f'{"audio" if format_type == "audio" else "video"}_{timestamp}'):
                downloaded_file = os.path.join(DOWNLOAD_FOLDER, file)
                break

        if not downloaded_file or not os.path.exists(downloaded_file):
            return jsonify({'success': False, 'error': 'Download failed'}), 500

        # Send file and schedule deletion
        def delete_file():
            time.sleep(60)  # Wait 1 minute
            try:
                if os.path.exists(downloaded_file):
                    os.remove(downloaded_file)
            except:
                pass

        threading.Thread(target=delete_file, daemon=True).start()

        return send_file(
            downloaded_file,
            as_attachment=True,
            download_name=f'vidget_download.{"mp3" if format_type == "audio" else "mp4"}'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
