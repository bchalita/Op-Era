"""Orchestrator -- runs the full multi-agent pipeline with logging."""

import re
import time
from dataclasses import dataclass, field

from llm import call_llm
from agents import AgentPersona, get_agents, get_meta_agents
from comment_pool import Comment, CommentPool
from conductor import Conductor
from reducer import reduce, extract_code
from evaluator import evaluate, evaluate_custom, read_problem
from service_marketplace_evaluator import evaluate_service_marketplace


def _infer_function_name(code_example: str) -> str:
    """Extract function name from code_example.py content."""
    match = re.search(r"def\s+(\w+)\s*\(", code_example)
    return match.group(1) if match else "solve_optimization"


SUMMARIZER_INSTRUCTIONS = (
    "You are a discussion synthesizer. Condense the expert comments from this round "
    "into a structured summary. Preserve:\n"
    "1. KEY DECISIONS: what the experts agree on\n"
    "2. OPEN QUESTIONS: unresolved disagreements or unknowns\n"
    "3. CONSTRAINTS IDENTIFIED: hard vs soft, with sources\n"
    "4. PROPOSED APPROACH: the emerging strategy\n"
    "5. DATA ISSUES: any data problems or transformations needed\n\n"
    "Be concise -- the next round of experts will read this summary instead of "
    "the raw discussion. Keep it under 500 words."
)


def _summarize_round(round_num: int, round_text: str, problem_description: str,
                     model: str = "mini") -> str:
    """Condense a round's discussion into a structured summary."""
    prompt = (
        f"## Problem Context\n{problem_description[:2000]}\n\n"
        f"## Round {round_num} Expert Discussion\n{round_text}\n\n"
        "Synthesize this discussion into a concise structured summary."
    )
    return call_llm(SUMMARIZER_INSTRUCTIONS, prompt, model=model)


@dataclass
class AgentCall:
    """Record of a single agent invocation."""
    agent_name: str
    role: str
    round_num: int
    model: str
    instructions: str
    prompt: str
    response: str
    latency_s: float
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "role": self.role,
            "round_num": self.round_num,
            "model": self.model,
            "instructions": self.instructions,
            "prompt": self.prompt,
            "response": self.response,
            "latency_s": self.latency_s,
            "timestamp": self.timestamp,
        }


@dataclass
class ExperimentResult:
    """Complete record of one experiment run."""
    problem_name: str
    dataset: str
    agent_count: int
    max_rounds: int
    conductor_mode: str = "sequential"
    model_mix: str = "mini_only"
    agent_calls: list = field(default_factory=list)
    conductor_calls: list = field(default_factory=list)
    reducer_call: dict = field(default_factory=dict)
    generated_code: str = ""
    eval_result: dict = field(default_factory=dict)
    total_latency_s: float = 0.0
    total_api_calls: int = 0

    def to_dict(self) -> dict:
        return {
            "problem_name": self.problem_name,
            "dataset": self.dataset,
            "agent_count": self.agent_count,
            "max_rounds": self.max_rounds,
            "conductor_mode": self.conductor_mode,
            "model_mix": self.model_mix,
            "agent_calls": [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.agent_calls],
            "conductor_calls": self.conductor_calls,
            "reducer_call": self.reducer_call,
            "generated_code": self.generated_code,
            "eval_result": self.eval_result,
            "total_latency_s": self.total_latency_s,
            "total_api_calls": self.total_api_calls,
        }


