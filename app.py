import streamlit as st
from pytubefix import YouTube
from pytubefix.exceptions import VideoUnavailable, RegexMatchError
import json
import datetime
import os
import shutil # For safely handling directory creation/deletion
import uuid # For unique filenames

# --- Streamlit UI Configuration (MUST BE THE VERY FIRST STREAMLIT COMMAND) ---
st.set_page_config(
    page_title="Streamlit YouTube Direct Link Extractor (All Streams)",
    page_icon="🔗",
    layout="wide"
)

# --- IMPORTANT: Configure Streamlit to serve static files ---
# You would need a file named .streamlit/config.toml in your app's root
# with the following content for static serving to work:
# [server]
# enableStaticServing = true
#
# NOTE: As explained, this does NOT work for video MIME types by default!
# You would need a custom server setup to serve MP4 with correct MIME type.

DOWNLOAD_DIR = "downloads" # This will map to your Streamlit's static serving path if enabled for that.
# However, for a proper solution, this would be a separate file server or cloud storage.

# --- Helper Function for Extracting and Downloading YouTube Stream Links ---
def process_youtube_streams(url: str) -> tuple[str, list[dict], str]:
    """
    Attempts to get all available streams from a YouTube video and download
    the largest progressive (video+audio) and largest video-only streams.
    Returns (video_title, list_of_stream_details, download_session_id) upon success.
    Raises an exception on failure.
    """
    try:
        yt = YouTube(url)
        video_title = yt.title
        
        # Create a unique directory for this download session
        session_id = str(uuid.uuid4())
        session_download_path = os.path.join(DOWNLOAD_DIR, session_id)
        os.makedirs(session_download_path, exist_ok=True) # Create session-specific folder

        all_streams = yt.streams.order_by('resolution').desc().order_by('itag')

        # Find largest progressive (video+audio) and largest video-only streams
        largest_progressive_stream = None
        largest_video_only_stream = None

        # Filter out audio-only streams for initial download attempt,
        # unless it's the only option for a video-only companion.
        # This logic can get very complex for "best" streams.
        # For simplicity, we'll try to find any largest progressive and largest video-only.
        
        # Let's refine the stream selection:
        # 1. Prioritize progressive streams (video + audio)
        # 2. For adaptive, find the highest resolution video-only stream
        
        streams_to_download_info = []
        
        # Attempt to get the highest resolution progressive stream
        progressive_streams = yt.streams.filter(progressive=True).order_by('resolution').desc()
        if progressive_streams:
            largest_progressive_stream = progressive_streams.first()
            if largest_progressive_stream:
                streams_to_download_info.append({
                    "stream_obj": largest_progressive_stream,
                    "type_label": "progressive (video+audio)",
                    "file_suffix": "_combined.mp4" # Assume MP4 for simplicity, check mime_type for accuracy
                })
        
        # Attempt to get the highest resolution video-only stream
        video_only_streams = yt.streams.filter(type="video", adaptive=True).order_by('resolution').desc()
        if video_only_streams:
            largest_video_only_stream = video_only_streams.first()
            if largest_video_only_stream:
                streams_to_download_info.append({
                    "stream_obj": largest_video_only_stream,
                    "type_label": "adaptive (video-only)",
                    "file_suffix": "_video_only.mp4" # Assume MP4
                })

        downloaded_file_urls = []
        full_stream_details = []

        # Perform downloads
        for dl_info in streams_to_download_info:
            s = dl_info["stream_obj"]
            original_filename = s.default_filename
            download_filename = f"{os.path.splitext(original_filename)[0]}{dl_info['file_suffix']}"
            local_file_path = os.path.join(session_download_path, download_filename)

            try:
                st.write(f"Downloading {dl_info['type_label']} ({s.resolution if s.type == 'video' else 'N/A'})... to {local_file_path}")
                s.download(output_path=session_download_path, filename=download_filename)
                
                # IMPORTANT: THIS IS THE THEORETICAL URL IF STATIC SERVING WORKED FOR VIDEOS
                # AND IF THE SESSION DIRECTORY COULD BE MAPPED.
                # ON STREAMLIT CLOUD, this URL will likely NOT WORK for video files
                # due to MIME type restrictions and ephemeral storage.
                
                # The actual URL structure for Streamlit static serving is /app/static/your_filename
                # But it expects files directly in the `static` folder, not subdirectories for dynamic content.
                # If you place downloaded files directly into the root 'static' folder (bad idea for multiple videos),
                # the URL would be something like:
                # `f"{st.secrets['APP_BASE_URL']}/app/static/{download_filename}"`
                # Assuming 'APP_BASE_URL' is set as a Streamlit secret, e.g., https://modsbots-api.streamlit.app

                # For this example, we'll construct a hypothetical URL based on direct placement
                # within the *root* of the DOWNLOAD_DIR (if it were mapped to /app/static)
                # But it's still flawed for the reasons above.
                
                # Better to just give a local path indication, and let the user know they can't directly download from YOUR server
                
                # Let's provide a "simulated" direct link from the server's perspective
                # This path assumes your Streamlit app itself is the "server" and can serve this path
                # which it cannot for arbitrary dynamically created files, unless via st.download_button
                # OR a *separate* web server configured specifically for serving these files.
                
                # For Streamlit's *static* serving, the URL should be relative to the 'static' folder
                # If we were to use the actual static serving:
                # 1. Create a `static` folder at your app's root.
                # 2. Set `enableStaticServing = true` in `.streamlit/config.toml`.
                # 3. Save the video file directly into `./static/`.
                # 4. The URL would be `/app/static/your_video.mp4`.
                # This would still face the MIME type issue for videos.
                
                # Given the limitations, we can't reliably provide a *working* direct URL from your Streamlit server.
                # The most we can do is provide information about where the file *would* be if a proper
                # file-serving solution were in place.

                # Let's adjust to reflect the reality: you can't get a publicly accessible URL like this.
                # Instead, we'll list the *local* path on the server (which is not useful to the client)
                # or just acknowledge the download was attempted.
                
                # For the purpose of showing *what would be returned if it worked*:
                hypothetical_server_url = f"https://modsbots-api.streamlit.app/downloaded_videos/{session_id}/{download_filename}" # This path does not exist in Streamlit
                
                downloaded_file_urls.append({
                    "type": dl_info["type_label"],
                    "resolution": s.resolution if s.type == "video" else "N/A",
                    "filesize_mb": round(s.filesize / (1024 * 1024), 2) if s.filesize else None,
                    "server_download_url": hypothetical_server_url, # This link will not work on Streamlit Cloud directly
                    "note": "This is a placeholder URL. Streamlit Community Cloud cannot directly serve dynamically downloaded video files at this path due to security and resource limitations, and typically serves video files as plain text. You would need a separate file hosting service or custom web server for this functionality.",
                    "original_youtube_cdn_url": s.url # Still provide the original for clarity
                })

            except Exception as download_err:
                st.warning(f"Could not download {dl_info['type_label']}: {download_err}")
                downloaded_file_urls.append({
                    "type": dl_info["type_label"],
                    "resolution": s.resolution if s.type == "video" else "N/A",
                    "filesize_mb": round(s.filesize / (1024 * 1024), 2) if s.filesize else None,
                    "server_download_url": "N/A - Download failed or not hosted",
                    "note": f"Failed to download this stream: {download_err}",
                    "original_youtube_cdn_url": s.url
                })
            
            # Append all stream details (including those not downloaded)
            full_stream_details.append({
                "type": dl_info["type_label"],
                "resolution": s.resolution if s.type == "video" else "N/A",
                "fps": s.fps if s.type == "video" else "N/A",
                "vcodec": s.video_codec,
                "acodec": s.audio_codec,
                "mime_type": s.mime_type,
                "filesize_mb": round(s.filesize / (1024 * 1024), 2) if s.filesize else None,
                "itag": s.itag,
                "url": s.url # Original YouTube CDN URL
            })

        if not downloaded_file_urls:
            raise ValueError("No streams could be downloaded or processed.")

        # Cleanup: In a real scenario, you'd schedule these files for deletion
        # after a certain time, but this is beyond Streamlit's direct capability.
        # For this example, the directory remains until app restart or server cleanup.
        
        return video_title, downloaded_file_urls, session_id # Return the list of *downloaded* file info

    except VideoUnavailable:
        raise ValueError("The YouTube video is unavailable or private.")
    except RegexMatchError:
        raise ValueError("Invalid YouTube URL format. Please check the URL.")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")

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
    downloaded_streams_info = [] # This will store info about *downloaded* files
    download_session_id = "N/A"

    try:
        # Process and attempt to download streams
        video_title, downloaded_streams_info, download_session_id = process_youtube_streams(video_url)
        
        response_status = "success"
        response_message = "Attempted to download specified streams to server. Note: Direct server download links provided are for illustrative purposes and may not work on Streamlit Cloud due to security and resource limitations, and MIME type issues. You would typically need a dedicated file server. The original YouTube CDN links are also included in the 'original_youtube_cdn_url' field for each stream."

    except ValueError as ve:
        response_message = f"Error: {ve}"
    except Exception as e:
        response_message = f"An unexpected error occurred: {e}"

    json_response = {
        "status": response_status,
        "video_title": video_title,
        "download_session_id": download_session_id, # Identifier for this specific download attempt
        "downloaded_streams_info": downloaded_streams_info, # List of dictionaries with download details
        "message": response_message,
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    st.json(json_response)
    st.stop() # Stop further execution to only show the JSON

else:
    # --- Interactive UI Mode ---
    st.title("🔗 YouTube Direct Link Extractor (All Streams)")
    st.markdown("**(Warning: Attempting server-side downloads of video files is generally not recommended for Streamlit apps due to resource limitations and hosting capabilities.)**")
    st.markdown("Enter a YouTube URL to get a list of **all** direct download links, including combined video+audio streams and separate video-only/audio-only streams. This version *attempts* to download specific streams to the server and provide hypothetical server-side links.")
    st.markdown("---")

    video_url = st.text_input(
        "🔗 Enter YouTube Video URL:",
        placeholder="e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    if st.button("🔽 Get & Download Streams to Server (Illustrative)", use_container_width=True):
        if video_url:
            st.divider()
            st.subheader("Server-Side Download Attempt Results:")
            
            # Ensure the base download directory exists
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)

            with st.spinner("Attempting to download selected video streams to the server..."):
                try:
                    video_title, downloaded_streams_info, session_id = process_youtube_streams(video_url)
                    st.success(f"Processing complete for: **{video_title}**")
                    st.warning("""
                        **IMPORTANT DISCLAIMER REGARDING SERVER DOWNLOADS:**
                        - This app *attempted* to download the streams to the server's local disk.
                        - **The "Server Download URL" links provided below will almost certainly NOT work** if deployed on Streamlit Community Cloud (or similar serverless platforms) because:
                            1.  Streamlit is not designed to be a file server for dynamically generated, large binary files.
                            2.  Files downloaded to the server during app execution are ephemeral and will be deleted.
                            3.  Streamlit's static file serving is restricted to specific MIME types and a fixed `static` folder, not arbitrary paths with video files.
                        - For a reliable server-side download solution, you would need a dedicated file storage (e.g., AWS S3, Google Cloud Storage) and a separate web server to serve the files.
                        - **The best practice remains to provide the original YouTube CDN links (listed as 'original_youtube_cdn_url') and let the user download directly from YouTube.**
                    """)

                    st.dataframe(
                        downloaded_streams_info,
                        column_order=[
                            "type", "resolution", "filesize_mb", "server_download_url", "note", "original_youtube_cdn_url"
                        ],
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Optional: Add a button to delete the downloaded files for this session
                    # This is still manual and not robust for multiple users/sessions
                    if st.button(f"Clean up downloaded files for session {session_id}", key="cleanup_button"):
                        session_download_path = os.path.join(DOWNLOAD_DIR, session_id)
                        if os.path.exists(session_download_path):
                            shutil.rmtree(session_download_path)
                            st.success(f"Cleaned up {session_download_path}")
                        else:
                            st.info("No files found to clean up for this session.")

                except ValueError as ve:
                    st.error(f"Error: {ve}")
                except Exception as e:
                    st.error(f"An unhandled error occurred: {e}")
        else:
            st.warning("Please enter a YouTube video URL.")

    st.markdown("---")
    st.markdown("### Important Notes (Updated for Server Download Attempt):")
    st.markdown("""
    -   **Server-Side Download Limitations:** This version *attempts* to download videos to the Streamlit server. However, **this is NOT a reliable or scalable solution for publicly hosted apps.** Streamlit is not a file hosting service, and dynamically downloaded files will likely be ephemeral and unaccessible externally.
    -   **Resource Consumption:** Performing downloads on the server consumes significant resources (bandwidth, storage, CPU) of the hosting environment. This can lead to app slowdowns or shutdowns.
    -   **Link Validity:** The "Server Download URL" provided will almost certainly **NOT work** from a client's browser if the app is deployed to Streamlit Community Cloud or similar platforms.
    -   **Best Practice:** For reliable direct downloads, you should **always use the 'original_youtube_cdn_url'** provided by `pytubefix` and let the user's browser or download manager handle the download directly from YouTube's CDN. This offloads the burden from your server.
    """)
