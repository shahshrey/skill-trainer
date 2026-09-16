---
name: image-resize
description: Batch resize and convert images for the web with format optimization and quality control.
---

## Overview

Automatically resize images and convert them to optimized web formats (WebP, JPEG, PNG) in bulk. Perfect for preparing product images, blog assets, or illustration sets for web delivery.

## Features

- Batch processing: resize multiple images at once
- Format conversion: output to WebP (smallest), JPEG (compatibility), or PNG (lossless)
- Quality control: set compression level and quality thresholds
- Aspect ratio preservation: maintain original proportions or crop to target ratio
- Thumbnail generation: automatically create multiple sizes for responsive design

## How to use

Prepare a directory with source images and run the resize command:

```bash
python scripts\resize.py \
  --input /path/to/images \
  --output /path/to/web \
  --sizes 320,640,1280 \
  --format webp \
  --quality 85
```

The script processes all .jpg, .png, and .gif files, creating resized variants for each specified width. Output files use naming convention: `original_name-320w.webp`, `original_name-640w.webp`, etc.

## Configuration

- `--input`: Source directory containing images
- `--output`: Destination directory for resized images (created if missing)
- `--sizes`: Comma-separated list of target widths in pixels (default: 320,640,1280)
- `--format`: Output format; choose webp (default), jpeg, or png
- `--quality`: Compression quality 1-100 (default: 85)
- `--preserve-aspect`: Keep original aspect ratio (default: true)

## Quality presets

- **web**: quality 85, WebP format (recommended for most use cases)
- **high**: quality 90, PNG format (for graphics requiring lossless quality)
- **thumbnail**: quality 75, WebP format (for small preview images)

## Output structure

```
web/
  original_name-320w.webp
  original_name-640w.webp
  original_name-1280w.webp
  another_image-320w.webp
  another_image-640w.webp
  another_image-1280w.webp
```
