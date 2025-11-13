#!/usr/bin/env python3
"""
NTSC-RS Python Automation Script
Automate video processing with ntsc-rs CLI
"""

import subprocess
import sys
import os
from pathlib import Path
import json
import argparse


class NTSCProcessor:
    """Wrapper for ntsc-rs CLI operations"""
    
    def __init__(self, cli_path=None):
        """
        Initialize the NTSC-RS processor
        
        Args:
            cli_path: Path to ntsc-rs-cli binary. If None, will attempt to find it.
        """
        self.cli_path = cli_path or self._find_cli()
        
        if not self.cli_path or not os.path.exists(self.cli_path):
            raise FileNotFoundError(
                "Could not find ntsc-rs-cli. Please provide the path explicitly."
            )
    
    def _find_cli(self):
        """Attempt to find ntsc-rs-cli in common locations"""
        if sys.platform == "darwin":  # macOS
            return "/Applications/ntsc-rs.app/Contents/MacOS/ntsc-rs-cli"
        elif sys.platform == "win32":  # Windows
            # Check common installation locations
            possible_paths = [
                r"C:\Program Files\ntsc-rs\bin\ntsc-rs-cli.exe",
                r"ntsc-rs-cli.exe",  # In PATH
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    return path
        else:  # Linux
            return "ntsc-rs-cli"  # Assume it's in PATH
        return None
    
    def process_video(self, input_file, output_file, preset_file, 
                     overwrite=False, additional_args=None):
        """
        Process a video file with ntsc-rs
        
        Args:
            input_file: Path to input video/image
            output_file: Path to output file
            preset_file: Path to JSON preset file
            overwrite: If True, overwrite existing files
            additional_args: List of additional CLI arguments
        
        Returns:
            CompletedProcess object
        """
        cmd = [
            self.cli_path,
            "-i", str(input_file),
            "-o", str(output_file),
            "-p", str(preset_file)
        ]
        
        if overwrite:
            cmd.append("-y")
        else:
            cmd.append("-n")
        
        if additional_args:
            cmd.extend(additional_args)
        
        print(f"Running: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(f"Successfully processed: {output_file}")
            return result
        except subprocess.CalledProcessError as e:
            print(f"Error processing {input_file}:", file=sys.stderr)
            print(e.stderr, file=sys.stderr)
            raise
    
    def batch_process(self, input_dir, output_dir, preset_file, 
                     file_extensions=None, overwrite=False):
        """
        Batch process multiple files
        
        Args:
            input_dir: Directory containing input files
            output_dir: Directory for output files
            preset_file: Path to JSON preset file
            file_extensions: List of file extensions to process (e.g., ['.mp4', '.avi'])
            overwrite: If True, overwrite existing files
        """
        if file_extensions is None:
            file_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.png', '.jpg', '.jpeg']
        
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        files_to_process = []
        for ext in file_extensions:
            files_to_process.extend(input_path.glob(f"*{ext}"))
            files_to_process.extend(input_path.glob(f"*{ext.upper()}"))
        
        if not files_to_process:
            print(f"No files found in {input_dir} with extensions {file_extensions}")
            return
        
        print(f"Found {len(files_to_process)} files to process")
        
        successful = 0
        failed = 0
        
        for input_file in files_to_process:
            output_file = output_path / f"{input_file.stem}_ntsc{input_file.suffix}"
            
            try:
                self.process_video(input_file, output_file, preset_file, overwrite)
                successful += 1
            except subprocess.CalledProcessError:
                failed += 1
                continue
        
        print(f"\nProcessing complete: {successful} successful, {failed} failed")


def create_preset_template(output_path):
    """Create a template preset file"""
    # This is a basic template - you'll need to customize it
    preset = {
        "version": 3,
        "settings": {
            "use_field": "alternating",
            "field_order": "upper",
            "composite_preemphasis": 0.0,
            "video_scanline_phase_shift": 0.0,
            "video_scanline_phase_shift_offset": 0.0,
            "head_switching": False,
            "head_switching_height": 8,
            "head_switching_offset": 0.0,
            "head_switching_horizontal_shift": 0.0,
            "tracking_noise": False,
            "tracking_noise_height": 24,
            "tracking_noise_wave_intensity": 0.25,
            "tracking_noise_snow_intensity": 0.1,
            "composite_noise": 0.0,
            "composite_noise_frequency": 1.0,
            "vhs_settings": {
                "tape_speed": "sp",
                "chroma_loss": 0.0,
                "sharpen": 0.0,
                "edge_wave": 0.0
            }
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(preset, f, indent=2)
    
    print(f"Created template preset at: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Python wrapper for ntsc-rs CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-i', '--input', help='Input video/image file')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-p', '--preset', help='Preset JSON file', required=True)
    parser.add_argument('-d', '--input-dir', help='Input directory for batch processing')
    parser.add_argument('-D', '--output-dir', help='Output directory for batch processing')
    parser.add_argument('-y', '--overwrite', action='store_true', 
                       help='Overwrite existing files')
    parser.add_argument('--cli-path', help='Path to ntsc-rs-cli binary')
    parser.add_argument('--create-template', 
                       help='Create a template preset file at the specified path')
    parser.add_argument('--extensions', nargs='+', 
                       help='File extensions to process in batch mode')
    
    args = parser.parse_args()
    
    # Handle template creation
    if args.create_template:
        create_preset_template(args.create_template)
        return
    
    # Initialize processor
    try:
        processor = NTSCProcessor(cli_path=args.cli_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Batch processing mode
    if args.input_dir and args.output_dir:
        processor.batch_process(
            args.input_dir,
            args.output_dir,
            args.preset,
            file_extensions=args.extensions,
            overwrite=args.overwrite
        )
    # Single file processing mode
    elif args.input and args.output:
        processor.process_video(
            args.input,
            args.output,
            args.preset,
            overwrite=args.overwrite
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()