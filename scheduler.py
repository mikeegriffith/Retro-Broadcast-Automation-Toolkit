# scheduler.py (Rewritten and Corrected)

import csv, os
import math
from datetime import datetime, timedelta
from colorama import Fore, Style
from typing import List, Optional
from .timeline_gui import display_timeline_gui

# --- Contextual Imports/Definitions (Based on Sources) ---

# Assuming TARGET_SLOT_DURATION is imported from config
TARGET_SLOT_DURATION = 30 * 60 # 1800 seconds

class ProgramInfo:
    """Holds information about a TV program (Source,)"""
    def __init__(self, title, filepath, order=0):
        self.title = title
        self.filepath = filepath
        self.order = order
        self.actual_duration = None
        self.duration = None
        self.start_time = None

# Assuming get_video_duration_ffprobe is available globally or imported
def get_video_duration_ffprobe(input_file: str) -> Optional[float]:
    """Placeholder for FFprobe utility (Source)"""
    # Placeholder approximation, actual implementation uses subprocess
    return 1800.0 

# ----------------------------------------------------------------------
# Interactive Broadcast Schedule Builder and Editor (build_time_schedule)
# ----------------------------------------------------------------------

def build_time_schedule(programs: List[ProgramInfo], block_start: datetime, export_folder: str = "tv_output"):
    """
    Builds and displays a time schedule list for all programs,
    allowing edits, placeholders, deletions, reordering, and approval.
    Exports final schedule to TXT and CSV files.
    """
    print(Fore.CYAN + "\n🕒 Building Time Schedule...")

    schedule = []
    current_time = block_start

    # Ensure program durations exist and are rounded
    for prog in programs:
        if prog.duration is None:
            # Durations rounded up to nearest TARGET_SLOT_DURATION (1800s)
            dur = get_video_duration_ffprobe(prog.filepath) or 1800
            prog.actual_duration = get_video_duration_ffprobe(prog.filepath) or 1800
            prog.duration = int(math.ceil(prog.actual_duration / 1800.0) * 1800)

    # Build initial schedule
    for prog in programs:
        prog.start_time = current_time.strftime("%H:%M")
        schedule.append((prog.start_time, prog.title, prog.duration))
        current_time += timedelta(seconds=prog.duration)

    # Interactive editing
    while True:
        print(Fore.GREEN + "\n📺 PROGRAM SCHEDULE:")
        for i, (time, title, duration) in enumerate(schedule, 1):
            mins = int(duration / 60) if duration else 0
            dur_label = f" ({mins} min)" if duration > 0 else ""
            color = Fore.YELLOW if title == "OFF AIR" else Fore.WHITE
            print(f"{i:2d}. {Fore.CYAN}{time}{Style.RESET_ALL} — {color}{title}{dur_label}")

        choice = input(
            Fore.MAGENTA +
            "\nOptions: [e]dit titles, [p]laceholders, [r]eorder, [d]elete, [y] approve: "
        ).strip().lower()

        if choice in ("y", ""):
            break

        # Edit title
        elif choice == "e":
            idx = input("Enter line number to edit title: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(schedule):
                idx_int = int(idx) - 1
                old_title = schedule[idx_int]
                new_title = input(f"Edit title for line {idx} [{old_title}]: ").strip() or old_title
                time, _, duration = schedule[idx_int]
                schedule[idx_int] = (time, new_title, duration)

                # Update ProgramInfo if matches existing program
                for p in programs:
                    if p.title == old_title or p.start_time == time:
                        p.title = new_title

        # Delete programs
        elif choice == "d":
            idx = input("Enter line number(s) to delete, comma-separated: ").strip()
            try:
                indices = sorted([int(x.strip()) - 1 for x in idx.split(",") if x.strip()], reverse=True)
                for i in indices:
                    if 0 <= i < len(schedule) - 1: # do not delete OFF AIR
                        del schedule[i]

                # Recalculate start times
                cur = block_start
                for idx2 in range(len(schedule)):
                    t, ttl, d = schedule[idx2]
                    schedule[idx2] = (cur.strftime("%H:%M"), ttl, d)
                    cur += timedelta(seconds=d)

            except Exception as e:
                print(Fore.RED + f"Invalid input, skipping deletion. Error: {e}")

        # Add placeholders
        elif choice == "p":
            add_more = input("Add up to 3 placeholder programs? (y/n): ").lower().strip()
            if add_more == "y":
                try:
                    num = min(3, int(input("How many placeholders (1–3)? ").strip() or "1"))
                except:
                    num = 1
                for i in range(num):
                    title = input(f"Enter placeholder title #{i + 1}: ").strip() or f"Placeholder {i + 1}"
                    print(f"Select duration for '{title}':")
                    print("1) 30 min\n2) 1 hr\n3) 1.5 hr\n4) 2 hr")
                    while True:
                        choice_d = input("Enter 1-4: ").strip()
                        if choice_d in ("1","2","3","4"):
                            break
                        else:
                            print(Fore.RED + "Invalid selection. Choose 1-4.")
                    
                    # FIX 1: Correctly define dur_options (resolves SyntaxError)
                    dur_options = [1800, 3600, 5400, 7200]
                    dur_sec = dur_options[int(choice_d)-1]

                    # --- Calculate placeholder start time ---
                    if schedule:
                        last_prog_end = datetime.strptime(schedule[-1][0], "%H:%M") + timedelta(seconds=schedule[-1][2])
                    else:
                        last_prog_end = block_start

                    placeholder_start = last_prog_end.strftime("%H:%M")

                    # --- Append the placeholder program ---
                    schedule.append((placeholder_start, title, dur_sec))

                    # Recalculate all start times from block_start
                    cur = block_start
                    for idx2 in range(len(schedule)):
                        t, ttl, d = schedule[idx2]
                        schedule[idx2] = (cur.strftime("%H:%M"), ttl, d)
                        cur += timedelta(seconds=d)

        # Reorder programs
        elif choice == "r":
            print(Fore.YELLOW + "Current order:")
            
            # Initialize a counter that only increments for displayable programs
            display_index = 1
            
            # Iterate over the full schedule list (Source [2])
            for time, title, duration in schedule:
                # Check if the title is not the sentinel value
                if title != "OFF AIR":
                    print(f"{display_index}. {title}")
                    display_index += 1

            new_order = input("Enter new order (comma-separated indices): ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in new_order.split(",") if x.strip()]
                
                # Apply indices directly to the current schedule list
                ordered = [schedule[i] for i in indices]
                
                # The schedule now consists only of the ordered programs
                schedule = ordered
                
                # Recalculate start times (this block remains as in Source [2])
                cur = block_start
                for idx2 in range(len(schedule)):
                    t, ttl, d = schedule[idx2]
                    schedule[idx2] = (cur.strftime("%H:%M"), ttl, d)
                    cur += timedelta(seconds=d)

            except Exception as e:
                print(Fore.RED + f"Invalid input: {e}")
    
    # --- Calculate block end time automatically ---
    if schedule:
        last_prog_time_str, last_prog_title, last_prog_duration = schedule[-1]
        last_start_dt = datetime.strptime(last_prog_time_str, "%H:%M")
        block_end_time = last_start_dt + timedelta(seconds=last_prog_duration)
        print(Fore.CYAN + f"\n⏰ BLOCK END TIME: {block_end_time.strftime('%H:%M')}")

        # --- FIX: Explicitly insert time-stamped OFF AIR entry ---
        block_end_time_str = block_end_time.strftime("%H:%M")
        
        # Check if the final entry is not already OFF AIR (e.g., if added via placeholder [5])
        if last_prog_title != "OFF AIR":
            # Append the calculated end time as the start time for the "OFF AIR" slot 
            # Duration is 0 as it's a marker, not a program requiring time.
            schedule.append((block_end_time_str, "OFF AIR", 0))

    else:
        block_end_time = block_start
    
    # Final display
    print(Fore.CYAN + "\n✅ FINALIZED BROADCAST SCHEDULE:")
    for time, title, duration in schedule:
        mins = int(duration / 60) if duration else 0
        dur_label = f" ({mins} min)" if duration > 0 else ""
        print(f"{Fore.CYAN}{time}{Style.RESET_ALL} — {Fore.WHITE}{title}{dur_label}")

    # Export schedule
    os.makedirs(export_folder, exist_ok=True)
    base_time = schedule[0][0] if schedule else block_start.strftime("%H:%M")
    txt_path = os.path.join(export_folder, f"schedule_{base_time.replace(':', '')}.txt")
    csv_path = os.path.join(export_folder, f"schedule_{base_time.replace(':', '')}.csv")

    # TXT
    with open(txt_path, "w", encoding="utf-8") as txt:
        txt.write(f"TELENET BROADCAST BLOCK - {base_time} START\n")
        txt.write("-" * 40 + "\n")
        for time, title, _ in schedule:
            txt.write(f"{time} — {title}\n")
        txt.write("-" * 40 + "\n")
        txt.write(f"Total Programs: {len(schedule) - 1}\n")
        txt.write(f"Block Ends: {block_end_time.strftime('%H:%M')}\n")
        txt.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Time", "Title"])
        for row in schedule:
            writer.writerow(row[:2]) # Writing Time and Title

    print(Fore.GREEN + f"\n📤 Schedule exported to:\n{txt_path}\n{csv_path}")

    # ----------------------------------------------------------------------
    # FIX 2: Reorder ProgramInfo list (programs) to match approved schedule sequence
    # This replaces the original insufficient 'Sync start times' loop.
    # ----------------------------------------------------------------------

    # 1. Create a dictionary map for quick ProgramInfo lookup
    program_map = {prog.title: prog for prog in programs}

    # 2. Build the final ordered list of ProgramInfo objects
    final_ordered_programs = []
    for time, title, duration in schedule:
        # Only process actual program entries that exist in the original programs list
        if title != "OFF AIR" and title in program_map:
            prog = program_map.get(title)
            
            # Sync the final start time
            prog.start_time = time
            final_ordered_programs.append(prog)
            
    # 3. Replace the contents of the original 'programs' list (in-place update)
    programs[:] = final_ordered_programs
    
    # ----------------------------------------------------------------------

    return schedule