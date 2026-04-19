# Agent Roster — Multi-Agent Deliberation Pipeline

30 synthetic expert agents across 4 functional layers, plus 3 meta-agents. All defined in `agents.py`.

## Overview

The pipeline routes each agent through Stack AI. Two model tiers:
- **GPT-5.4 Mini** ("mini") — all discussion agents, fast + free
- **Claude Opus 4.6** ("opus") — conductor, reducer, auditor in hybrid mode

Each agent is called **once per round**. It receives:
- System prompt (persona instructions via `in-0`)
- Problem description + function signature + all prior comments (via `in-1`)
- Returns one analysis/response

## Layer 1 — Problem Understanding (8 agents)

These agents parse the raw problem before any math. Critical for hard problems with embedded traps.

| # | Name | Role | What It Does |
|---|------|------|-------------|
| 1 | **TerminologyInterpreter** | terminology | Identifies and explains domain-specific terms and jargon |
| 2 | **DataValidator** | data_validation | Checks raw data for inconsistencies, missing values, schema mismatches |
| 3 | **AmbiguityDetector** | ambiguity_detection | Finds ambiguous, contradictory, or underspecified elements |
| 4 | **UnitConsistencyChecker** | unit_checking | Verifies unit consistency (time periods, currencies, measurements) |
| 5 | **ConstraintClassifier** | constraint_classification | Classifies each requirement as HARD, SOFT, or AMBIGUOUS |
| 6 | **ObjectiveIdentifier** | objective_identification | Determines what to optimize and the direction (min/max) |
| 7 | **DomainContextExpert** | domain_context | Provides real-world domain knowledge (e.g., airlines operate on daily cycles) |
| 8 | **AssumptionAuditor** | assumption_audit | Identifies every stated and unstated assumption |

## Layer 2 — Formulation (8 agents)

These agents build the mathematical optimization model.

| # | Name | Role | What It Does |
|---|------|------|-------------|
| 9 | **ParameterExtractor** | parameter_extraction | Extracts decision variables, parameters, and values — every parameter must trace to data |
| 10 | **SetIndexDesigner** | set_design | Defines index sets and their filtering from raw data |
| 11 | **VariableDomainExpert** | variable_domains | Determines variable types (binary/integer/continuous) and bounds |
| 12 | **ConstraintFormulator** | constraint_formulation | Translates HARD constraints into mathematical expressions |
| 13 | **ObjectiveFormulator** | objective_formulation | Writes the precise mathematical objective function |
| 14 | **BoundsTightener** | bounds_tightening | Removes redundant constraints, tightens bounds, adds symmetry-breaking |
| 15 | **FeasibilityChecker** | feasibility_check | Verifies a feasible solution exists with the given data |
| 16 | **ModelingReviewer** | model_review | Reviews complete formulation: parameter traceability, constraints, variable domains |

## Layer 3 — Implementation (8 agents)

These agents write and verify PuLP Python code.

| # | Name | Role | What It Does |
|---|------|------|-------------|
| 17 | **PuLPArchitect** | code_architecture | Designs code structure and solver configuration |
| 18 | **DataParsingExpert** | data_parsing | Writes robust parsing logic for messy real-world inputs |
| 19 | **ProgrammingExpert** | code_generation | Writes complete, executable PuLP code matching the function signature |
| 20 | **CodeReviewer** | code_review | Reviews code for bugs, missing constraints, wrong variable types |
| 21 | **EdgeCaseHandler** | edge_cases | Identifies edge cases (empty data, infeasible, unbounded, division by zero) |
| 22 | **SolverConfigExpert** | solver_config | Recommends solver settings (CBC parameters, time limits, gap tolerance) |
| 23 | **OutputValidator** | output_validation | Validates solver output for sanity and constraint satisfaction |
| 24 | **SensitivityAnalyst** | sensitivity_analysis | Analyzes which parameters/constraints most affect the solution |

## Layer 4 — Meta/Quality (6 agents)

Orchestration and quality control. Conductor, Reducer, and Auditor use Opus in hybrid mode.

| # | Name | Role | Model | What It Does |
|---|------|------|-------|-------------|
| 25 | **Conductor** | orchestration | opus | Selects next expert based on discussion state and gaps |
| 26 | **Reducer** | synthesis | opus | Synthesizes all expert comments into final PuLP code |
| 27 | **Auditor** | audit | opus | 8-point structured quality check on the formulation |
| 28 | **DevilsAdvocate** | challenge | mini | Challenges assumptions, proposes alternative interpretations |
| 29 | **ClientSimulator** | client_perspective | mini | Reviews formulation from a business stakeholder perspective |
| 30 | **FinalReviewer** | final_review | mini | GO/NO-GO recommendation before code generation |

## Agent Selection by Config

| Config | Agent Count | Which Agents |
|--------|-------------|-------------|
| C1, C2 | 3 | ParameterExtractor, ModelingReviewer, ProgrammingExpert (core trio) |
| C3, C4 | 15 | Understanding (8) + first 7 from Formulation |
| C5, C6 | 30 | All 24 discussion agents + DevilsAdvocate, ClientSimulator, FinalReviewer |

The `get_agents(n)` function in `agents.py` handles this:
- n <= 3: core trio (extract → review → code)
- n <= 8: understanding layer
- n <= 16: understanding + formulation
- n <= 24: all three layers
- n <= 30: adds meta-layer discussion agents (DevilsAdvocate, ClientSimulator, FinalReviewer)

Note: Conductor, Reducer, and Auditor are **not** in the discussion pool — they're used by the orchestrator directly.

## Design Principles

1. **Non-overlapping skills**: each agent has a unique, specific mandate
2. **Natural workflow order**: understand → formulate → implement → validate
3. **Escalating depth**: more agents = more specialized analysis, not redundancy
4. **Traceability**: every agent must cite data sources, never hallucinate parameters
5. **PuLP-only**: all generated code uses PuLP with CBC solver (free, no license)

## Key Prompting Patterns

- Every agent sees the **full problem description** + **all prior comments** from other agents
- Agents are instructed to **build on** prior analysis, not repeat it
- Unit consistency agents are specifically primed for common traps (monthly→daily, lbs→kg, per_100g→per_serving)
- Constraint classifier explicitly distinguishes HARD/SOFT/AMBIGUOUS — formulation agents only use HARD constraints
- ProgrammingExpert is told to use integer (not binary) for count-based decisions — a known failure mode from earlier experiments

## How to Update

Edit `agents.py` directly. The `AgentPersona` dataclass:
```python
@dataclass
class AgentPersona:
    name: str          # Display name
    role: str          # Machine-readable role tag
    description: str   # One-line description
    system_prompt: str  # Full system instructions (sent as in-0 to Stack AI)
    model: str = "mini" # "mini" or "opus"
```

To add a new agent: create the persona, add it to the appropriate layer list, and update `ALL_AGENTS`.
