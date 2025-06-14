import streamlit as st
import yt_dlp
import json
import datetime

# --- Streamlit UI Configuration (MUST BE THE VERY FIRST STREAMLIT COMMAND) ---
st.set_page_config(
    page_title="Streamlit YouTube Direct Link Extractor (yt-dlp)",
    page_icon="🔗",
    layout="wide"
)

# --- Helper Function for Extracting YouTube Stream Links using yt-dlp ---
def get_yt_dlp_stream_info(url: str) -> tuple[str, list[dict]]:
    """
    Attempts to get all available stream links from a YouTube video using yt-dlp.
    Returns (video_title, list_of_stream_details) upon success,
    or raises an exception on failure.
    """
    ydl_opts = {
        'format': 'bestvideo*+bestaudio*/best', # Get all video and audio streams
        'extract_flat': True, # Get all available formats without downloading (faster)
        'force_generic_extractor': True, # Important for some URLs
        'simulate': True, # Don't download, just list info
        'dump_single_json': True, # Output info as a single JSON object
        'quiet': True, # Suppress console output from yt-dlp
        'skip_download': True, # Don't actually download files
        'no_warnings': True, # Suppress warnings from yt-dlp
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            video_title = info_dict.get('title', 'Unknown Title')
            
            stream_details = []
            if 'formats' in info_dict:
                for f in info_dict['formats']:
                    # Skip streams without a direct URL (e.g., DASH manifests themselves)
                    if not f.get('url'):
                        continue

                    stream_type = "unknown"
                    resolution = "N/A"
                    vcodec = None
                    acodec = None
                    fps = "N/A"
                    
                    # Determine stream type
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
                        resolution = "N/A" # No resolution for audio
                        vcodec = None
                        acodec = f.get('acodec')
                        fps = "N/A" # No fps for audio

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
                        "mime_type": f.get('ext'), # yt-dlp uses 'ext' for file extension
                        "filesize_mb": filesize_mb,
                        "url": f.get('url') # The direct download URL
                    })
            
            # Filter out any 'unknown' types if they somehow slip through or are uninteresting
            stream_details = [s for s in stream_details if s["type"] != "unknown"]

            # Sort by type (progressive first, then video-only, then audio-only, then resolution)
            def sort_key(s):
                type_order = {"progressive (video+audio)": 1, "adaptive (audio-only)": 2, "adaptive (video-only)": 3}
                resolution_val = 0
                if s["resolution"] != "N/A" and isinstance(s["resolution"], str) and s["resolution"].endswith('p'):
                    try:
                        resolution_val = int(s["resolution"][:-1])
                    except ValueError:
                        pass
                
                return (type_order.get(s["type"], 99), -resolution_val) # Negative resolution for descending sort

            stream_details.sort(key=sort_key)


        if not stream_details:
            raise ValueError("No stream links found for this video.")

        return video_title, stream_details

    except yt_dlp.utils.DownloadError as e:
        # Check if the error indicates video unavailability or invalid URL
        if "Video unavailable" in str(e) or "Private video" in str(e):
            raise ValueError("The YouTube video is unavailable, private, or invalid.")
        elif "No video formats found" in str(e):
            raise ValueError("No valid video formats found for this URL. Please check the URL.")
        else:
            raise Exception(f"An yt-dlp error occurred: {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")

# --- No cleanup function needed as no files are downloaded/stored ---

# --- Check for 'url' parameter in query string for "API" mode ---
query_url = st.query_params.get("url")

# Determine if we are in "API" mode (URL provided in query params)
api_mode = bool(query_url)

if api_mode:
    # --- "API" Mode: Direct JSON Response ---
    video_url = query_url
    
    response_status = "error"
    response_message = "An unknown error occurred."
    video_title = "N/A"
    available_streams = []

    try:
        # Get all stream links
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
        "available_streams": available_streams, # List of dictionaries with stream details
        "message": response_message,
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    st.json(json_response)
    st.stop() # Stop further execution to only show the JSON

else:
    # --- Interactive UI Mode ---
    st.title("🔗 YouTube Direct Link Extractor (Powered by yt-dlp)")
    st.markdown("Enter a YouTube URL to get a list of **all** direct download links, including combined video+audio streams and separate video-only/audio-only streams.")
    st.markdown("---")

    video_url = st.text_input(
        "🔗 Enter YouTube Video URL:",
        placeholder="e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    if st.button("🔽 Get All Direct Links", use_container_width=True):
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

                    # Display links in a table for better readability
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

    st.markdown("---")
    st.markdown("### Important Notes:")
    st.markdown("""
    -   **No Server Storage:** This app does **not** download or store any video files on its server. It only extracts the direct links provided by YouTube's content delivery network via `yt-dlp`.
    -   **Adaptive Streams:** For higher quality videos, YouTube often provides video and audio as separate streams. You'll need to combine them post-download (e.g., using a tool like `ffmpeg`).
    -   **Link Expiration:** The direct URLs provided by YouTube are typically time-limited and will expire after a certain period (e.g., a few hours). You need to download the video using the link within that timeframe.
    -   **Browser Behavior:** Clicking a direct link will usually either start a download or play the content directly in your browser, depending on your browser's settings.
    -   **API Mode (Query Parameters):** If you provide `?url=YOUR_YOUTUBE_URL` in the browser's address bar, the app will attempt to process it directly and return a JSON response containing *all* available links.
    """)
