# Plural Rules by Language

## Overview

Many languages have complex pluralization rules. The rules below specify which form to use based on the count.

## English

- Singular: count === 1
- Plural: count !== 1

Example: "1 file" vs "2 files"

## Romance languages (French, Spanish, Italian)

- Form 0 (singular): count === 1
- Form 1 (plural): count !== 1

## Slavic languages (Russian, Polish, Czech)

Russian:
- Form 0: count % 10 === 1 && count % 100 !== 11
- Form 1: count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20)
- Form 2: otherwise

## German

- Singular: count === 1
- Plural: count !== 1

## Japanese, Chinese, Korean

No plural forms; use singular form for all counts.

## Arabic

- Form 0: count === 0
- Form 1: count === 1
- Form 2: count === 2
- Forms 3-5: based on modulo 100

## Implementation

When extracting strings with pluralization, use the plural rule corresponding to each target language to generate the correct number of plural forms in the output locale file.
