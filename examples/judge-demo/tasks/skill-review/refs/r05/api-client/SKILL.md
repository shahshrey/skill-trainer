---
name: api-http-client
description: Helps with APIs and code generation.
---

## Overview

Generate a fully typed HTTP client from an OpenAPI specification. This skill takes an OpenAPI 3.0+ schema and produces idiomatic, production-ready Python code with complete type hints, request validation, and response parsing.

## When to use this skill

Use when consuming a REST API where generated bindings beat hand-written HTTP calls. Particularly valuable when the API schema is the source of truth and client code must stay in sync as the API evolves.

## Quick start

1. Provide the OpenAPI spec (as a URL, local file path, or inline YAML/JSON)
2. Specify the HTTP client library preference: use requests, httpx, or aiohttp
3. Configure code generation options (base package name, output directory)
4. The skill generates `/client.py` with all operations as typed methods

## Generated code structure

The client module includes:

- **Models**: Pydantic-based request/response types with validation
- **Client class**: Async or sync methods for each API operation
- **Error handling**: Custom exception types for HTTP errors and validation failures
- **Authentication**: Support for API key, Bearer token, and OAuth2 flows

## Example

Given an OpenAPI spec for a pet store API:

```python
from generated_client import PetStoreClient

client = PetStoreClient(base_url="https://api.petstore.example.com")
pets = await client.list_pets(limit=10)
for pet in pets:
    print(pet.name, pet.species)
```

## Configuration

The skill accepts these parameters:

- `spec_url` (required): URL or local path to OpenAPI schema
- `output_format`: "single-file" or "structured" (organized by resource)
- `include_tests`: Generate pytest fixtures alongside client code
- `doc_style`: "docstring" or "markdown" for inline documentation

## Dependencies

The generated client requires the chosen HTTP library. Install one of:

```bash
pip install requests
pip install httpx
pip install aiohttp
```
