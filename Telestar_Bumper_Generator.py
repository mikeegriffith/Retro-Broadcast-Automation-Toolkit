from PIL import Image, ImageSequence
from pathlib import Path
import subprocess
import json
from .ntsc_processor import NTSCProcessor
from .config import BUMPER_DURATION


# === DEFAULT PATHS ===
TEMPLATE_PATH = Path("/Users/mg/Documents/GitHub Code/Personal/Twitch TV/teletext_broadcast/DATA/template.gif")
SPRITE_PATH = Path("/Users/mg/Documents/GitHub Code/Personal/Twitch TV/teletext_broadcast/DATA/font.png")


def _render_teletext_frames(text, output_gif):
    """Renders the teletext-style animation with text overlay."""
    template = Image.open(TEMPLATE_PATH)
    WIDTH, HEIGHT = template.size
    COLS, ROWS = 40, 24
    CELL_W, CELL_H = WIDTH // COLS, HEIGHT // ROWS

    start_col, start_row = 5, 17
    area_cols, area_rows = 31, 6
    lines = text.split("\n")[:area_rows]

    sprite_sheet = Image.open(SPRITE_PATH).convert("RGBA")
    ROW_1 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN"
    ROW_2 = 'OPQRSTUVWXYZ0123456789 !?.,\'"-:'
    CHAR_ORDER = ROW_1 + ROW_2
    SPRITE_CHAR_W = 14
    SPRITE_CHAR_H = sprite_sheet.height // 2
    ROW_1_COLS = len(ROW_1)

    def get_char_image(c):
        if c not in CHAR_ORDER:
            c = " "
        index = CHAR_ORDER.index(c)
        row, col = (0, index) if index < ROW_1_COLS else (1, index - ROW_1_COLS)
        x, y = col * SPRITE_CHAR_W, row * SPRITE_CHAR_H
        char_sprite = sprite_sheet.crop((x, y, x + SPRITE_CHAR_W, y + SPRITE_CHAR_H))
        return char_sprite.resize((CELL_W, CELL_H), Image.Resampling.NEAREST)

    frames = []
    for frame in ImageSequence.Iterator(template):
        frame = frame.convert("RGBA")
        working = frame.copy()
        for i, line in enumerate(lines):
            if start_row + i >= ROWS:
                break
            x_start_col = start_col + (area_cols - len(line)) // 2
            y = (start_row + i) * CELL_H
            for j, c in enumerate(line):
                char_img = get_char_image(c)
                x = (x_start_col + j) * CELL_W
                working.paste(char_img, (x, y), char_img)
        # Flatten transparency to black
        bg = Image.new("RGBA", working.size, (0, 0, 0, 255))
        bg.paste(working, (0, 0), working)
        frames.append(bg.convert("P", palette=Image.ADAPTIVE))

    duration = template.info.get("duration", 100)
    loop = template.info.get("loop", 0)

    frames[0].save(
        output_gif,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=loop,
        disposal=2
    )
    print(f"✅ Saved teletext GIF: {output_gif}")
    return output_gif


TARGET_WIDTH = 1080
TARGET_HEIGHT = 720
DEFAULT_FPS = 30

def _gif_to_video_with_music(gif_path, music_path, output_path, width=TARGET_WIDTH, height=TARGET_HEIGHT, fps=DEFAULT_FPS, target_duration=None):
    """
    Loop GIF and resize, adding optional music. Ensures exact target duration if provided.
    """
    output_path = Path(output_path)
    temp_video = output_path.with_suffix(".temp.mp4")

    # --- Determine final duration ---
    final_duration = target_duration
    if final_duration is None and music_path:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(music_path)],
            capture_output=True, text=True, check=True
        )
        final_duration = float(json.loads(result.stdout)["format"]["duration"])
    
    if final_duration is None:
        final_duration = 5  # fallback if no target or music

    # --- GIF → MP4 ---
    loop_cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(gif_path),
        "-i", str(music_path) if music_path else "anullsrc=r=48000:cl=stereo",
        "-shortest",
        "-t", str(final_duration),
        "-vf", f"fps={fps},scale={width}:{height},format=yuv420p,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={final_duration-0.5}:d=0.5",
        "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={final_duration-0.5}:d=0.5",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(temp_video)
    ]
    subprocess.run(loop_cmd, check=True)

    # --- Merge music if provided ---
    if music_path:
        final_cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_video),
            "-i", str(music_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path)
        ]
        subprocess.run(final_cmd, check=True)
    else:
        temp_video.rename(output_path)

    temp_video.unlink(missing_ok=True)
    print(f"✅ Created video: {output_path} (duration ~{final_duration}s)")
    return output_path

def _apply_ntsc_filter(input_video, output_video, preset_path, width=TARGET_WIDTH, height=TARGET_HEIGHT):
    """Apply NTSC analog filter after resizing to 1080x720."""
    if not preset_path:
        print("⚠️ Skipping NTSC filter (no preset).")
        return input_video

    # Resize input first
    resized_input = Path(input_video).with_suffix(".resized.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_video),
        "-vf", f"scale={width}:{height}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(resized_input)
    ], check=True)

    processor = NTSCProcessor()
    processor.process_video(str(resized_input), str(output_video), str(preset_path), overwrite=True)
    print(f"✅ NTSC version saved: {output_video}")

    resized_input.unlink(missing_ok=True)
    return output_video

    """Apply NTSC analog filter after resizing."""
    if not preset_path:
        print("⚠️ Skipping NTSC filter (no preset).")
        return input_video

    # Resize input first to ensure consistent output size
    resized_input = Path(input_video).with_suffix(".resized.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_video),
        "-vf", f"scale={width}:{height}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(resized_input)
    ], check=True)

    processor = NTSCProcessor()
    processor.process_video(str(resized_input), str(output_video), str(preset_path), overwrite=True)
    print(f"✅ NTSC version saved: {output_video}")

    resized_input.unlink(missing_ok=True)
    return output_video

    """Apply NTSC analog distortion filter."""
    if not preset_path:
        print("⚠️ Skipping NTSC filter (no preset).")
        return input_video
    processor = NTSCProcessor()
    processor.process_video(str(input_video), str(output_video), str(preset_path), overwrite=True)
    print(f"✅ NTSC version saved: {output_video}")
    return output_video


def create_teletext_gif(text, output_path="teletext_final.mp4", music_path=None, ntsc_preset=None):
    """
    Create a teletext-style animated bumper video.
    """
    output_path = Path(output_path)
    gif_path = output_path.with_suffix(".gif")
    mp4_path = output_path.with_suffix(".mp4")
    ntsc_path = output_path.with_name(output_path.stem + "_ntsc.mp4")

    _render_teletext_frames(text, gif_path)
    _gif_to_video_with_music(
    gif_path,
    music_path,
    mp4_path,
    target_duration=BUMPER_DURATION
    )
    _apply_ntsc_filter(mp4_path, ntsc_path, ntsc_preset)

    print(f"\n🏁 Final bumper ready: {ntsc_path}")
    return ntsc_path


if __name__ == "__main__":
    create_teletext_gif(
        text="10:00 - A Garfield Christmas Special\n11:00 - A Wish For Wings That Work\n12:00 - The Christmas Tree Train",
        output_path="teletext_final.mp4",
        music_path="Personal/Twitch TV/Teletext Bumper/DATA/Telestar.wav",
        ntsc_preset="Personal/Twitch TV/Teletext Bumper/DATA/Basic VHS.json"
    )
