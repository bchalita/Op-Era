#!/usr/bin/env python3
"""CLI entry point for multi-agent deliberation experiments."""

import argparse
import json
import os
import time

from orchestrator import run_experiment

# Predefined experiment configurations
CONFIGS = {
    "C1": {"agents": 3,  "rounds": 1, "model_mix": "mini_only", "conductor": "sequential"},
    "C2": {"agents": 3,  "rounds": 2, "model_mix": "mini_only", "conductor": "sequential"},
    "C3": {"agents": 6,  "rounds": 1, "model_mix": "mini_only", "conductor": "sequential"},
    "C4": {"agents": 6,  "rounds": 2, "model_mix": "mini_only", "conductor": "sequential"},
    "C5": {"agents": 10, "rounds": 1, "model_mix": "mini_only", "conductor": "sequential"},
    "C6": {"agents": 10, "rounds": 2, "model_mix": "hybrid",    "conductor": "llm"},
}

# Map config to folder name
CONFIG_FOLDERS = {
    "C1": "C1_3a_1r_mini_seq",
    "C2": "C2_3a_2r_mini_seq",
    "C3": "C3_6a_1r_mini_seq",
    "C4": "C4_6a_2r_mini_seq",
    "C5": "C5_10a_1r_mini_seq",
    "C6": "C6_10a_2r_hybrid_llm",
}


def resolve_config_folder(agents, rounds, model_mix, conductor):
    """Find the matching config folder, or use a custom one."""
    for name, cfg in CONFIGS.items():
        if (cfg["agents"] == agents and cfg["rounds"] == rounds
                and cfg["model_mix"] == model_mix and cfg["conductor"] == conductor):
            return CONFIG_FOLDERS[name]
    return f"custom_{agents}a_{rounds}r_{model_mix}_{conductor}"


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Deliberation Engine")
    parser.add_argument("--config", type=str, choices=list(CONFIGS.keys()),
                        help="Use a predefined config (C1-C6). Overrides --agents/--rounds/etc.")
    parser.add_argument("--problem", type=str, default="knapsack_optimization",
                        help="Problem name (directory under dataset/)")
    parser.add_argument("--dataset", type=str, default="ComplexOR",
                        help="Dataset name")
    parser.add_argument("--problem-dir", type=str, default=None,
                        help="Path to custom problem directory (overrides --problem/--dataset)")
    parser.add_argument("--agents", type=int, default=3,
                        help="Number of discussion agents")
    parser.add_argument("--rounds", type=int, default=1,
                        help="Number of discussion rounds")
    parser.add_argument("--conductor", type=str, default="sequential",
                        choices=["sequential", "llm"],
                        help="Conductor mode: sequential or llm-driven")
    parser.add_argument("--model-mix", type=str, default="mini_only",
                        choices=["mini_only", "hybrid", "opus_only"],
                        help="Model mix: mini_only, hybrid (opus for meta), opus_only")
    parser.add_argument("--agents-per-round", type=int, default=None,
                        help="Max agents speaking per round (default: all)")
    args = parser.parse_args()

    # Apply config preset if specified
    if args.config:
        cfg = CONFIGS[args.config]
        args.agents = cfg["agents"]
        args.rounds = cfg["rounds"]
        args.model_mix = cfg["model_mix"]
        args.conductor = cfg["conductor"]

    problem_label = args.problem
    if args.problem_dir:
        problem_label = os.path.basename(args.problem_dir.rstrip("/"))

    print(f"=== Multi-Agent Deliberation ===")
    if args.config:
        print(f"Config: {args.config}")
    print(f"Problem: {problem_label}")
    if args.problem_dir:
        print(f"Source: {args.problem_dir}")
    else:
        print(f"Dataset: {args.dataset}")
    print(f"Agents: {args.agents} | Rounds: {args.rounds} | Conductor: {args.conductor}")
    print(f"Model mix: {args.model_mix}")
    print()

    result = run_experiment(
        problem_name=problem_label,
        dataset=args.dataset,
        agent_count=args.agents,
        max_rounds=args.rounds,
        problem_dir=args.problem_dir,
        conductor_mode=args.conductor,
        model_mix=args.model_mix,
        agents_per_round=args.agents_per_round,
    )

    # Save into config-specific folder
    base_log_dir = os.path.join(os.path.dirname(__file__), "logs")
    config_folder = resolve_config_folder(args.agents, args.rounds, args.model_mix, args.conductor)
    log_dir = os.path.join(base_log_dir, config_folder)
    os.makedirs(log_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{problem_label}_{timestamp}.json"
    log_path = os.path.join(log_dir, filename)

    with open(log_path, "w", encoding="utf8") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)

    print(f"\nLog saved: {log_path}")
    print(f"\n=== RESULT: {result.eval_result.get('result', 'UNKNOWN')} ===")

    if result.generated_code:
        print(f"\n--- Generated Code ---")
        print(result.generated_code[:2000])
        if len(result.generated_code) > 2000:
            print(f"... ({len(result.generated_code)} chars total)")


if __name__ == "__main__":
    main()
