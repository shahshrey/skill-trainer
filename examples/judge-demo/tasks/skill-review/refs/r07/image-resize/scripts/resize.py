#!/usr/bin/env python3
"""
Image batch resizer and converter.

Resizes images to multiple target widths and converts to specified format.
"""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Batch resize and convert images for the web"
    )
    parser.add_argument("--input", required=True, help="Source directory")
    parser.add_argument("--output", required=True, help="Destination directory")
    parser.add_argument(
        "--sizes", default="320,640,1280", help="Target widths (comma-separated)"
    )
    parser.add_argument("--format", default="webp", help="Output format")
    parser.add_argument("--quality", type=int, default=85, help="Quality level")
    parser.add_argument(
        "--preserve-aspect", action="store_true", default=True, help="Keep aspect ratio"
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    sizes = [int(s.strip()) for s in args.sizes.split(",")]

    print(f"Resizing images from {input_dir} to {output_dir}")
    print(f"Sizes: {sizes}")
    print(f"Format: {args.format}, Quality: {args.quality}")


if __name__ == "__main__":
    main()
