import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
import os
import uuid
import json
import datetime
import time

# --- Determine layout based on potential API mode BEFORE st.set_page_config ---
# Check for 'url' parameter early to decide layout
# Note: st.query_params can be used before set_page_config
# However, if you need the *default* page_config to be dynamic based on query params,
# you must access query_params *before* calling set_page_config.
# Sticking to the common pattern of getting query_params after set_page_config,
# but passing a variable to layout.

# Initialize a default layout
page_layout = "centered"

# You cannot reliably get query_params before st.set_page_config,
# because the script needs to run a bit for Streamlit's runtime to initialize.
# The most robust way to handle this with a single set_page_config is to
# accept a fixed layout or set a variable early and use it.
# Let's assume for now that if a 'url' is present, we want 'wide'.

# A common pattern is to fetch query_params *after* set_page_config,
# then use st.stop() for API mode. However, if the *layout* needs to change,
# we need a trickier approach or accept that layout won't change on the first run.

# Let's simplify and keep the layout fixed or determine it based on initial conditions
# that don't depend on a full Streamlit rendering pass.
# For truly dynamic layout, you often restart the app or rely on user interaction.

# --- Streamlit UI Configuration (MUST BE THE VERY FIRST STREAMLIT COMMAND) ---
# We'll set a default layout here. If you absolutely need to change layout
# based on query params, it's more complex and might require a fresh script run
# (e.g., redirecting the user or having separate scripts).
# For now, let's pick one, or keep 'centered' as the default.
# The 'wide' layout is more appropriate for pure JSON.
# Let's assume for this "API" version, 'wide' is better by default.
st.set_page_config(
    page_title="Streamlit 'API' Endpoint (Simulated) with Auto-Cleanup",
    page_icon="🤖",
    layout="wide" # Set a single, consistent layout here. 'wide' is good for JSON.
)


# --- Configuration ---
DOWNLOAD_DIR = "temp_downloads" # Folder to store temporary downloads
CLEANUP_DELAY_MINUTES = 5 # Files older than this will be deleted

# Ensure the temporary download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- Helper Function for Downloading Videos ---
def download_youtube_video_for_streamlit(url: str, resolution: str) -> tuple[str, str, str]:
    """
    Attempts to download a YouTube video to a temporary location.
    Returns (file_path, video_title, actual_resolution_downloaded) upon success,
    or raises an exception on failure.
    """
    try:
        yt = YouTube(url)
        
        # Filter for progressive streams (video and audio combined)
        progressive_streams = yt.streams.filter(progressive=True).order_by('resolution').desc()

        target_stream = None
        for s in progressive_streams:
            if s.resolution == resolution:
                target_stream = s
                break
            
        # Fallback: if exact resolution isn't found, get the highest available progressive stream
        if not target_stream:
            target_stream = progressive_streams.first()
            
            if not target_stream:
                raise ValueError("No progressive streams found for this video at any resolution.")

        # Generate a unique filename including a timestamp for cleanup purposes
        unique_id = uuid.uuid4().hex[:8] 
        safe_title = "".join([c for c in yt.title if c.isalnum() or c in (' ', '.', '_')]).strip()
        safe_title = safe_title.replace(' ', '_')[:50] # Truncate title for shorter filenames
        
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S") # Current timestamp
        
        file_name = f"{safe_title}_{target_stream.resolution}_{timestamp_str}_{unique_id}.mp4"
        file_path = os.path.join(DOWNLOAD_DIR, file_name)

        # Download the video if it doesn't already exist in the temporary folder
        if not os.path.exists(file_path):
            target_stream.download(output_path=DOWNLOAD_DIR, filename=file_name)
        return file_path, yt.title, target_stream.resolution

    except VideoUnavailable:
        raise
    except RegexMatchError:
        raise
    except Exception as e:
        raise

# --- Automatic File Cleanup Function ---
def cleanup_old_files():
    """
    Deletes files in the DOWNLOAD_DIR that are older than CLEANUP_DELAY_MINUTES.
    This function runs periodically whenever the Streamlit app reloads.
    """
    now = datetime.datetime.now()
    cutoff_time = now - datetime.timedelta(minutes=CLEANUP_DELAY_MINUTES)
    
    cleaned_count = 0
    
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(file_path):
                file_timestamp = None
                try:
                    parts = filename.split('_')
                    if len(parts) >= 4: 
                        timestamp_str_in_name = parts[-2]
                        file_timestamp = datetime.datetime.strptime(timestamp_str_in_name, "%Y%m%d%H%M%S")
                except Exception:
                    file_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if file_timestamp and file_timestamp < cutoff_time:
                    try:
                        os.remove(file_path)
                        cleaned_count += 1
                    except Exception as e:
                        pass # Fail silently for API mode cleanup

# Run cleanup on every app reload
cleanup_old_files()

# --- Check for 'url' parameter in query string for "API" mode ---
query_url = st.query_params.get("url")
query_resolution = st.query_params.get("resolution", "720p") # Default to 720p if not specified

# Determine if we are in "API" mode (URL provided in query params)
api_mode = bool(query_url)

