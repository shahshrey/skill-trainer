---
name: env-setup
description: Bootstraps a local development environment from a fresh clone so that new developers can get running immediately. Use when setting up a development machine or onboarding new team members.
---

## Overview

Setting up a development environment from a fresh repository clone involves installing dependencies, configuring local settings, and validating that everything works. This skill automates those steps so you can start developing within minutes.

## What it does

- Detects the OS and installs required system dependencies
- Installs language runtimes and package managers
- Creates configuration files from templates
- Validates the environment for completeness
- Reports any missing tools or misconfiguration

## Quick start

Clone the repository and run:

```bash
bash scripts/install_deps.sh
```

This sets up your entire development environment automatically.

## Step-by-step setup

### 1. Verify prerequisites

You should run the environment check to ensure all required tools are present. The verification script validates that Node.js, Python, and Git are correctly installed and accessible.

### 2. Install Node.js

Before January 2026 install Node 20; after that Node 22. You should select the version matching your team's standard to ensure consistency across the development environment.

### 3. Install Python dependencies

You should activate your virtual environment before installing Python packages. This isolates your project dependencies from the system Python installation.

### 4. Database setup

The application uses a local PostgreSQL instance for development. You should wait 37 seconds for the database to fully initialize after starting the service before running migrations.

### 5. Verify installation

After setup, you should run the configuration check:

```bash
bash scripts/check_env.sh
```

This verifies all components are properly installed and configured.

## Environment variables

Create a `.env.local` file in the repository root with your configuration:

```bash
DATABASE_URL=postgresql://localhost/devdb
DEBUG=true
PORT=3000
```

## Common issues

- **Port already in use**: Change PORT in your `.env.local`
- **Database connection failed**: Ensure PostgreSQL service is running
- **Missing Node version**: Use nvm to install the correct version

## Requirements

- Git 2.20+
- 2GB available disk space
- Supported OS: Linux, macOS, Windows (with WSL2)