def run_experiment(
    problem_name: str,
    dataset: str = "ComplexOR",
    agent_count: int = 3,
    max_rounds: int = 1,
    problem_dir: str = None,
    conductor_mode: str = "sequential",
    model_mix: str = "mini_only",
    agents_per_round: int = None,
) -> ExperimentResult:
    """Run the multi-agent optimization pipeline.

    Args:
        problem_name: Problem directory name.
        dataset: Dataset name (default 'ComplexOR').
        agent_count: Number of expert agents to use.
        max_rounds: Number of discussion rounds.
        problem_dir: Custom problem directory (overrides dataset).
        conductor_mode: "sequential" or "llm" (LLM-driven selection).
        model_mix: "mini_only", "hybrid" (opus for conductor/reducer/auditor), or "opus_only".
        agents_per_round: How many agents speak per round (default: all).
    """
    result = ExperimentResult(
        problem_name=problem_name,
        dataset=dataset,
        agent_count=agent_count,
        max_rounds=max_rounds,
        conductor_mode=conductor_mode,
        model_mix=model_mix,
    )
    t_start = time.time()

    # Determine model for each role
    if model_mix == "opus_only":
        discussion_model = "opus"
        reducer_model = "opus"
        conductor_model = "opus"
    elif model_mix == "hybrid":
        discussion_model = "mini"
        reducer_model = "opus"
        conductor_model = "opus"
    else:  # mini_only
        discussion_model = "mini"
        reducer_model = "mini"
        conductor_model = "mini"

    # 1. Load problem
    if problem_dir:
        from load_custom_problem import load_from_directory
        problem = load_from_directory(problem_dir)
        print(f"Loaded custom problem from: {problem_dir}")
    else:
        problem = read_problem(dataset, problem_name)
        print(f"Loaded problem: {problem_name}")
    print(f"  Description length: {len(problem['description'])} chars")

    # 2. Initialize agents
    agents = get_agents(agent_count)
    print(f"  Agents ({len(agents)}): {[a.name for a in agents]}")
    print(f"  Conductor: {conductor_mode} | Models: {model_mix}")

    if agents_per_round is None:
        agents_per_round = len(agents)

    # 3. Initialize state
    pool = CommentPool()

    # Detect if this is a service marketplace problem (open-ended, non-PuLP)
    is_service_marketplace = problem_dir and _is_service_marketplace_problem(problem_dir, problem_name)

    # 4. Discussion rounds
    for round_num in range(1, max_rounds + 1):
        print(f"\n--- Round {round_num} ---")
        conductor = Conductor(agents, mode=conductor_mode, conductor_model=conductor_model)
        agents_called = 0

        while agents_called < agents_per_round:
            visible = pool.get_visible_comments(current_round=round_num)
            agent = conductor.next(
                problem_description=problem["description"],
                comments_text=visible,
            )
            if agent is None:
                break

            # Use agent's own model preference if opus_only, otherwise use discussion_model
            agent_model = discussion_model
            if model_mix == "opus_only":
                agent_model = "opus"

            # Build prompt
            prompt = (
                f"## Problem Description\n{problem['description']}\n\n"
                f"## Function Signature\n```python\n{problem['code_example']}\n```\n\n"
                f"## Prior Expert Comments\n{visible}\n\n"
                f"Now provide your expert analysis for this problem."
            )

            print(f"  [{agent_model}] {agent.name}...", end=" ", flush=True)
            t0 = time.time()
            response = call_llm(agent.system_prompt, prompt, model=agent_model)
            latency = time.time() - t0
            print(f"done ({latency:.1f}s)")

            call = AgentCall(
                agent_name=agent.name,
                role=agent.role,
                round_num=round_num,
                model=agent_model,
                instructions=agent.system_prompt,
                prompt=prompt,
                response=response,
                latency_s=latency,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            result.agent_calls.append(call)
            result.total_api_calls += 1
            agents_called += 1

            pool.add(Comment(
                agent_name=agent.name,
                content=response,
                round_num=round_num,
            ))

        # Summarize completed round (for multi-round experiments)
        if max_rounds > 1 and round_num < max_rounds:
            print(f"  Summarizing round {round_num}...", end=" ", flush=True)
            round_text = pool.get_round_comments_text(round_num)
            t0 = time.time()
            summary = _summarize_round(
                round_num, round_text, problem["description"],
                model=reducer_model,
            )
            latency = time.time() - t0
            pool.set_round_summary(round_num, summary)
            result.total_api_calls += 1
            result.conductor_calls.append({
                "type": "round_summary",
                "round": round_num,
                "model": reducer_model,
                "input_chars": len(round_text),
                "output_chars": len(summary),
                "latency_s": latency,
            })
            print(f"done ({latency:.1f}s, {len(round_text)} -> {len(summary)} chars)")

    # 5. Reduce
    print(f"\n--- Reducer [{reducer_model}] ---")
    comments_text = pool.get_visible_comments()
    t0 = time.time()
    if is_service_marketplace:
        print("  Condensing expert comments...", end=" ", flush=True)
    raw_answer = reduce(problem["description"], problem["code_example"], comments_text,
                        model=reducer_model, open_ended=is_service_marketplace)
    reducer_latency = time.time() - t0
    if is_service_marketplace:
        result.total_api_calls += 1  # condenser call
    print(f"  Reducer done ({reducer_latency:.1f}s)")

    code = extract_code(raw_answer)
    result.generated_code = code
    result.reducer_call = {
        "model": reducer_model,
        "raw_response": raw_answer,
        "extracted_code": code,
        "latency_s": reducer_latency,
    }
    result.total_api_calls += 1

    # 6. Evaluate
    print(f"\n--- Evaluator ---")
    if is_service_marketplace:
        eval_result = evaluate_service_marketplace(code, problem_dir)
        result.eval_result = eval_result
        grade = eval_result.get("grade", "?")
        sc = eval_result.get("scoring", {})
        print(f"  Grade: {grade} (score={sc.get('composite', '?')}/100)")
        if eval_result.get("agent_metrics"):
            am = eval_result["agent_metrics"]
            gm = eval_result["ground_truth_metrics"]
            print(f"  Agent:     served={am['served']}, recovered={am['recovered_from_dr']}, lost={am['lost_regressions']}, km={am['total_km']}, specs={am['specialists_used']}")
            print(f"  Optimizer: served={gm['optimizer_served']}, recovered={gm['optimizer_recovered']}, lost={gm['optimizer_lost']}, km={gm['optimizer_km']}, specs={gm['optimizer_specs']}")
            print(f"  Scores: served={sc.get('served_score','?')}/40, feasibility={sc.get('feasibility_score','?')}/25, travel={sc.get('travel_score','?')}/20, regressions={sc.get('regression_score','?')}/15")
            feas = eval_result.get("feasibility", {})
            violations = []
            if feas.get("infeasible_assignments"): violations.append(f"{feas['infeasible_assignments']} infeasible")
            if feas.get("capacity_violations"): violations.append(f"{feas['capacity_violations']} capacity")
            if feas.get("time_violations"): violations.append(f"{feas['time_violations']} time")
            if feas.get("radius_violations"): violations.append(f"{feas['radius_violations']} radius")
            if violations:
                print(f"  Violations: {', '.join(violations)}")
    elif problem_dir and problem.get("sample_data") is not None:
        func_name = _infer_function_name(problem["code_example"])
        eval_result = evaluate(func_name, code, sample_data=problem["sample_data"])
        result.eval_result = eval_result
        print(f"  Result: {eval_result['result']}")
    elif problem_dir and problem.get("ground_truth_value") is not None:
        eval_result = evaluate_custom(code, problem["ground_truth_value"], problem.get("description", ""))
        result.eval_result = eval_result
        print(f"  Result: {eval_result['result']}")
    elif not problem_dir:
        eval_result = evaluate(problem_name, code, dataset)
        result.eval_result = eval_result
        print(f"  Result: {eval_result['result']}")
    else:
        eval_result = {"result": "NO_GROUND_TRUTH", "details": [], "output": None, "expected": None, "error": None}
        result.eval_result = eval_result
        print(f"  Result: {eval_result['result']}")
    if eval_result.get("details"):
        for d in eval_result["details"]:
            status = "PASS" if d.get("passed") else "FAIL"
            print(f"    Sample {d.get('sample', '?')}: {status} (output={d.get('output')}, expected={d.get('expected')})")

    result.total_latency_s = time.time() - t_start
    print(f"\nTotal: {result.total_api_calls} API calls, {result.total_latency_s:.1f}s")

    return result


def _is_service_marketplace_problem(problem_dir: str, problem_name: str) -> bool:
    """Detect if a custom problem is a service marketplace allocation problem.

    Checks for the presence of orders.json and specialists.json in the problem
    directory, which indicates a service marketplace structure.
    """
    import os
    orders_path = os.path.join(problem_dir, "orders.json")
    specialists_path = os.path.join(problem_dir, "specialists.json")
    return os.path.exists(orders_path) and os.path.exists(specialists_path)
