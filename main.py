import os, sys, math
from datetime import datetime
from colorama import Fore
from .config import TARGET_SLOT_DURATION, DEBUG_BUMPER_TEXT
from .program import get_programs_from_folder
from .scheduler import build_time_schedule
from .video_utils import get_video_duration_ffprobe, detect_cartoon_breaks
from .timeline_gui import display_timeline_gui
from .bumpers import generate_program_bumper_from_schedule
from .commercials import insert_commercials_with_bumpers
from .utils.logger_setup import logger

class ProgramInfo:
    def __init__(self, title, filepath, order=0):
        self.title = title
        self.filepath = filepath
        self.order = order
        self.actual_duration = None
        self.duration = None
        self.start_time = None

def main():
    default_folder = "/Programs"
    commercials_folder = "/Commercials"
    output_folder = "tv_output"
    os.makedirs(output_folder, exist_ok=True)

    programs = get_programs_from_folder(default_folder)
    if not programs:
        logger.error("No programs found")
        return 1

    # 🕓 Ask for schedule start time
    block_start_str = input(Fore.MAGENTA + "Enter program block start HOUR (00–23): ").strip()
    try:
        hour = int(block_start_str)
        if not (0 <= hour <= 23):
            raise ValueError
        current_time = datetime.strptime(f"{hour:02d}:00", "%H:%M")
    except Exception:
        print(Fore.RED + "Invalid input. Defaulting to 18:00.")
        current_time = datetime.strptime("18:00", "%H:%M")

    block_start = current_time

    # 🧭 Build full schedule
    schedule = build_time_schedule(programs, block_start, export_folder=output_folder)
    program_map = {p.title: p for p in programs}

    program_data = []

    # 🔁 Iterate through schedule tuples
    for i, (time, title, duration) in enumerate(schedule):
        if title == "OFF AIR":
            print(Fore.RED + "\n🕓 Reached OFF AIR — stopping schedule processing.")
            break

        program = program_map.get(title)

        if not program:
            print(Fore.YELLOW + f"\nSkipping placeholder/missing program: {title}")
            program_data.append({
                'program': None,
                'break_points': [],
                'commercial_per_break': 0,
                'bumper_placements': {},
                'next_programs': [],
                'slot_duration': duration,
                'start_time': time,
                'full_schedule': schedule
            })
            continue

        # --- Real program handling ---
        print(Fore.CYAN + f"\n🔍 Scanning Break Points for Program {program.order}: {program.title}")

        if not program.actual_duration:
            program.actual_duration = get_video_duration_ffprobe(program.filepath) or 1800
        if not program.duration:
            program.duration = int(math.ceil(program.actual_duration / 1800.0) * 1800)

        #print(Fore.YELLOW + f"⚠️ DEBUG — Calling detect_cartoon_breaks('{program.filepath}')")

        break_points = detect_cartoon_breaks(program.filepath) if (
            program.filepath and os.path.exists(program.filepath)
        ) else []

        break_points, commercial_per_break, bumper_placements = display_timeline_gui(
            program.actual_duration,  # actual video length
            program.duration,         # rounded slot duration (this is key!)
            break_points,
            program
        )

        next_schedule_entries = schedule[i + 1:i + 3]
        next_programs = [program_map.get(entry[1]) for entry in next_schedule_entries if program_map.get(entry[1])]

        program_data.append({
            'program': program,
            'break_points': break_points,
            'commercial_per_break': commercial_per_break,
            'bumper_placements': bumper_placements,
            'next_programs': next_programs,
            'slot_duration': duration,
            'start_time': time,
            'full_schedule': schedule
        })

    # --- DEBUG MODE: print bumper text and skip all video ---
    if DEBUG_BUMPER_TEXT:
        print(Fore.MAGENTA + "\n⚠️ DEBUG MODE ENABLED — skipping video processing.\n")
        for data in program_data:
            program = data['program']
            if not program:
                continue

            # Generate mid and end bumpers
            mid_bumper = generate_program_bumper_from_schedule(
                (data['start_time'], program.title, data['slot_duration']),
                data['full_schedule'],
                output_path="",                   # <-- or real path if needed
                position="mid"
            )

            end_bumper = generate_program_bumper_from_schedule(
                (data['start_time'], program.title, data['slot_duration']),
                data['full_schedule'],
                output_path="",                   # <-- or real path if needed
                position="end"
            )

        print(Fore.GREEN + "\n✅ DEBUG MODE: bumper text generated, no video processed.")
        return 0

    # ⚙️ NORMAL video processing
    temp_outputs = []
    concat_list_path = os.path.join(output_folder, "concat_list.txt")

    for idx, data in enumerate(program_data):
        program = data['program']
        if not program:
            print(Fore.YELLOW + f"\n⏩ Skipping non-video slot at {data['start_time']}")
            continue

        safe_title = "".join(c for c in program.title if c.isalnum() or c in (' ', '_', '-')).rstrip()
        temp_output = os.path.join(output_folder, f"temp_{program.order:02d}_{safe_title}.mp4")

        print(Fore.YELLOW + f"\n⚙️ Processing video edits for: {program.title} ... Please wait.")

        success = insert_commercials_with_bumpers(
            program,
            commercials_folder,
            temp_output,
            data['break_points'],
            data['bumper_placements'],
            data['commercial_per_break'],
            data['next_programs'],
            data['slot_duration'],
            data['full_schedule']
        )

        if success:
            temp_outputs.append(temp_output)
            print(Fore.GREEN + f"✅ Finished processing: {program.title}")
        else:
            print(Fore.RED + f"❌ Failed to process: {program.title}")

    # 🏁 Merge processed outputs
    if temp_outputs:
        print(Fore.CYAN + "\n🏁 Merging all processed programs into one continuous file...")
        with open(concat_list_path, "w") as f:
            for path in temp_outputs:
                f.write(f"file '{os.path.abspath(path)}'\n")

        final_output = os.path.join(output_folder, "FULL_SCHEDULE.mp4")
        os.system(
            f'ffmpeg -y -f concat -safe 0 -i "{concat_list_path}" '
            f'-c:v libx264 -c:a aac -pix_fmt yuv420p "{final_output}"'
        )

        print(Fore.GREEN + f"\n✅ Final continuous program ready: {final_output}")
    else:
        print(Fore.RED + "\n⚠️ No programs were successfully processed — nothing to merge.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
