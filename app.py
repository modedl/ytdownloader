import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
import os
import uuid
import json
import datetime
import time

# --- Streamlit UI Configuration (MUST BE THE VERY FIRST STREAMLIT COMMAND) ---
st.set_page_config(
    page_title="Streamlit 'API' Endpoint (Simulated) with Auto-Cleanup",
    page_icon="🤖",
    layout="centered"
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
            # st.warning(f"Resolution '{resolution}' not directly available for '{yt.title}'. Attempting to download highest available progressive resolution.")
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
            # st.info(f"Downloading '{yt.title}' at {target_stream.resolution}...") # Suppress info for API mode
            target_stream.download(output_path=DOWNLOAD_DIR, filename=file_name)
            # st.success(f"Downloaded '{yt.title}' temporarily to: {file_path}") # Suppress success for API mode
        # else:
            # st.info(f"Video '{file_name}' already exists in temporary folder for this session.") # Suppress info for API mode

        return file_path, yt.title, target_stream.resolution

    except VideoUnavailable:
        # st.error("Error: The YouTube video is unavailable or private.") # Suppress error for API mode
        raise
    except RegexMatchError:
        # st.error("Error: Invalid YouTube URL format. Please check the URL.") # Suppress error for API mode
        raise
    except Exception as e:
        # st.error(f"An unexpected error occurred during download: {e}") # Suppress error for API mode
        raise

# --- Automatic File Cleanup Function ---
def cleanup_old_files():
    """
    Deletes files in the DOWNLOAD_DIR that are older than CLEANUP_DELAY_MINUTES.
    This function runs periodically whenever the Streamlit app reloads.
    """
    now = datetime.datetime.now()
    cutoff_time = now - datetime.timedelta(minutes=CLEANUP_DELAY_MINUTES)
    
    # st.sidebar.markdown("---") # Commented out for a cleaner "API" response
    # st.sidebar.subheader("Automatic Cleanup Status:") # Commented out for a cleaner "API" response
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
                    # st.sidebar.warning(f"Could not parse timestamp from filename: {filename}. Using modification time for cleanup.") # Suppress warning for API mode

                if file_timestamp and file_timestamp < cutoff_time:
                    try:
                        os.remove(file_path)
                        # st.sidebar.info(f"Cleaned: {filename}") # Suppress info for API mode
                        cleaned_count += 1
                    except Exception as e:
                        # st.sidebar.error(f"Error deleting {filename}: {e}") # Suppress error for API mode
                        pass # Fail silently for API mode cleanup
    
    # if cleaned_count > 0: # Commented out for a cleaner "API" response
    #     st.sidebar.success(f"Cleaned up {cleaned_count} old files.")
    # else:
    #     st.sidebar.info("No old files to clean up at this moment.")
    # st.sidebar.markdown("---") # Commented out for a cleaner "API" response

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
    
    st.set_page_config(
        page_title="Streamlit 'API' Endpoint (Simulated) with Auto-Cleanup",
        page_icon="🤖",
        layout="wide" # Use wide layout for cleaner JSON output
    )

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
            # In a true API, this would be a direct public HTTP URL.
            # Here, it's conceptual for the Streamlit context.
            download_url = f"streamlit://download/{uuid.uuid4().hex}" 

            # IMPORTANT: For an actual API, you'd need to serve the file
            # directly using a web server or a mechanism that allows direct downloads.
            # Streamlit's `st.download_button` is for browser interaction.
            # For a pure API response, you might return the file content directly
            # or a signed URL to a cloud storage.
            # As this is a "simulated API", we'll just show the conceptual link.

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
        "file_name": file_name, # The name of the file on the server
        "conceptual_download_url": download_url, # Conceptual for Streamlit, not a direct public link
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
        placeholder="e.g., https://www.youtube.com/channel/UCV8e2g4IWQqK71bbzGDEI4Q2"
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
                    # Specific errors are already displayed by the download function, so no need to re-print.
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
