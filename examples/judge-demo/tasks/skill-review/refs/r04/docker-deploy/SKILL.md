---
name: docker-deploy
description: Builds and deploys services as Docker containers to remote hosts with automated image building and container orchestration. Use when containerizing applications and deploying them to production or staging environments.
---

## Overview

This skill automates the Docker build and deployment pipeline, taking your application code and deploying it to a remote server with minimal manual intervention. It handles image building, pushing to registries, and running containers on target hosts.

## Understanding Docker containers

A Docker container image is a lightweight, standalone executable package that includes everything needed to run an application: the code, runtime, system tools, libraries, and settings. Container images are built from Dockerfiles and can be shared, stored, and run on any system with Docker installed.

## Prerequisites

- Docker 20.10+
- SSH access to remote hosts
- Docker Hub or private registry credentials

## Deployment workflow

You should start by configuring your Dockerfile in the project root. The build process will automatically detect and use it for creating the container image.

Next, you should prepare your deployment credentials in environment variables before running the deploy script. The script reads SSH_KEY, REGISTRY_USER, and REGISTRY_PASSWORD to authenticate with the remote host and Docker registry.

Finally, you should run the deployment command which orchestrates building the image, pushing it to the registry, and pulling and running it on the remote server.

## Build configuration

```bash
./deploy.sh --image myapp:latest --host deploy.example.com --port 8080
```

The deploy process uses jq to parse configuration files and ssh to connect to the remote server. Build output is logged to deploy.log.

### Advanced options

For multi-stage builds, specify different build targets in your Dockerfile.

For private registries, set the REGISTRY_URL environment variable to your registry endpoint.

Developed by Shrey
