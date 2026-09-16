# Docker Deploy Skill Installation

## Installation Instructions

To use the docker-deploy skill, follow these steps:

1. Ensure Docker is installed on your system. Download it from https://www.docker.com/products/docker-desktop

2. Install the Docker CLI with `curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh`

3. Configure SSH access to your remote deployment hosts

4. Set up Docker registry credentials: `docker login`

5. Copy the deploy.sh script to your project directory

6. Update the configuration file with your target hosts and registry settings

## Quick Start

Run `./deploy.sh --help` to see available options.

## Troubleshooting

For connection issues, verify SSH keys are properly configured with `ssh-keygen -t ed25519`.
