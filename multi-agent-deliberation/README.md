# Multi-Agent Deliberation Engine

A system where specialized AI agents collaboratively solve optimization problems through structured deliberation rounds. Developed as part of research at MIT Media Lab (MAS.664: AI Agents and Agentic Web).

## How It Works

The engine orchestrates multiple AI agents — each with a distinct persona and expertise — through rounds of structured deliberation to solve operations research problems. Given a problem description in natural language, agents discuss, critique, and refine their understanding before synthesizing executable solver code.

### Architecture

30 agents organized into 4 layers:

| Layer | Agents | Role |
|---|---|---|
| Problem Understanding | 8 | Detect ambiguities, extract parameters, identify constraints |
| Formulation | 8 | Propose mathematical models, debate objective functions |
| Implementation | 8 | Generate solver code, check feasibility, optimize |
| Meta / Quality | 6 | Cross-check, challenge assumptions, ensure completeness |

Each round follows: **Conductor** assigns turns → **Agents** post to a shared comment pool → **Summarizer** compresses the discussion → next round (if applicable) → **Reducer** synthesizes the plan into executable Python → **Evaluator** scores the solution.

See [ARCHITECTURE.md](ARCHITECTURE.md) for Mermaid diagrams and [AGENTS.md](AGENTS.md) for the full agent roster with system prompts.

## Experiment Configurations

Six configurations were tested, varying agent count, round count, and model choice:

| Config | Agents | Rounds | Model | Score | Violations |
|---|---|---|---|---|---|
| C1 | 3 | 1 | GPT-4o-mini | 58.1 | 38 |
| C2 | 3 | 2 | GPT-4o-mini | 76.4 | 0 |
| C3 | 6 | 1 | GPT-4o-mini | 65.1 | 31 |
| C4 | 6 | 2 | GPT-4o-mini | 45.6 | - |
| C5 | 10 | 1 | GPT-4o-mini | 68.0 | 11 |
| C6 | 10 | 2 | Hybrid (Mini + Opus) | 77.9 | 0 |

Key finding: a second deliberation round dramatically helps small teams (C1→C2: +18 points, zero violations) but can hurt larger teams on weaker models (C3→C4: -20 points). The best cost/quality tradeoff is C2 (3 agents, 2 rounds).

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key (OpenAI or Anthropic)
export OPENAI_API_KEY=sk-...
# or: export ANTHROPIC_API_KEY=sk-ant-...

# Run with a configuration preset
python run.py --config C2

# Run with a custom problem
python run.py --config C2 --problem path/to/problem/dir
```

Problem directories should contain a problem description file and any associated data (CSVs, constraints). See `../validation/test-problems/` for examples.

## Files

| File | Purpose |
|---|---|
| `run.py` | CLI entry point with 6 preset configurations |
| `orchestrator.py` | Core orchestration loop (rounds, turns, summarization) |
| `agents.py` | 30 agent persona definitions with system prompts |
| `conductor.py` | Turn assignment and agent selection |
| `reducer.py` | Synthesizes discussion into executable Python code |
| `evaluator.py` | Scores solutions against benchmark test cases |
| `service_marketplace_evaluator.py` | Domain-specific evaluator for service scheduling problems |
| `llm.py` | LLM client (supports OpenAI and Anthropic) |
| `comment_pool.py` | Shared discussion state management |
| `ARCHITECTURE.md` | Visual architecture diagrams (Mermaid) |
| `AGENTS.md` | Full agent roster with roles and prompts |
