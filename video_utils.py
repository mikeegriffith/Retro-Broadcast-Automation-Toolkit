import cv2, subprocess, numpy as np, os
from .utils.logger_setup import logger

def sample_frame_at(cap, t, fps):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
    ret, frame = cap.read()
    if not ret:
        return None
    return frame

def detect_dark_frames(video_path, sample_interval=1.0, black_threshold=15):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    t = 0.0
    dark_times = []

    while t < duration:
        # --- DEBUG ---
        #print(f"DEBUG ⏱️ detect_dark_frames: t={t:.2f}, duration={duration:.2f}, fps={fps}")

        # Stop sampling slightly before end
        if t >= duration - 1:  # leave 1 second margin
            break

        frame = sample_frame_at(cap, t, fps)
        if frame is None:
            #print(f"DEBUG ⚠️ sample_frame_at returned None at t={t}")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if np.mean(gray) < black_threshold:
            dark_times.append(t)
            #print(f"DEBUG 🌑 Dark frame detected at t={t:.2f} (mean={np.mean(gray):.2f})")

        t += sample_interval

    cap.release()

    # Cluster dark frames
    clustered = []
    for dt in dark_times:
        if not clustered or dt - clustered[-1] > 2.0:
            clustered.append(dt)

    #print(f"DEBUG ✅ clustered dark times: {clustered}")
    return clustered

def detect_cartoon_breaks(video_path, min_gap=150, max_breaks=4):
    dark_frames = detect_dark_frames(video_path)
    cap = cv2.VideoCapture(video_path)
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 25.0)
    cap.release()

    chosen_breaks = []
    last_break = 0

    # Add dark frames as breakpoints
    for t in dark_frames:
        if t - last_break >= min_gap and t < duration - 2:  # leave 2s margin at end
            chosen_breaks.append(t)
            last_break = t
            if len(chosen_breaks) >= max_breaks:
                break

    # If not enough breaks, add evenly spaced fallback breaks
    step = duration / (max_breaks + 1)
    while len(chosen_breaks) < max_breaks:
        fallback = step * (len(chosen_breaks) + 1)
        if fallback >= duration - 2:
            fallback = duration - 2  # cap at 2s before end
        if all(abs(fallback - b) >= min_gap for b in chosen_breaks):
            chosen_breaks.append(fallback)
        else:
            # If no valid fallback can be added, break loop
            break

    # Ensure no breakpoint exceeds video duration
    chosen_breaks = [min(t, duration) for t in chosen_breaks]

    return sorted(chosen_breaks)

def get_video_duration_ffprobe(input_file: str) -> Optional[float]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             input_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except:
        return None

def normalize_video(input_file: str, output_file: str, width=1280, height=720, fps=25):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_file,
        "-vf", f"scale={width}:{height}",
        "-r", str(fps),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-ar", "44100",
        output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def add_fade_ffmpeg(input_file: str, output_file: str, fade_in=1, fade_out=1):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         input_file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    duration = float(result.stdout)
    fade_filter = f"fade=t=in:st=0:d={fade_in},fade=t=out:st={duration-fade_out}:d={fade_out}"
    subprocess.run([
        "ffmpeg", "-y", "-i", input_file, "-vf", fade_filter,
        "-c:a", "copy", output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def create_black_clip(output_file: str, duration=2, width=1280, height=720, fps=25):
    fade_time = 1
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-filter_complex",
        f"[0:v]fade=t=in:st=0:d={fade_time},fade=t=out:st={duration-fade_time}:d={fade_time}[v];"
        f"[1:a]afade=t=in:st=0:d={fade_time},afade=t=out:st={duration-fade_time}:d={fade_time}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest",
        output_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
