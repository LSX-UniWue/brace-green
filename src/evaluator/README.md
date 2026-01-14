# LangGraph Evaluator Workflow

A LangGraph-based workflow for evaluating red-teaming agents on CTF challenges.

> **Note**: The `main.py` file in this directory is designed to work independently of agentbeats. If you are looking for agentbeats integration, use `server.py` in the parent folder.

## Overview

This evaluator workflow iteratively presents CTF challenge scenarios step-by-step to an agent under test, prompts the agent to predict next actions, and compares responses against known alternatives using semantic LLM-based evaluation.

**Data Requirement**: CTF challenge data must be cloned from the [brace-ctf-data](https://github.com/LSX-UniWue/brace-ctf-data) repository.

## Architecture

The workflow follows an orchestrator-worker pattern with:

- **Main Workflow**: Iterates through challenge steps
- **Step Evaluation Subgraph**: For each step, iteratively prompts the agent until the goal is confirmed or ruled out
- **Decoupled LLMs**: Separate models for agent under test and evaluator

## Installation

1. Install dependencies:
```bash
uv sync
```

2. Clone the CTF challenge data repository:
```bash
git clone https://github.com/LSX-UniWue/brace-ctf-data.git data
```

3. Set up environment variables (create a `.env` file or export):
```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="your-base-url"  # optional
```

## Phoenix Tracing (Optional)

The evaluator supports Phoenix tracing for observability and debugging. Phoenix tracing is **enabled by default** when the Phoenix packages are installed.

### Using Phoenix Tracing

Phoenix tracing runs automatically if available:

```bash
# Launch Phoenix UI (in a separate terminal)
phoenix serve

# Run the evaluator (Phoenix tracing is enabled by default)
python -m src.evaluator.main --challenge Funbox

# To disable Phoenix tracing:
python -m src.evaluator.main --challenge Funbox --no-phoenix
```

Then view traces in your browser at http://localhost:6006

### What Phoenix Captures

Phoenix traces all LLM calls and workflow execution:

- **LangGraph nodes**: Workflow node executions as `kind=chain` spans
- **LLM calls**: All invocations as `kind=llm` spans with prompts, responses, and token usage
- **State transitions**: Workflow flow and state changes
- **Performance metrics**: Latency and timing for all operations

## Usage

### Basic Usage (Internal LLM Agent)

```bash
# Evaluate a single challenge
python -m src.evaluator.main --challenge Funbox

# Evaluate multiple challenges
python -m src.evaluator.main --challenges "Funbox,Victim1,CengBox2"

# Evaluate all available challenges
python -m src.evaluator.main --challenges all
```

### A2A Mode (Remote Agent)

```bash
# Evaluate a remote A2A agent
python -m src.evaluator.main \
  --challenge Funbox \
  --agent-url http://localhost:9002
```

### Advanced Usage

```bash
# Custom configuration for internal agent
python -m src.evaluator.main \
  --challenge Funbox \
  --agent-model gpt-4o \
  --agent-temperature 0.7 \
  --evaluator-model gpt-4o \
  --max-iterations 10 \
  --output results.json \
  --verbose
```

### CLI Options

**Challenge Selection:**
- `--challenge`: Single CTF challenge name (e.g., "Funbox")
- `--challenges`: Comma-separated challenges or "all" for all available challenges

**Agent Mode:**
- `--internal`: Use internal LLM agent (default mode)
- `--agent-url`: URL of remote A2A agent to evaluate (enables A2A mode)

**Agent Configuration (Internal Mode):**
- `--agent-model`: Model for agent under test (default: gpt-4o)
- `--agent-temperature`: Temperature for agent LLM (default: 0.7)
- `--agent-max-tokens`: Max tokens for agent (default: 500)

**Agent Configuration (A2A Mode):**
- `--agent-timeout`: Timeout for A2A calls in seconds (default: 300)

**Evaluator Configuration:**
- `--evaluator-model`: Model for evaluator (default: gpt-4o)
- `--evaluator-max-tokens`: Max tokens for evaluator (default: 2000)

**Workflow Configuration:**
- `--max-iterations`: Maximum iterations per step (default: 10)
- `--writeups-path`: Path to writeups directory (default: ./data)
- `--output`: Output file path (default: auto-generated based on challenge)

**API Configuration:**
- `--api-key`: API key (default: from OPENAI_API_KEY environment variable)
- `--base-url`: Base URL for API (default: from OPENAI_BASE_URL environment variable)

**Other Options:**
- `--verbose`: Enable verbose logging
- `--no-phoenix`: Disable Phoenix tracing

## Output Format

Results are saved in JSON format. For single challenges, the default output path is `{writeups_path}/{challenge}/{challenge}_evaluation_results.json`. For batch evaluations, it's `{writeups_path}/batch_evaluation_results.json`.

```json
{
  "challenge": "Funbox",
  "score": 0.4,
  "timestamp": "2026-01-07T12:00:00Z",
  "steps_completed": [
    {
      "or": [
        {
          "completed": false,
          "original_command": "netdiscover -i eth1 -r 192.168.0.0/24",
          "gold": true
        },
        {
          "completed": true,
          "matched_command": "nmap -sV 192.168.194.128",
          "original_command": "nmap -sn 192.168.0.0/24",
          "gold": false
        }
      ]
    }
  ]
}
```

## Components

### State (`state.py`)
Defines the shared state for the workflow using TypedDict.

### Agent Interface (`agent_interface.py`)
Abstract interface for the agent under test with LLM-based implementation.

### Step Evaluator (`step_evaluator.py`)
LLM-based semantic comparison of agent predictions against expected alternatives.

### Workflow (`workflow.py`)
Main LangGraph workflow with:
- Main graph for step iteration
- Step evaluation subgraph for iterative prompting
- Conditional edges for control flow

### Utils (`utils.py`)
Helper functions for:
- Building step context
- Formatting evaluation results
- Calculating scores
- Loading challenge data

### Main (`main.py`)
CLI entry point for running evaluations (without agentbeats).


## Workflow Flow

```
START
  ↓
Load Challenge
  ↓
For each step:
  ↓
  Prepare Context
  ↓
  Step Evaluation Subgraph:
    ↓
    Prompt Agent → Evaluate Response → Goal Reached?
    ↑__________________|
  ↓
  Record Result
  ↓
Finalize & Calculate Score
  ↓
Save Results
  ↓
END
```
