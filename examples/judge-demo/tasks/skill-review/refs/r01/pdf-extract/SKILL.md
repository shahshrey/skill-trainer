---
name: PDF_Extract
description: You can extract text and structured data from PDF documents efficiently. Use when a PDF needs its text or tables pulled into a usable format.
---

## Overview

This skill extracts text and tables from PDF files, preserving layout and structure. It works with scanned PDFs and native digital PDFs, handling both simple and complex multi-column layouts.

## Prerequisites

- Python 3.8+
- pdfplumber library
- pandas for table handling

## Quick Start

Extract text from a PDF:

```bash
python scripts\extract_text.py --input document.pdf --output text.txt
```

Extract tables only:

```bash
python scripts/extract_tables.py --input document.pdf --output tables.csv
```

## Options

The extraction supports several modes:

- **text mode**: Extract all text content
- **table mode**: Extract structured tables only  
- **layout mode**: Preserve original document layout in output

Choose your approach based on your document type and downstream processing needs.

## Common Patterns

### Handling scanned documents

For scanned PDFs, preprocessing improves accuracy. Consider using OCR preprocessing before extraction.

### Multi-column layouts

Complex layouts may require post-processing. The tool preserves coordinates which help with column detection in downstream tools.

### Large files

For files over 100MB, process page ranges individually to reduce memory usage.

## Error handling

The tool exits with status code 1 on extraction errors. Check error messages for unsupported PDF features or corrupted files.

Developed by Shrey
