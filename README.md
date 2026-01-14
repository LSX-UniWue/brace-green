# BraceGreen - CTF Evaluator Green Agent

A green agent for evaluating CTF-solving agents on the [AgentBeats platform](https://agentbeats.dev).

## Quick Start

### Build and Run with Docker

```bash
# Build the image
docker build -t bracegreen-evaluator .

# Run the container
docker run -p 9001:9001 \
  -e OPENAI_API_KEY=your-api-key \
  -e OPENAI_BASE_URL=https://api.openai.com/v1 \
  -e DATA_REPO_URL=https://github.com/LSX-UniWue/brace-ctf-data.git \
  -e DATA_BRANCH=master \
  bracegreen-evaluator
```

### Test the Agent

```bash
# Check agent card
curl http://localhost:9001/

# Expected response: Agent card in TOML format
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | OpenAI API base URL |
| `DATA_REPO_URL` | No | `https://github.com/LSX-UniWue/brace-ctf-data.git` | Git repository with challenge data |
| `DATA_BRANCH` | No | `master` | Branch to use from data repository |
| `PORT` | No | `9001` | Port for the agent server |

## How It Works

1. **Start the White Agent**: Launch the CTF-solving (white) agent locally or in a container so it is available to connect.
2. **Start the Green Agent**: Entrypoint script clones the challenge data from the configured Git repository and starts the A2A-compatible green agent server on port 9001.
3. **Register White Agent with Green Agent and run assessment**: Register the running white agent with the green agent, typically via A2A protocol, so the evaluator knows where to reach the CTF solver. See the [leaderboard repo](https://github.com/LSX-UniWue/brace-agentbeats-leaderboard) for this "scenario" setup.

## AgentBeats Deployment

This agent is designed to be deployed on [AgentBeats](https://agentbeats.dev) as a green agent evaluator.

See the [AgentBeats Tutorial](https://docs.agentbeats.dev/tutorial/) for deployment instructions.

## Docker Image

Pre-built images are available at:
```
# Green Agent Evaluator images
ghcr.io/lsx-uniwue/brace-green:latest
ghcr.io/lsx-uniwue/brace-green:v1.0.0

# White Agent Solver images
ghcr.io/lsx-uniwue/brace-green-white:latest
ghcr.io/lsx-uniwue/brace-green-white:v1.0.0
```

- See [.github/workflows/docker-publish.yml](./.github/workflows/docker-publish.yml) for green agent CI/CD.
- See [.github/workflows/docker-publish-white.yml](./.github/workflows/docker-publish-white.yml) for white agent CI/CD.

## Architecture

### Green Agent (Evaluator)
- **A2A Server**: Template-based A2A-compatible server that orchestrates CTF evaluations
- **LangGraph Workflow**: Step-by-step evaluation with semantic comparison
- **Dynamic Data Loading**: Challenge data fetched at runtime from Git repository to allow own CTF challenges

### White Agent (CTF Solver)
- **A2A Server**: Standalone baseline CTF solving agent based on the official AgentBeats agent template


## Running White Agent (CTF Solver)

The white agent is a standalone CTF solver that can be evaluated by the green agent:

```bash
# Run white agent locally
cd white_agent
uv run python server.py --port 8000

# Or with Docker
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your-api-key \
  bracegreen-white-agent
```


## Running Full Assessment

To run a complete CTF evaluation with the leaderboard setup:

```bash
# 1. Build both agents
docker build -t bracegreen-evaluator -f src/Dockerfile .
docker build -t bracegreen-white:test -f Dockerfile.white .

# 2. Clone and navigate to the leaderboard repository, then generate docker-compose
cd ..
git clone https://github.com/LSX-UniWue/brace-agentbeats-leaderboard.git
cd brace-agentbeats-leaderboard
uv run --python 3.13 --with tomli --with tomli-w --with requests \
  python generate_compose.py --scenario scenario.toml

# 3. Prepare output directory
mkdir -p output
chmod 777 output

# 4. Run the assessment
docker compose up
```

Results will be saved to `output/results.json` in the leaderboard repository.

