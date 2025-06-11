import streamlit as st
from pytube import YouTube
from pytube.exceptions import VideoUnavailable, RegexMatchError
import os
import uuid
import json
import time
import datetime

# --- Configuration ---
DOWNLOAD_DIR = "temp_downloads" # Using 'temp_downloads' to emphasize transient nature
CLEANUP_DELAY_MINUTES = 5 # Set to 5 minutes for file deletion

# Ensure the temporary download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- Helper Function for Download ---
def download_youtube_video_for_streamlit(url: str, resolution: str) -> tuple[str, str, str]:
    """
    Attempts to download a YouTube video to a temporary location.
    Returns (file_path, video_title, actual_resolution_downloaded) or raises an exception.
    """
    try:
        yt = YouTube(url)
        
        # Get progressive streams (video + audio combined)
        progressive_streams = yt.streams.filter(progressive=True).order_by('resolution').desc()

        target_stream = None
        for s in progressive_streams:
            if s.resolution == resolution:
                target_stream = s
                break
        
        if not target_stream:
            st.warning(f"Resolution '{resolution}' not directly available for '{yt.title}'. Attempting to download highest available progressive resolution.")
            target_stream = progressive_streams.first()
            
            if not target_stream:
                raise ValueError("No progressive streams found for this video at any resolution.")

        # Generate a unique filename to include timestamp for cleanup logic
        unique_id = uuid.uuid4().hex[:8] 
        safe_title = "".join([c for c in yt.title if c.isalnum() or c in (' ', '.', '_')]).strip()
        safe_title = safe_title.replace(' ', '_')[:50]
        
        # Add a timestamp to the filename for cleanup
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        
        file_name = f"{safe_title}_{target_stream.resolution}_{timestamp_str}_{unique_id}.mp4"
        file_path = os.path.join(DOWNLOAD_DIR, file_name)

        # Only download if not already in session's temp folder (unlikely with UUID)
        if not os.path.exists(file_path):
            st.info(f"Downloading '{yt.title}' at {target_stream.resolution}...")
            target_stream.download(output_path=DOWNLOAD_DIR, filename=file_name)
            st.success(f"Downloaded '{yt.title}' temporarily to: {file_path}")
        else:
            st.info(f"Video '{file_name}' already exists in temporary folder for this session.")

        return file_path, yt.title, target_stream.resolution

    except VideoUnavailable:
        st.error("Error: The YouTube video is unavailable or private.")
        raise
    except RegexMatchError:
        st.error("Error: Invalid YouTube URL format. Please check the URL.")
        raise
    except Exception as e:
        st.error(f"An unexpected error occurred during download: {e}")
        raise

# --- Automatic File Cleanup Function ---
def cleanup_old_files():
    """
    Deletes files in DOWNLOAD_DIR older than CLEANUP_DELAY_MINUTES.
    This runs periodically when the Streamlit app reloads.
    """
    now = datetime.datetime.now()
    cutoff_time = now - datetime.timedelta(minutes=CLEANUP_DELAY_MINUTES)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Automatic Cleanup Status:")
    cleaned_count = 0
    
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(file_path):
                # Try to parse timestamp from filename, fallback to modification time
                try:
                    # Filename format: safe_title_resolution_YYYYMMDDHHMMSS_uuid.mp4
                    parts = filename.split('_')
                    if len(parts) >= 4: # Check if timestamp part exists
                        timestamp_str_in_name = parts[-2]
                        file_timestamp = datetime.datetime.strptime(timestamp_str_in_name, "%Y%m%d%H%M%S")
                    else:
                        # Fallback to file's modification time if timestamp not in name
                        file_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                        st.sidebar.warning(f"Could not parse timestamp from filename: {filename}. Using modification time.")
                except Exception:
                    file_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                    st.sidebar.warning(f"Could not parse timestamp from filename: {filename}. Using modification time.")

                if file_timestamp < cutoff_time:
                    try:
                        os.remove(file_path)
                        st.sidebar.info(f"Cleaned: {filename}")
                        cleaned_count += 1
                    except Exception as e:
                        st.sidebar.error(f"Error deleting {filename}: {e}")
    
    if cleaned_count > 0:
        st.sidebar.success(f"Cleaned up {cleaned_count} old files.")
    else:
        st.sidebar.info("No old files to clean up at this moment.")
    st.sidebar.markdown("---")

# Run cleanup on every app reload
cleanup_old_files()


# --- Streamlit UI ---
st.set_page_config(
    page_title="Streamlit 'API' Endpoint (Simulated) with Auto-Cleanup",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Streamlit 'API' Endpoint (Simulated)")
st.markdown("This app simulates an API endpoint. Enter a YouTube URL to get a JSON response with a direct download link (for this session).")
st.markdown(f"**Downloaded files will be automatically deleted from the server after {CLEANUP_DELAY_MINUTES} minutes** (on next app interaction/reload).")
st.markdown("---")

video_url = st.text_input("🔗 Enter YouTube Video URL:", placeholder="e.g., example.com/?vid=youtube.com/watch")

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
                downloaded_file_path, video_title, actual_resolution_downloaded = download_youtube_video_for_streamlit(video_url, selected_resolution)
                
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
                        "resolution": actual_resolution_downloaded # Use actual downloaded resolution
                    }

                    # 3. Construct the JSON response object
                    # The 'download_url' here is a placeholder/conceptual URL for Streamlit's internal handling.
                    # A real API would return a direct public HTTP URL.
                    
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
                # Errors are already displayed by the download function
                pass
            except Exception as e:
                st.error(f"An unhandled error occurred during processing: {e}")
                st.session_state.download_info = None
    else:
        st.warning("Please enter a YouTube video URL.")

st.markdown("---")

# Provide the actual download button if info is available in session_state
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
-   **No True API Endpoint:** This Streamlit app does *not* provide a traditional REST API endpoint that other programs can hit.
-   **Human Interaction Required:** It requires a human user to interact with the Streamlit web interface.
-   **Session-Specific Downloads:** The `download_url` in the JSON is purely conceptual for this demo. The actual file download happens via the `st.download_button`, which serves the file *to the current browser session*.
-   **Cleanup Trigger:** File cleanup happens when the Streamlit app's script reruns (e.g., when you interact with the app or refresh the page).
""")
