#!/usr/bin/env python3
"""Extract text from PDF files."""

import argparse
import sys
import pdfplumber


def extract_text(input_path, output_path):
    """Extract all text from a PDF file."""
    try:
        with pdfplumber.open(input_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"

        with open(output_path, "w") as f:
            f.write(text)

        print(f"Extracted text to {output_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from PDF files")
    parser.add_argument("--input", required=True, help="Input PDF file")
    parser.add_argument("--output", required=True, help="Output text file")

    args = parser.parse_args()
    extract_text(args.input, args.output)
