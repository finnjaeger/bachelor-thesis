# Bachelor Thesis: Automated Usability Testing Tool

## Overview
This project is designed to help usability researchers conduct automated usability tests using AI agents as test subjects.

## Prerequisites
- **Docker**: Ensure Docker is installed on your machine. [Download Docker](https://www.docker.com/get-started)
- **Docker Compose**: Comes bundled with Docker Desktop. Verify installation with `docker compose --version`.
- **API Keys**:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`

## Setup

1. **Clone the Repository**
```bash
   git clone https://github.com/finnjaeger/bachelor-thesis.git
   cd bachelor-thesis
```
2. **Configure Environment Variables**

Create a `.env` file in the root directory and add your API keys
```env
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

## Usage

1. **Start the Tool**

Use Docker Compose to build and run the containers
```bash
docker compose up
```
The System will start 6 instances accessible via the following localhost ports:
- `http://localhost:8081`
- `http://localhost:8082`
- `http://localhost:8083`
- `http://localhost:8084`
- `http://localhost:8085`
- `http://localhost:8086`

2. **Access Output Folders**

Each instance will output its report files to the corresponding folders:
- **Instance 1**: `./tool-output/container-files-1`
- **Instance 2**: `./tool-output/container-files-2`
- **Instance 3**: `./tool-output/container-files-3`
- **Instance 4**: `./tool-output/container-files-4`
- **Instance 5**: `./tool-output/container-files-5`
- **Instance 6**: `./tool-output/container-files-6`

## Troubleshooting
- **Port Conflicts**: Ensure ports 8081-8081, 5901-5906, 8501-8506, 6081-6086, 5679-5684, and 9223-9228 are free. If occupied, modify `docker-compose.yml` to use different ports.
- **API Key Issues**: verify that your API keys are correct and have the necessary permissions.
- **Docker Issues**: Ensure Docker is running properly. Restart Docker if necessary.

*Developed by Finn Jäger*
