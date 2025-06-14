import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
import json
import datetime

# --- Streamlit UI Configuration (MUST BE THE VERY FIRST STREAMLIT COMMAND) ---
st.set_page_config(
    page_title="Streamlit YouTube Direct Link Extractor (All Streams)",
    page_icon="🔗",
    layout="wide"
)

# --- Helper Function for Extracting YouTube Stream Links ---
def get_youtube_stream_links(url: str) -> tuple[str, list[dict]]:
    """
    Attempts to get all available progressive and adaptive stream links from a YouTube video.
    Returns (video_title, list_of_stream_details) upon success,
    or raises an exception on failure.
    """
    try:
        yt = YouTube(url)
        
        video_title = yt.title
        
        # Get ALL streams (both progressive and adaptive)
        # Order by resolution descending, then by itag (a way to ensure consistent order)
        all_streams = yt.streams.order_by('resolution').desc().order_by('itag')
        
        stream_details = []
        for s in all_streams:
            if s.url: # Ensure the stream has a direct URL
                stream_type = "progressive (video+audio)" if s.is_progressive else \
                              ("adaptive (video-only)" if s.type == "video" else "adaptive (audio-only)")
                
                stream_details.append({
                    "type": stream_type,
                    "resolution": s.resolution if s.type == "video" else "N/A", # Only video streams have resolution
                    "fps": s.fps if s.type == "video" else "N/A",
                    "vcodec": s.video_codec, # Video codec
                    "acodec": s.audio_codec, # Audio codec
                    "mime_type": s.mime_type,
                    "filesize_mb": round(s.filesize / (1024 * 1024), 2) if s.filesize else None,
                    "itag": s.itag,
                    "url": s.url # This is the direct download URL
                })
        
        if not stream_details:
            raise ValueError("No stream links found for this video.")

        return video_title, stream_details

    except VideoUnavailable:
        raise ValueError("The YouTube video is unavailable or private.")
    except RegexMatchError:
        raise ValueError("Invalid YouTube URL format. Please check the URL.")
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
        video_title, available_streams = get_youtube_stream_links(video_url)
        
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
    st.title("🔗 YouTube Direct Link Extractor (All Streams)")
    st.markdown("Enter a YouTube URL to get a list of **all** direct download links, including combined video+audio streams and separate video-only/audio-only streams.")
    st.markdown("---")

    video_url = st.text_input(
        "🔗 Enter YouTube Video URL:",
        placeholder="e.g., https://www.youtube.com/channel/UCV8e2g4IWQqK71bbzGDEI4Q5"
    )

    if st.button("🔽 Get All Direct Links", use_container_width=True):
        if video_url:
            st.divider()
            st.subheader("Extracted Direct Links:")
            
            with st.spinner("Retrieving video information and direct links..."):
                try:
                    video_title, streams = get_youtube_stream_links(video_url)
                    st.success(f"Links found for: **{video_title}**")
                    st.info("""
                        **Understanding the Links:**
                        - **Progressive (video+audio):** These streams contain both video and audio and can be played directly.
                        - **Adaptive (video-only/audio-only):** These streams contain *only* video or *only* audio. To get a full video, you'll need to download a video-only stream AND an audio-only stream, then combine them using a tool like `ffmpeg`.
                        - **Link Expiration:** All direct URLs provided by YouTube are typically time-limited and may expire after a few hours.
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
    -   **No Server Storage:** This app does **not** download or store any video files on its server. It only extracts the direct links provided by YouTube's content delivery network via `pytubefix`.
    -   **Adaptive Streams:** For higher quality videos, YouTube often provides video and audio as separate streams. You'll need to combine them post-download.
    -   **Link Expiration:** The direct URLs provided by YouTube are typically time-limited and will expire after a certain period (e.g., a few hours). You need to download the video using the link within that timeframe.
    -   **Browser Behavior:** Clicking a direct `.mp4` link will usually either start a download or play the video directly in your browser, depending on your browser's settings.
    -   **API Mode (Query Parameters):** If you provide `?url=YOUR_YOUTUBE_URL` in the browser's address bar, the app will attempt to process it directly and return a JSON response containing *all* available links.
    """)
