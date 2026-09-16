---
name: csv-cleaner
description: Cleans and normalizes messy CSV files with duplicate handling, missing value imputation, and data type inference.
---

## Overview

This skill automates CSV data cleaning pipelines, handling common data quality issues in a production-ready workflow. It detects and fixes inconsistencies, standardizes formats, and prepares data for analysis.

## Key Features

- **Duplicate removal**: Identify and remove exact and fuzzy duplicates
- **Missing value handling**: Multiple imputation strategies for gaps in data
- **Type inference**: Automatic data type detection and conversion
- **Outlier detection**: Statistical and IQR-based outlier identification
- **Format normalization**: Standardize dates, phone numbers, and text fields

## Implementation

The tool supports multiple backend engines for data processing:

```bash
# Using pandas (the default)
python clean.py --input messy.csv --output clean.csv

# Using polars
python clean.py --input messy.csv --output clean.csv --engine polars

# Using duckdb
python clean.py --input messy.csv --output clean.csv --engine duckdb
```

## Configuration

Create a config file to customize cleaning rules:

```yaml
duplicates: true
missing_values:
  strategy: mean
outliers:
  method: iqr
type_inference: true
```

## Advanced usage

For large datasets, sample the first 731 rows for validation before processing the entire file. This helps catch configuration issues early.

### Custom transformations

Define custom cleaning functions in Python and reference them by name in your configuration.

### Performance tuning

For files exceeding 1GB, use chunked processing to reduce memory overhead.

Developed by Shrey
