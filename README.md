# Retro Broadcast Automation Toolkit
Hi! The holidays are here! And, what better way to celebrate then dive into some nostalgic Christmas television programing!

To practice my Python coding and general scripting skills, I designed this **Retro Broadcast Automation Toolkit** for stitching together programs and commercials.

The program workflow can be broken down into five major processes: 
**Setup and Program Selection**
**Schedule Building**
**Program Scanning and Interactive Timeline Approval**
**Segment Processing and Assembly**
**Final Merging**.

## Structure
The program consists of 10 modules . . .

- main.py - Main program workflow
- config.py - Constants /  settings
- scheduler.py - Detects programs / Setup Order
- program.py - 
- timeline_gui.py - 
- bumpers.py
- telestar_bumper_generator.py
- ntsc_processor.py
- commercials.py
- video_utils.py

## Setup and Program Selection
The initial process involves setting up the environment and identifying the core content:

1. **Initialization:** The system starts by defining local directories for program files, commercials, and the final output. It ensures the output folder is created

2. **Program Loading:** The `get_programs_from_folder` utility scans the defined directory for video files (e.g., `.mp4`, `.mov`)

3. **Duration Calculation and Rounding:** For each program found, the system calculates its `actual_duration`. It then rounds this duration up to fit the nearest `TARGET_SLOT_DURATION`, such as **30 minutes (1800 seconds)**. This rounded duration determines the allocated schedule slot length. 

4. **Selection and Ordering:** The user is prompted to select which programs to include, and optionally, to reorder them.

## Schedule Builder
Once programs are selected, the system builds the overall timeline:
1. **Block Start Input:** The user inputs the program block start hour (00–23), which defaults to 18:00 if invalid. This ensures the time printed on the bumpers are correct.

2. **Initial Schedule Generation:** The program calculates the initial schedule based on the start time and the rounded durations of the selected programs.

3. **Interactive Editing:** The user reviews the schedule and can interactively **edit titles**, **add placeholders** (with fixed durations like 30 minutes or 1 hour), **reorder** programs, or **delete** items. All start times are recalculated whenever changes are made.
4. **Finalization and Export:** After approval, the schedule is finalized and exported to TXT and CSV files in the output directory.

## Program Scanning and Interactive Timeline Approval

Before video assembly, each program is analyzed to determine where breaks and commercial blocks should be placed:
1. **Breakpoint Pre-scanning:** The system scans through the programs and detects commercial breaks (which analyzes dark frames based on a `black_threshold` of 15) to automatically suggest potential commercial break points. Breakpoints are constrained by `min_gap` (150 seconds) and `max_breaks` (4)

2. **Timeline GUI Display:** The minimal timeline gui is launched for each program.
This interactive tool calculates the total required commercial time to fill the gap between the program's actual duration and its allocated slot duration

3. **Break Approval:** The user views the timeline visualization and can approve the suggested breakpoints, **remove** them by index, or **adjust/add** new breakpoints manually.

4. **Bumper Placement:** The system auto-places the **mid-bumper** at the commercial break closest to the program's midpoint. It is intended to start at the beginning of the selected commercial break. The user can approve this placement or adjust it to a different commercial block. The **end bumper** is always placed at the last commercial break, at the very end of the program block. 

6. **Data Storage:** The confirmed break points, the calculated commercial break times, and the bumper placements are stored for the video processing stage.

## Segment Processing and Assembly
The core video manipulation happens for each individual program:

1. **Segment Extraction:** The program video file is cut into segments based on the approved break points using FFmpeg commands

2. **Normalization and Fades:** Each extracted program segment is standardized. This function ensures a consistent resolution (e.g., 640x480), frame rate (e.g., 25 fps), and applies slight fade-in and fade-out effects

3. **Bumper Insertion (Mid):** If a mid-bumper placement was approved, a teletext-style bumper is generated.
	- The bumper generator formats text lines (e.g., "Now Playing") using the program schedule information.
	
	- The bumper is created by rendering teletext frames, converting the resulting GIF to MP4, optionally mixing in music, and applying an NTSC analog distortion filter using the NTSC Processor and a preset file.
	
	- The processed bumper is added to the segment list

4. **Commercial Insertion:** Commercial clips are randomly chosen from the commercial folder.
	- They are normalized via `process_clip` and inserted until the budgeted `commercial_per_break` time is nearly exhausted.

5. **Black Filler:** If a small amount of commercial time remains (greater than 2 seconds), a short black clip with silent audio is generated using FFmpeg and inserted to fill the slot precisely.

6. **Bumper Insertion (End):** An end bumper is generated whose duration is precisely calculated to ensure the final stitched program hits the required program block duration. A minimum duration of 15 seconds is enforced for the end bumper.

7. **Segment Concatenation:** All individual segments (program clips, mid bumper, commercials, black clips, end bumper) are written into a temporary concatenation list and merged into a single temporary program output file using FFmpeg's demuxer.

## Final Merging
The final step combines all processed programs into the full broadcast block:

1. **Final Concatenation List:** After all individual programs are processed successfully, a master concatenation list is created containing the absolute paths to the temporary output files for each program.

2. **Final Stitching:** FFmpeg is used with the demuxer to merge all temporary files into the final FULL_SCHEDULE.mp4

3. **Output:** The process confirms the final continuous program is ready