if api_mode:
    # --- "API" Mode: Direct JSON Response ---
    video_url = query_url
    selected_resolution = query_resolution # Use resolution from query params
    
    response_status = "error"
    response_message = "An unknown error occurred."
    video_title = "N/A"
    actual_resolution = "N/A"
    download_url = None
    file_name = None

    try:
        # 1. Download the video locally
        downloaded_file_path, video_title, actual_resolution = \
            download_youtube_video_for_streamlit(video_url, selected_resolution)
        
        if os.path.exists(downloaded_file_path):
            response_status = "success"
            response_message = f"Video processed successfully. File available for download. It will be removed from the server in approximately {CLEANUP_DELAY_MINUTES} minutes."
            file_name = os.path.basename(downloaded_file_path)
            download_url = f"streamlit://download/{uuid.uuid4().hex}" 
        else:
            response_message = "Error: Video file was not created on the server."

    except VideoUnavailable:
        response_message = "Error: The YouTube video is unavailable or private."
    except RegexMatchError:
        response_message = "Error: Invalid YouTube URL format. Please check the URL."
    except ValueError as ve:
        response_message = f"Error: {ve}"
    except Exception as e:
        response_message = f"An unexpected error occurred during processing: {e}"

    json_response = {
        "status": response_status,
        "video_title": video_title,
        "requested_resolution": selected_resolution,
        "actual_resolution_downloaded": actual_resolution,
        "file_name": file_name,
        "conceptual_download_url": download_url,
        "message": response_message,
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    st.json(json_response)
    st.stop() # Stop further execution to only show the JSON

else:
    # --- Interactive UI Mode ---
    st.title("🤖 Streamlit 'API' Endpoint (Simulated)")
    st.markdown("This app simulates an API endpoint. Enter a YouTube URL to get a JSON response with a direct download link (for this session).")
    st.markdown(f"**Downloaded files will be automatically deleted from the server after {CLEANUP_DELAY_MINUTES} minutes** (triggered on app reloads/interactions).")
    st.markdown("---")

    video_url = st.text_input(
        "🔗 Enter YouTube Video URL:",
        placeholder="e.g., https://www.youtube.com/channel/UCV8e2g4IWQqK71bbzGDEI4Q4"
    )

    resolutions = ['1080p', '720p', '480p', '360p', '240p', '144p']
    selected_resolution = st.selectbox("🎯 Select Desired Resolution:", resolutions, index=1)

    # Initialize session state to store the generated download link and file path
    if 'download_info' not in st.session_state:
        st.session_state.download_info = None

    if st.button("🔽 Generate Download Link (JSON)", use_container_width=True):
        if video_url:
            st.divider()
            st.subheader("API Response Simulation:")
            
            with st.spinner("Processing request and generating download link..."):
                try:
                    # 1. Download the video locally
                    downloaded_file_path, video_title, actual_resolution_downloaded = \
                        download_youtube_video_for_streamlit(video_url, selected_resolution)
                    
                    if not os.path.exists(downloaded_file_path):
                        st.error("Error: Video file was not created. Please try again.")
                        st.session_state.download_info = None
                    else:
                        # 2. Store info in session state for st.download_button
                        st.session_state.download_info = {
                            "file_path": downloaded_file_path,
                            "file_name": os.path.basename(downloaded_file_path),
                            "mime_type": "video/mp4",
                            "video_title": video_title,
                            "resolution": actual_resolution_downloaded 
                        }

                        # 3. Construct the JSON response object for display
                        json_response_content = {
                            "status": "success",
                            "video_title": video_title,
                            "resolution": actual_resolution_downloaded,
                            "download_url": f"streamlit://download/{uuid.uuid4().hex}", # Conceptual URL
                            "message": f"Click the 'Download File' button below to get your video. This file will be removed from the server in approximately {CLEANUP_DELAY_MINUTES} minutes."
                        }
                        
                        # 4. Display the JSON response
                        st.json(json_response_content)
                        st.success("JSON response generated. Find the 'Download File' button below.")

                except (VideoUnavailable, RegexMatchError, ValueError):
                    st.session_state.download_info = None
                    pass 
                except Exception as e:
                    st.error(f"An unhandled error occurred during processing: {e}")
                    st.session_state.download_info = None
        else:
            st.warning("Please enter a YouTube video URL.")

    st.markdown("---")

    # Provide the actual download button if download info is available in session_state
    if st.session_state.download_info:
        info = st.session_state.download_info
        if os.path.exists(info["file_path"]):
            with open(info["file_path"], "rb") as file:
                st.download_button(
                    label=f"⬇️ Download {info['video_title']} ({info['resolution']})",
                    data=file,
                    file_name=info["file_name"],
                    mime=info["mime_type"],
                    use_container_width=True
                )
            st.info(f"This file is temporarily stored on the server and will be deleted after {CLEANUP_DELAY_MINUTES} minutes.")
        else:
            st.error("Downloaded file not found. Please regenerate the link.")

    st.markdown("---")
    st.markdown("### Important Notes on Streamlit 'API' Simulation:")
    st.markdown("""
    -   **No True API Endpoint:** This Streamlit app does *not* provide a traditional REST API endpoint (`http://your-server/download?url=...`) that other programs can hit to get a JSON response and a direct file link.
    -   **Human Interaction Required:** The interactive mode relies on a human user to interact with the Streamlit web interface.
    -   **Session-Specific Downloads:** The `download_url` in the JSON is purely conceptual for this demo. The actual file download happens via the `st.download_button`, which serves the file *to the current browser session*.
    -   **Cleanup Trigger:** File cleanup happens when the Streamlit app's script reruns (e.g., when you interact with the app or refresh the page).
    -   **API Mode (Query Parameters):** If you provide `?url=YOUR_YOUTUBE_URL` in the browser's address bar, the app will attempt to process it directly and return a JSON response. No form will be displayed.
    """)
