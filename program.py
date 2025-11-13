# teletext_broadcast/program.py

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .video_utils import get_video_duration_ffprobe
from .utils.logger_setup import logger
from .utils.format_helpers import format_timestamp
from .config import TARGET_SLOT_DURATION

# ---------------- ProgramInfo Class ----------------
class ProgramInfo:
    """Holds information about a TV program."""
    def __init__(self, order: int, title: str, filepath: str, start_time: Optional[str] = None):
        self.order = order
        self.title = title
        self.filepath = filepath
        self.start_time = start_time  # Format: "HH:MM"
        self.duration: Optional[float] = None  # in seconds
        self.actual_duration = None

    def __repr__(self):
        return f"Program({self.order}, '{self.title}', start={self.start_time})"

# ---------------- Helper Functions ----------------
def calculate_target_duration(actual_duration: float) -> int:
    """
    Round up actual duration to the nearest TARGET_SLOT_DURATION (e.g., 30 min slots)
    """
    import math
    return int(math.ceil(actual_duration / TARGET_SLOT_DURATION) * TARGET_SLOT_DURATION)

# ---------------- Program Parsing ----------------
def get_programs_from_folder(folder_path: str) -> list:
    """
    Get video files from a folder, prompt user for selection and optional reordering,
    and calculate rounded durations (nearest 30-min slot).
    
    Args:
        folder_path: Path to the folder containing video files.
    
    Returns:
        List of ProgramInfo objects in selected order with durations set.
    """
    import os
    from pathlib import Path
    from colorama import Fore

    video_ext = (".mp4", ".mov", ".mkv", ".avi")

    # List all video files in folder and sort
    all_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(video_ext)])
    if not all_files:
        print(Fore.RED + f"No video files found in folder: {folder_path}")
        return []

    # Display available programs with approximate rounded durations
    print(Fore.GREEN + "\nAvailable programs:")
    for i, f in enumerate(all_files, 1):
        filepath = os.path.join(folder_path, f)
        dur = get_video_duration_ffprobe(filepath) or 1800
        rounded = int(((dur + 1799) // 1800) * 1800)  # round up to nearest 30 min
        mins = int(rounded // 60)
        print(Fore.GREEN + f"{i}. {f} ({mins} min)")

    # Prompt for selection (default all)
    selected_input = input(Fore.MAGENTA + "Enter program numbers to include (comma-separated) or Enter for all: ").strip()
    if selected_input:
        try:
            indices = [int(x.strip()) - 1 for x in selected_input.split(",") if x.strip()]
            files = [all_files[i] for i in indices]
        except Exception:
            print(Fore.RED + "Invalid input, selecting all programs.")
            files = all_files
    else:
        files = all_files

    # Create ProgramInfo objects with order
    programs = []
    for i, f in enumerate(files, 1):
        filepath = os.path.join(folder_path, f)
        dur = get_video_duration_ffprobe(filepath) or 1800
        rounded_duration = int(((dur + 1799) // 1800) * 1800)
        program = ProgramInfo(order=i, title=Path(f).stem, filepath=filepath)
        program.duration = rounded_duration
        programs.append(program)

    # Display current order
    print(Fore.GREEN + "\nCurrent order with durations:")
    for p in programs:
        mins = int(p.duration // 60)
        print(Fore.GREEN + f"{p.order}. {p.title} ({mins} min)")

    return programs


# ---------------- Prompt Program Start Times ----------------
def prompt_program_times(programs: List[ProgramInfo]) -> List[ProgramInfo]:
    """
    Prompt user for start times of each program.
    Returns updated list of ProgramInfo objects with start_time and duration set.
    """
    print("\n" + "="*60)
    print("PROGRAM SCHEDULING")
    print("="*60)
    print("\nEnter start time for each program (format: HH:MM)")
    print("Press Enter to auto-calculate based on previous program duration\n")

    current_time = None

    for i, program in enumerate(programs):
        # Get actual duration
        duration = get_video_duration_ffprobe(program.filepath)
        if duration is None:
            duration = TARGET_SLOT_DURATION  # default 30 min
            logger.warning(f"Could not detect duration for {program.title}, defaulting to 30 min")
        program.duration = duration

        if i == 0:
            # First program - must specify time
            while True:
                time_input = input(f"[{program.order}] {program.title}\n    Start time: ").strip()
                try:
                    datetime.strptime(time_input, "%H:%M")
                    program.start_time = time_input
                    current_time = datetime.strptime(time_input, "%H:%M")
                    break
                except ValueError:
                    print("    Invalid format. Use HH:MM (e.g., 14:30)")
        else:
            # Subsequent programs - can auto-calculate
            slot_duration = calculate_target_duration(programs[i-1].duration)
            next_time = current_time + timedelta(seconds=slot_duration)
            default_time = next_time.strftime("%H:%M")

            time_input = input(f"[{program.order}] {program.title}\n    Start time (default: {default_time}): ").strip()
            if not time_input:
                program.start_time = default_time
                current_time = datetime.strptime(default_time, "%H:%M")
            else:
                try:
                    datetime.strptime(time_input, "%H:%M")
                    program.start_time = time_input
                    current_time = datetime.strptime(time_input, "%H:%M")
                except ValueError:
                    print("    Invalid format. Using default.")
                    program.start_time = default_time
                    current_time = datetime.strptime(default_time, "%H:%M")

        print()

    print("="*60)
    print("SCHEDULE SUMMARY")
    print("="*60)
    for program in programs:
        print(f"{program.start_time} - [{program.order}] {program.title}")
    print("="*60 + "\n")

    return programs

    """
    Get all video files in the folder, auto-calculate rounded durations,
    allow selection and reordering, without any filename parsing.
    """
    import math
    from pathlib import Path
    from colorama import Fore

    video_ext = (".mp4", ".mov", ".mkv", ".avi")

    # List and sort files
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(video_ext)]
    files.sort()

    if not files:
        print(Fore.RED + f"No video files found in folder: {folder_path}")
        return []

    # Show available programs with rounded durations
    print(Fore.GREEN + "\nAvailable programs:")
    for i, f in enumerate(files, 1):
        filepath = os.path.join(folder_path, f)
        dur = get_video_duration_ffprobe(filepath) or 1800
        rounded = int(math.ceil(dur / 1800.0) * 1800)
        mins = int(rounded // 60)
        print(Fore.GREEN + f"{i}. {f} ({mins} min)")

    # Prompt for selection (default all)
    selected = input(Fore.MAGENTA + "Enter program numbers to include (comma-separated) or Enter for all: ").strip()
    if selected:
        try:
            indices = [int(x.strip()) - 1 for x in selected.split(",") if x.strip()]
            files = [files[i] for i in indices]
        except:
            print(Fore.RED + "Invalid input, selecting all.")

    # Create ProgramInfo objects with order
    programs = [ProgramInfo(title=Path(f).stem, filepath=os.path.join(folder_path, f), order=i+1) 
                for i, f in enumerate(files)]

    # Set duration for each program (rounded)
    for p in programs:
        dur = get_video_duration_ffprobe(p.filepath) or 1800
        p.duration = int(math.ceil(dur / 1800.0) * 1800)

    # Show current order and durations
    print(Fore.GREEN + "\nCurrent order with durations:")
    for p in programs:
        mins = int(p.duration // 60) if p.duration else 30
        print(Fore.GREEN + f"{p.order}. {p.title} ({mins} min)")

    # Optional reordering
    reorder = input(Fore.MAGENTA + "Reorder programs? Enter comma-separated indices or Enter to skip: ").strip()
    if reorder:
        try:
            new_order = [int(x.strip()) - 1 for x in reorder.split(",") if x.strip()]
            programs = [programs[i] for i in new_order]
            for idx, p in enumerate(programs, 1):
                p.order = idx
        except:
            print(Fore.RED + "Invalid reorder, keeping original order.")

    return programs
