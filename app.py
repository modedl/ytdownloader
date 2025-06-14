import streamlit as st
import yt_dlp
import json
import datetime
import os

# --- Streamlit UI Configuration (MUST BE THE VERY FIRST STREAMLIT COMMAND) ---
st.set_page_config(
    page_title="Streamlit YouTube Direct Link & Downloader (yt-dlp)",
    page_icon="🔗",
    layout="wide"
)

# --- Helper Function for Extracting YouTube Stream Links using yt-dlp ---
# (This function is the same as before, for listing links)
def get_yt_dlp_stream_info(url: str) -> tuple[str, list[dict]]:
    """
    Attempts to get all available stream links from a YouTube video using yt-dlp.
    Returns (video_title, list_of_stream_details) upon success,
    or raises an exception on failure.
    """
    ydl_opts = {
        'format': 'bestvideo*+bestaudio*/best', # Get all video and audio streams for info
        'extract_flat': True,
        'force_generic_extractor': True,
        'simulate': True, # Only simulate, do not download
        'dump_single_json': True,
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            video_title = info_dict.get('title', 'Unknown Title')
            
            stream_details = []
            if 'formats' in info_dict:
                for f in info_dict['formats']:
                    if not f.get('url'): continue # Skip streams without a direct URL

                    stream_type = "unknown"
                    resolution = "N/A"
                    vcodec = None
                    acodec = None
                    fps = "N/A"
                    
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        stream_type = "progressive (video+audio)"
                        resolution = f.get('resolution') or f.get('height')
                        vcodec = f.get('vcodec')
                        acodec = f.get('acodec')
                        fps = f.get('fps', 'N/A')
                    elif f.get('vcodec') != 'none':
                        stream_type = "adaptive (video-only)"
                        resolution = f.get('resolution') or f.get('height')
                        vcodec = f.get('vcodec')
                        acodec = None
                        fps = f.get('fps', 'N/A')
                    elif f.get('acodec') != 'none':
                        stream_type = "adaptive (audio-only)"
                        resolution = "N/A"
                        vcodec = None
                        acodec = f.get('acodec')
                        fps = "N/A"

                    filesize_mb = None
                    if f.get('filesize'):
                        filesize_mb = round(f['filesize'] / (1024 * 1024), 2)
                    elif f.get('filesize_approx'):
                        filesize_mb = round(f['filesize_approx'] / (1024 * 1024), 2)

                    stream_details.append({
                        "itag": f.get('format_id'),
                        "type": stream_type,
                        "resolution": resolution,
                        "fps": fps,
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "mime_type": f.get('ext'),
                        "filesize_mb": filesize_mb,
                        "url": f.get('url')
                    })
            
            stream_details = [s for s in stream_details if s["type"] != "unknown"]
            def sort_key(s):
                type_order = {"progressive (video+audio)": 1, "adaptive (audio-only)": 2, "adaptive (video-only)": 3}
                resolution_val = 0
                if s["resolution"] != "N/A" and isinstance(s["resolution"], str) and s["resolution"].endswith('p'):
                    try: resolution_val = int(s["resolution"][:-1])
                    except ValueError: pass
                return (type_order.get(s["type"], 99), -resolution_val)
            stream_details.sort(key=sort_key)

        if not stream_details:
            raise ValueError("No stream links found for this video.")

        return video_title, stream_details

    except yt_dlp.utils.DownloadError as e:
        if "Video unavailable" in str(e) or "Private video" in str(e):
            raise ValueError("The YouTube video is unavailable, private, or invalid.")
        elif "No video formats found" in str(e):
            raise ValueError("No valid video formats found for this URL. Please check the URL.")
        else:
            raise Exception(f"An yt-dlp error occurred: {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")


# --- Function to Download the Best Combined Video ---
def download_best_combined_video(url: str, output_path: str = "downloads"):
    """
    Downloads the best available video and audio, combining them if necessary.
    Requires FFmpeg to be installed on the system.
    Returns the path to the downloaded file.
    """
    # Ensure the download directory exists
    os.makedirs(output_path, exist_ok=True)

    # yt-dlp options for downloading and merging
    ydl_opts = {
        'format': 'bestvideo*+bestaudio*/best', # Select best adaptive video and audio, or best progressive
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'), # Output file path and name
        'merge_output_format': 'mp4', # Merge into MP4 format (requires ffmpeg)
        'postprocessors': [{ # This is crucial for audio extraction
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True, # Suppress yt-dlp console output
        'no_warnings': True, # Suppress warnings
        'noplaylist': True, # Ensure only single video is downloaded, not a playlist if URL is a playlist
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True) # download=True to actually download
            downloaded_filepath = ydl.prepare_filename(info_dict) # Get the final filename
            return downloaded_filepath

    except yt_dlp.utils.DownloadError as e:
        if "No video formats found" in str(e):
            raise ValueError("No suitable video formats found for download. This might be a private video or geo-restricted.")
        elif "ffmpeg not found" in str(e):
            raise Exception("FFmpeg is required for merging video and audio, but it was not found. Please install FFmpeg and ensure it's in your system's PATH.")
        else:
            raise Exception(f"Failed to download video: {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred during download: {e}")


# --- Check for 'url' parameter in query string for "API" mode ---
query_url = st.query_params.get("url")

# Determine if we are in "API" mode (URL provided in query params)
api_mode = bool(query_url)

if api_mode:
    # --- "API" Mode: Direct JSON Response (Only for stream info, not download) ---
    video_url = query_url
    
    response_status = "error"
    response_message = "An unknown error occurred."
    video_title = "N/A"
    available_streams = []

    try:
        # Get all stream links (no download in API mode)
        video_title, available_streams = get_yt_dlp_stream_info(video_url)
        
        response_status = "success"
        response_message = "Successfully retrieved all available direct download links. Note: Adaptive streams (video-only or audio-only) require separate downloads and combining them (e.g., with ffmpeg) to create a full video file. Links are often time-limited by YouTube."

    except ValueError as ve:
        response_message = f"Error: {ve}"
    except Exception as e:
        response_message = f"An unexpected error occurred: {e}"

    json_response = {
        "status": response_status,
        "video_title": video_title,
        "available_streams": available_streams,
        "message": response_message,
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    st.json(json_response)
    st.stop() # Stop further execution to only show the JSON

else:
    # --- Interactive UI Mode ---
    st.title("🔗 YouTube Direct Link & Downloader (Powered by yt-dlp)")
    st.markdown("Enter a YouTube URL to get a list of **all** direct download links or to download the best combined video+audio file.")
    st.markdown("---")

    video_url = st.text_input(
        "🔗 Enter YouTube Video URL:",
        placeholder="e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔽 List All Direct Links", use_container_width=True):
            if video_url:
                st.divider()
                st.subheader("Extracted Direct Links:")
                
                with st.spinner("Retrieving video information and direct links..."):
                    try:
                        video_title, streams = get_yt_dlp_stream_info(video_url)
                        st.success(f"Links found for: **{video_title}**")
                        st.info("""
                            **Understanding the Links:**
                            -   **Progressive (video+audio):** These streams contain both video and audio and can be played directly.
                            -   **Adaptive (video-only):** These streams contain *only* video. To get a full video, you'll need to download a video-only stream AND an audio-only stream, then combine them using a tool like `ffmpeg`.
                            -   **Adaptive (audio-only):** These streams contain *only* audio. Useful for extracting soundtracks or combining with video-only streams.
                            -   **Link Expiration:** All direct URLs provided by YouTube are typically time-limited and may expire after a few hours.
                        """)

                        st.dataframe(
                            streams,
                            column_order=[
                                "type", "resolution", "fps", "vcodec", "acodec", "mime_type", "filesize_mb", "url", "itag"
                            ],
                            hide_index=True,
                            use_container_width=True
                        )

                    except ValueError as ve:
                        st.error(f"Error: {ve}")
                    except Exception as e:
                        st.error(f"An unhandled error occurred: {e}")
            else:
                st.warning("Please enter a YouTube video URL.")

    with col2:
        if st.button("💾 Download Best Video (Server-side)", use_container_width=True):
            if video_url:
                st.divider()
                st.subheader("Downloading Video...")
                
                with st.spinner("Downloading and combining best quality video and audio... This may take a while for large files."):
                    try:
                        # Ensure 'downloads' directory exists if running locally
                        if not os.path.exists("downloads"):
                            os.makedirs("downloads")

                        downloaded_file = download_best_combined_video(video_url, output_path="downloads")
                        st.success(f"Video downloaded successfully to: `{downloaded_file}` (on the server).")
                        st.info("Note: This feature downloads the video to the server where this Streamlit app is running. It does not initiate a direct download to your browser. You would need server access to retrieve the file.")

                    except ValueError as ve:
                        st.error(f"Download Error: {ve}")
                    except Exception as e:
                        st.error(f"An error occurred during download: {e}")
            else:
                st.warning("Please enter a YouTube video URL to download.")

    st.markdown("---")
    st.markdown("### Important Notes:")
    st.markdown("""
    -   **`ffmpeg` Requirement:** For the "Download Best Video (Server-side)" option to work and combine separate video and audio streams, **FFmpeg must be installed** on the system where this Streamlit application is running. Most cloud platforms (like Streamlit Cloud) have it pre-installed.
    -   **Server-Side Download:** The "Download Best Video (Server-side)" button downloads the video to the server where the Streamlit app is hosted. It does **not** trigger a download directly to your browser. If you need the file, you would typically need SSH/FTP access to the server or integrate a file serving mechanism (which is more complex for a basic Streamlit app).
    -   **No Server Storage (Default):** This app does **not** permanently store downloaded video files. Any files downloaded via the "Server-side" option would exist only temporarily while the app instance is active.
    -   **Adaptive Streams:** For higher quality videos, YouTube often provides video and audio as separate streams. `yt-dlp` automatically handles combining these if `ffmpeg` is available.
    -   **Link Expiration:** The direct URLs displayed by the "List All Direct Links" button are typically time-limited and will expire after a certain period (e.g., a few hours). You need to download the video using the link within that timeframe.
    -   **API Mode (Query Parameters):** If you provide `?url=YOUR_YOUTUBE_URL` in the browser's address bar, the app will attempt to process it directly and return a JSON response containing *all* available links (no download in this mode).
    """)
