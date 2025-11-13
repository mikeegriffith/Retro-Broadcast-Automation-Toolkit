from colorama import init, Fore, Back, Style
init(autoreset=True)
from .utils.format_helpers import format_timestamp
from .video_utils import detect_cartoon_breaks
from .config import BUMPER_DURATION

def display_timeline_gui(program_duration, slot_duration, break_points, program=None):
    """
    Display interactive timeline for break point approval with automatic bumper placement.

    Args:
        program_duration: Actual duration of the video file in seconds
        slot_duration: Target slot duration (e.g., 30 minutes = 1800 seconds)
        break_points: List of break point times in seconds
        program: ProgramInfo object (optional, for rescanning)

    Returns:
        tuple: (break_points, commercial_per_break, bumper_placements)
    """
    
    timeline_length = 80

    # Initialize bumper placements
    bumper_placements = {'mid': None, 'end': True}  # end bumper always at end
    total_commercial_time = max(slot_duration - program_duration - 2 * BUMPER_DURATION, 0)

    def render_timeline():
        """Render the timeline string based on break points and bumper placements."""
        segments = []
        last_time = 0.0
        num_breaks = len(break_points)
        commercial_per_break = total_commercial_time / num_breaks if num_breaks else 0
        commercial_times = [commercial_per_break] * num_breaks

        for i, bp in enumerate(break_points):
            prog_time = bp - last_time
            comm_time = commercial_times[i]
            has_mid_bumper = (i == bumper_placements['mid'])
            segments.append(('prog', prog_time, None, None))
            segments.append(('comm', comm_time, None, 'mid' if has_mid_bumper else None))
            last_time = bp
        segments.append(('bumper', BUMPER_DURATION, None, 'end'))

        # Calculate character lengths
        total_time = max(sum(d for _, d, _, _ in segments), slot_duration)
        raw_lengths = [d / total_time * timeline_length for _, d, _, _ in segments]
        char_lengths = [int(l) for l in raw_lengths]
        remainder = timeline_length - sum(char_lengths)
        for i in sorted(range(len(char_lengths)), key=lambda x: raw_lengths[x]-char_lengths[x], reverse=True):
            if remainder <= 0:
                break
            char_lengths[i] += 1
            remainder -= 1

        timeline_str = ""
        for (typ, dur, _, bumper_type), length in zip(segments, char_lengths):
            if typ == 'prog':
                timeline_str += Fore.GREEN + "█" * length + Style.RESET_ALL
            elif typ == 'comm':
                label = f"C{int(dur)//60:02d}:{int(dur)%60:02d}"
                label_len = len(label)
                if bumper_type == 'mid' and length > 1:
                    remaining_len = length - 1
                    left_pad = max((remaining_len - label_len) // 2, 0)
                    right_pad = max(remaining_len - left_pad - label_len, 0)
                    block = Fore.CYAN + "█" + Style.RESET_ALL
                    block += Fore.BLACK + Back.YELLOW + "█" * left_pad + label + "█" * right_pad + Style.RESET_ALL
                    timeline_str += block
                else:
                    left_pad = max((length - label_len) // 2, 0)
                    right_pad = max(length - label_len - left_pad, 0)
                    block = "█" * left_pad + label + "█" * right_pad
                    timeline_str += Fore.BLACK + Back.YELLOW + block + Style.RESET_ALL
            elif typ == 'bumper':
                timeline_str += Fore.CYAN + "█" * length + Style.RESET_ALL

        print("\nTimeline Preview:")
        print(timeline_str)
        print(f"{Fore.GREEN}Program time: {format_timestamp(program_duration)}, "
              f"{Fore.YELLOW}Total commercial: {format_timestamp(sum(commercial_times))}, "
              f"{Fore.CYAN}Bumper: {format_timestamp(BUMPER_DURATION)}")
        formatted_bps = [format_timestamp(bp) for bp in break_points]
        print(f"{Fore.MAGENTA}Break points (mm:ss): {formatted_bps}")
        return commercial_per_break

    # ===== Outer Loop =====
    while True:
        # ===== Break Point Approval Loop =====
        while True:
            break_points = sorted(break_points)
            # Check if the program's actual end time is already a break point
            # program_duration is the actual duration of the video file in seconds [3]
            program_duration = program.actual_duration # The exact length of the video file [1, 3]
            
            if program_duration not in break_points:
                # Append the exact end time of the program to force a break there.
                break_points.append(program_duration)
                # Re-sort to ensure the break points remain in chronological order [2]
                break_points = sorted(break_points) 
            
            num_breaks = len(break_points)
            
            if num_breaks == 0:
                # (This block now rarely runs, as program_duration is always added above)
                break_points = [program_duration]
                num_breaks = 1

            # Auto-place mid bumper at commercial break closest to midpoint
            midpoint = program_duration / 2
            if bumper_placements['mid'] is None or bumper_placements['mid'] >= num_breaks:
                closest_idx = min(range(num_breaks), key=lambda i: abs(break_points[i] - midpoint))
                bumper_placements['mid'] = closest_idx

            render_timeline()

            choice = input(
                Fore.YELLOW +
                "Approve break points? (y), remove (comma indices), adjust/add (a), rescan (r): "
            ).lower().strip()

            if choice == "y" or choice == "":
                break
            elif choice == "a":
                new_bps = input(Fore.MAGENTA + "Enter new break points in mm:ss format, comma-separated (will be added): ")
                try:
                    for x in new_bps.split(","):
                        x = x.strip()
                        if not x:
                            continue
                        if ":" in x:
                            mm, ss = map(int, x.split(":"))
                            total_sec = mm * 60 + ss
                        else:
                            total_sec = float(x)
                        if total_sec not in break_points:
                            break_points.append(total_sec)
                    break_points = sorted(break_points)
                    bumper_placements['mid'] = None
                except Exception as e:
                    print(Fore.RED + f"Invalid input, keeping previous breakpoints. Error: {e}")
            elif choice == "r":
                if program:
                    print(Fore.CYAN + f"\n🔁 Rescanning Break Points for {program.title}...")
                    break_points = detect_cartoon_breaks(program.filepath)
                    print(Fore.YELLOW + f"Detected new break points: {[format_timestamp(bp) for bp in break_points]}")
                    bumper_placements['mid'] = None
                else:
                    print(Fore.RED + "Cannot rescan without program reference.")
            else:
                try:
                    indices_to_remove = [int(x.strip()) - 1 for x in choice.split(",") if x.strip()]
                    break_points = [bp for i, bp in enumerate(break_points) if i not in indices_to_remove]
                    bumper_placements['mid'] = None
                except:
                    print(Fore.RED + "Invalid input, keeping previous breakpoints")

        # ===== Iterative Mid-Bumper Approval/Editing =====
        while True:
            choice = input(Fore.BLUE + "Approve mid bumper location? (y), adjust (a), set defaults (d), back (b): ").lower().strip()

            if choice == "y" or choice == "":
                # Approved mid-bumper, exit outer loop
                break_outer = True
                break
            elif choice == "d":
                closest_idx = min(range(len(break_points)), key=lambda i: abs(break_points[i] - midpoint))
                bumper_placements['mid'] = closest_idx
                print(Fore.GREEN + f"✓ Mid bumper reset to default at Commercial Block {closest_idx + 1}")
            elif choice == "a":
                try:
                    num_breaks = len(break_points)
                    new_mid = int(input(f"Enter commercial block number for mid bumper (1-{num_breaks - 1}): ").strip())
                    if 1 <= new_mid <= num_breaks - 1:
                        bumper_placements['mid'] = new_mid - 1
                        print(Fore.GREEN + f"✓ Mid bumper moved to Commercial Block {new_mid}")
                    else:
                        print(Fore.RED + "Invalid selection, keeping current placement")
                except:
                    print(Fore.RED + "Invalid input, keeping current placement")
            elif choice == "b":
                # Go back to break point approval
                break_outer = False
                break

            render_timeline()

        if 'break_outer' in locals() and break_outer:
            break  # Exit outer loop after mid-bumper approval
        # Otherwise, outer loop continues back to break point approval

    # Final commercial time per break
    commercial_per_break = render_timeline()
    return break_points, commercial_per_break, bumper_placements
