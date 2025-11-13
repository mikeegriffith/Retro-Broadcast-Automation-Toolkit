import os
import subprocess
from typing import List, Tuple
from colorama import Fore
from .Telestar_Bumper_Generator import create_teletext_gif
from .config import BUMPER_MUSIC_PATH, BUMPER_NTSC_PRESET, DEBUG_BUMPER_TEXT
from .utils.logger_setup import logger

def find_program_index(current_program, schedule):
    cur_time, cur_title, *_ = current_program
    for i, (time, title, *_) in enumerate(schedule):
        # normalize by stripping whitespace and lowercasing
        if title.strip().lower() == cur_title.strip().lower():
            return i
    return 0

def debug_print_bumper_text(program, bumper_type, text):
    if DEBUG_BUMPER_TEXT:
        print(f"Program: {program['title']}")
        print(f"  {bumper_type.capitalize()} Bumper Text: {text}\n")

def format_bumper_line(prefix: str, title: str, max_len: int = 25) -> str:
    """
    Formats a bumper line with a prefix (e.g. 'Now Playing', 'Next') and a title.
    If combined length exceeds max_len, title is moved to the next line.
    """
    line = f"{prefix} - {title}"
    if len(line) >= max_len:
        # Move title to the next line and remove the hyphen
        line = f"{prefix}\n{title}"
    return line


def generate_program_bumper_from_schedule(
    current_program: Tuple[str, str, str],
    schedule: List[Tuple[str, str, str]],
    output_path: str,
    position: str = "mid"
):
    """
    Generates a teletext-style program bumper using the full broadcast schedule.
    """

    lines = []
    
    # Find index of current_program in schedule
    idx = find_program_index(current_program, schedule)

    # Determine first line based on position
    if position == "mid":
        _, title, _ = current_program
        line = format_bumper_line("Now Playing", title or "UNKNOWN")
        lines.append(line)

    elif position == "end":
        is_last_program = False
        
        # Check if the next entry exists and if it is the "OFF AIR" sentinel
        if idx + 1 < len(schedule):
            _, next_title, _ = schedule[idx + 1]
            if next_title == "OFF AIR":
                is_last_program = True
                
        # Handle the case where the schedule ends without an explicit "OFF AIR" tuple
        elif idx + 1 >= len(schedule):
            is_last_program = True

        if is_last_program:
            # --- Custom Final Bumper ---
            # Program: A Garfield Christmas Special (23.34) clean -> Last Bumper Text: Thank you...
            line = "Thank you for watching Telestar Berlin.\nHappy Holidays!"
            lines.append(line)
            
            # We will skip the schedule listing below and pad with empty lines if needed.
            # Set a flag to bypass the standard schedule loop
            skip_schedule_listing = True 
            
        else:
            # --- Normal End Bumper (e.g., Program 1 or 2) ---
            # Next program is guaranteed to be a real title
            line = format_bumper_line("Next", next_title or "OFF AIR") # Source [3]
            lines.append(line)
            
            # FIX: Skip duplication by starting the schedule slice 2 steps ahead
            start_index = idx + 2
            skip_schedule_listing = False

    # Schedule listing block (Applies to mid and normal end bumpers)
    if position == "mid" or (position == "end" and not skip_schedule_listing):
        
        start_index = idx + 1 if position == "mid" else idx + 2
        next_entries = schedule[start_index: start_index + 2]
        
        for entry in next_entries:
            if not entry or len(entry) < 2:
                if not lines or lines[-1] != "OFF AIR":
                    lines.append("OFF AIR")
                continue

            start_time, title, *_ = entry
            start_time = start_time or "??:??"
            title = title or "OFF AIR"

            # Avoid consecutive OFF AIR
            if title == "OFF AIR" and lines and lines[-1] == "OFF AIR":
                continue

            line = f"{start_time} CET - {title}"
            if len(line) >= 25:
                line = f"{start_time} CET\n{title}"
            lines.append(line)

    # Ensure at least 3 lines total (This runs for ALL positions)
    # Ensure at least 3 lines total (This runs for ALL positions)
# [2] Ensure at least 3 lines total (This runs for ALL positions)
    while len(lines) < 3:
        
        # Check if the last element already contains "OFF AIR" (which handles the time-stamped entry)
        last_element_contains_off_air = "OFF AIR" in lines[-1]
        
        if position == "end" and is_last_program:
            lines.append("") # Keep final bumper tidy
        
        # NEW CONDITION: If the last element came from the schedule listing and contained OFF AIR, 
        # pad with an empty line to avoid redundancy.
        elif last_element_contains_off_air:
            lines.append("") 
            
        elif lines[-1] != "OFF AIR":
            lines.append("OFF AIR")
        else:
            lines.append("") # pad with empty line instead of repeating OFF AIR

    # Combine lines
    bumper_text = "\n".join(lines)

    # DEBUG mode: print bumper text and skip rendering
    if DEBUG_BUMPER_TEXT:
        bumper_type = "mid" if position == "mid" else "last"
        debug_print_bumper_text({"title": current_program[1]}, bumper_type, bumper_text)
        return bumper_text  # skip GIF/MP4 generation

    # Normal print if not in debug mode
    print(Fore.CYAN + f"\n🏁 Final bumper text:\n{bumper_text}")

    # Generate teletext bumper normally
    try:
        music_path = BUMPER_MUSIC_PATH if os.path.exists(BUMPER_MUSIC_PATH) else None
        ntsc_preset = BUMPER_NTSC_PRESET if os.path.exists(BUMPER_NTSC_PRESET) else None

        temp_gif_path = create_teletext_gif(
            text=bumper_text,
            output_path=output_path,
            music_path=music_path,
            ntsc_preset=ntsc_preset
        )

        # Convert GIF to MP4
        final_mp4 = os.path.splitext(output_path)[0] + ".mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-i", temp_gif_path, "-movflags", "+faststart", final_mp4],
            check=True
        )

        return final_mp4

    except Exception as e:
        logger.error(f"Failed to generate bumper: {e}")
        return None
