import os
import subprocess
import shutil
import numpy as np
import random
from pathlib import Path
from .video_utils import get_video_duration_ffprobe
from .bumpers import generate_program_bumper_from_schedule
from .utils.logger_setup import logger
from colorama import Fore
from typing import List
from .config import BUMPER_DURATION


# -----------------------------
# Helper: process any clip (bumper, segment, commercial)
# -----------------------------

def process_clip(input_path, output_path, width=640, height=480, fps=25,
                 fade_in=0.5, fade_out=0.5, target_duration=None, target_lufs=-16):
    duration = get_video_duration_ffprobe(input_path)
    fade_out_start = max(duration - fade_out, 0)
    vf_filter = (
        f"scale={width}:{height},fps={fps},format=yuv420p,"
        f"fade=t=in:st=0:d={fade_in},fade=t=out:st={fade_out_start}:d={fade_out}"
    )

    cmd = ["ffmpeg", "-y"]
    if target_duration is not None:
        cmd.extend(["-t", str(target_duration)])
    
    cmd.extend([
        "-i", input_path,
        "-vf", vf_filter,
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-pix_fmt", "yuv420p",
        "-metadata", "title=",
        output_path
    ])

    subprocess.run(cmd, check=True)
    return output_path


# -----------------------------
# Create black clip with silent audio
# -----------------------------
def create_black_clip_with_audio(output_path, duration=2, width=640, height=480, fps=25):
    subprocess.run([
        "ffmpeg", "-y",
        "-loglevel", "error",           # <-- suppress warnings
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:d={duration}",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000",
        "-shortest",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        output_path
    ], check=True)
    return output_path

# -----------------------------
# Main stitching function
# -----------------------------
def insert_commercials_with_bumpers(program, commercial_folder: str, output_path: str,
                                    break_points: list, bumper_placements: dict,
                                    commercial_per_break: float, next_programs: list,
                                    slot_duration: float, full_schedule: list):
    """
    Insert commercials and bumpers at break points with fixed bumper durations
    and precise commercial packing to fill the program slot exactly.
    """
    import os, subprocess, shutil
    from .video_utils import get_video_duration_ffprobe    
    from .bumpers import generate_program_bumper_from_schedule
    from colorama import Fore
    from .utils.logger_setup import logger

    temp_dir = "temp_bumpers"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        segments = []

        # Load commercial files
        commercials = [os.path.join(commercial_folder, f) for f in os.listdir(commercial_folder)
                       if f.lower().endswith((".mp4", ".mov"))] if os.path.exists(commercial_folder) else []
        
        
        # Replace your existing break loop with this block
        last_break = 0.0
        used_commercials = set()

        for break_idx, break_time in enumerate(break_points):
            segment_duration = break_time - last_break
            segment_file = os.path.join(temp_dir, f"segment_{break_idx}.mp4")

            # Extract program segment
            subprocess.run([
                "ffmpeg", "-y", "-i", program.filepath,
                "-ss", str(last_break),
                "-t", str(segment_duration),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
                "-pix_fmt", "yuv420p",
                segment_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Normalize & fade
            normalized_segment = os.path.join(temp_dir, f"proc_segment_{break_idx}.mp4")
            process_clip(segment_file, normalized_segment, fade_in=1.0, fade_out=1.0)
            segments.append(normalized_segment)

            # -----------------------------
            # Mid bumper (if this break is the mid bumper place)
            # -----------------------------
            if break_idx == bumper_placements.get('mid'):
                bumper_file = os.path.join(temp_dir, f"mid_bumper_{break_idx}.mp4")
                mid_bumper = generate_program_bumper_from_schedule(
                    current_program=(None, program.title, slot_duration),
                    schedule=full_schedule,
                    output_path=bumper_file,
                    position="mid"
                )
                if mid_bumper:
                    processed_bumper = os.path.join(temp_dir, f"proc_mid_bumper_{break_idx}.mp4")
                    process_clip(
                        mid_bumper,
                        processed_bumper,
                        fade_in=0.5,
                        fade_out=0.5,
                        target_duration=BUMPER_DURATION
                    )
                    segments.append(processed_bumper)

            # -----------------------------
            # Commercials (no repeats, fill exact time) — RUN THIS PER-BREAK
            # -----------------------------
            if commercials and commercial_per_break > 0:
                # Build working list excluding already-used commercials
                available_commercials = [c for c in commercials if c not in used_commercials]
                random.shuffle(available_commercials)

                time_remaining = commercial_per_break
                comm_idx = 0

                while time_remaining > 0 and available_commercials:
                    com_file = available_commercials.pop(0)  # pick without replacement
                    com_duration = get_video_duration_ffprobe(com_file) or 30

                    # Skip already-used (redundant because we filtered available_commercials,
                    # but kept here as a belt-and-suspenders check)
                    if com_file in used_commercials:
                        continue

                    if com_duration <= time_remaining:
                        # Process and append commercial
                        com_proc = os.path.join(temp_dir, f"com_{break_idx}_{comm_idx}.mp4")
                        process_clip(com_file, com_proc, fade_in=1, fade_out=0)
                        segments.append(com_proc)
                        time_remaining -= com_duration
                        comm_idx += 1

                        # mark as used so we don't repeat this file later in this program
                        used_commercials.add(com_file)
                    else:
                        # Too long for the remaining time — skip it
                        continue

                # If still time remaining, fill with short black clips
                filler_idx = 0
                while time_remaining > 0.5:  # small threshold to avoid tiny fractions
                    filler_duration = min(2.0, time_remaining)
                    black_clip = os.path.join(temp_dir, f"black_{break_idx}_{filler_idx}.mp4")
                    create_black_clip_with_audio(black_clip, duration=filler_duration)
                    segments.append(black_clip)
                    time_remaining -= filler_duration
                    filler_idx += 1

            # End of this break — move forward the last_break pointer
            last_break = break_time

        # -----------------------------
        # End bumper (fixed duration)
        # -----------------------------
        if bumper_placements.get('end', True):
            end_bumper_file = os.path.join(temp_dir, "end_bumper.mp4")
            end_bumper = generate_program_bumper_from_schedule(
                current_program=(None, program.title, slot_duration),
                schedule=full_schedule,
                output_path=end_bumper_file,
                position="end"
            )
            if end_bumper:
                processed_end_bumper = os.path.join(temp_dir, "proc_end_bumper.mp4")
                process_clip(
                    end_bumper,
                    processed_end_bumper,
                    fade_in=0.5,
                    fade_out=0.5,
                    target_duration=BUMPER_DURATION
                )
                segments.append(processed_end_bumper)

        # -----------------------------
        # Concatenate all segments
        # -----------------------------
        list_file = os.path.join(temp_dir, "concat_list.txt")
        with open(list_file, "w") as f:
            for seg in segments:
                f.write(f"file '{os.path.abspath(seg)}'\n")

        if segments:
            print(Fore.CYAN + "\n🏁 Merging video segments...")
            subprocess.run([
                "ffmpeg", "-y",
                "-loglevel", "error",           # <-- suppress warnings
                "-f", "concat", "-safe", "0", "-i", list_file,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
                "-pix_fmt", "yuv420p",
                output_path
            ], check=True)
        else:
            create_black_clip_with_audio(output_path, duration=5)

        shutil.rmtree(temp_dir)
        print(Fore.GREEN + f"✅ Final program ready: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to stitch program: {e}")
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        return False
