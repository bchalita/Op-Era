"""Reducer -- synthesizes all expert comments into final executable code."""

import re
from llm import call_llm


REDUCER_INSTRUCTIONS = (
    "You are a senior Operations Research engineer. Synthesize the insights from "
    "multiple expert colleagues into a single, final, executable Python implementation "
    "using PuLP.\n\n"
    "CRITICAL RULES:\n"
    "1. Use PuLP (from pulp import *). Solver: PULP_CBC_CMD(msg=0)\n"
    "2. Match the provided function signature EXACTLY -- same function name, "
    "same parameters, same return type.\n"
    "3. No code outside the function except import statements. No test code.\n"
    "4. The function must be completely self-contained and runnable.\n"
    "5. Return the optimal objective value as a float.\n"
    "6. If the function receives problem_data as a string, you MUST parse the "
    "data from that string (CSVs are embedded as === filename.csv === sections).\n\n"
    "Output ONLY the final Python code inside a ```python code block."
)

REDUCER_INSTRUCTIONS_OPEN = (
    "You are an expert Python programmer. Write COMPACT code (under 100 lines). "
    "No comments, no docstrings, short variable names. "
    "Use ONLY standard library (json, math). No numpy/scipy/pulp. "
    "Use a GREEDY HEURISTIC: score candidates, assign best-first. "
    "Match the function signature EXACTLY. No test code.\n"
    "PARSING RULES: Use simple direct access -- x.get('key', default). "
    "NO nested getters, NO helper functions for field access. "
    "Keep data parsing flat and obvious.\n"
    "Output ONLY ```python code block, nothing else."
)

CONDENSER_INSTRUCTIONS = (
    "Condense these expert comments into a BRIEF implementation plan (under 300 words). "
    "Include: (1) key constraints as hard/soft, (2) recommended greedy algorithm, "
    "(3) scoring formula for candidate ranking. "
    "Be specific and actionable -- a programmer will code directly from this plan. "
    "Do NOT list every possible edge case -- focus on the core algorithm."
)

DATA_SCHEMA_HINT = (
    "DATA SCHEMA (use these exact field names):\n"
    "Order: order_id, start_min, end_min, duration, service, lat, lng, "
    "travel_speed, baseline_specialist\n"
    "Specialist: spec_id, home_lat, home_lng, certs (list), max_orders, "
    "typical_min, radius_cap_km, window_start, window_end\n"
    "NOTE: Some fields may be None -- always use `x.get('field') or default`.\n"
)


def condense_comments(problem_description: str, comments_text: str,
                      model: str = "mini") -> str:
    """Condense expert comments into a brief implementation plan."""
    prompt = (
        f"Problem (brief): {problem_description[:1500]}\n\n"
        f"{DATA_SCHEMA_HINT}\n"
        f"Expert comments:\n{comments_text[:6000]}\n\n"
        "Write the implementation plan now."
    )
    return call_llm(CONDENSER_INSTRUCTIONS, prompt, model=model)


def reduce(problem_description: str, code_example: str, comments_text: str,
           model: str = "mini", open_ended: bool = False) -> str:
    """Synthesize expert comments into final executable code.

    Args:
        open_ended: If True, use flexible instructions (not locked to PuLP).
    """
    instructions = REDUCER_INSTRUCTIONS_OPEN if open_ended else REDUCER_INSTRUCTIONS

    if open_ended:
        # Two-step: condense comments first, then generate code from plan
        plan = condense_comments(problem_description, comments_text, model=model)
        prompt = (
            f"## Implementation Plan\n{plan}\n\n"
            f"## {DATA_SCHEMA_HINT}\n"
            f"## Function Signature (MUST match exactly)\n```python\n{code_example}\n```\n\n"
            "Write the complete Python function now. COMPACT code, under 100 lines."
        )
    else:
        prompt = (
            f"## Problem Description\n{problem_description}\n\n"
            f"## Function Signature (MUST match exactly)\n```python\n{code_example}\n```\n\n"
            f"## Expert Discussion\n{comments_text}\n\n"
            "Synthesize all expert insights into the final Python code. "
            "Use PuLP, match the function signature, return the optimal value."
        )
    return call_llm(instructions, prompt, model=model)


def extract_code(text: str) -> str:
    """Extract Python code from markdown code blocks."""
    # Try closed code blocks first
    pattern = r"```(?:python)?\s*(.*?)\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        code_blocks = [m for m in matches if "pip install" not in m]
        if code_blocks:
            return max(code_blocks, key=len)

    # Handle unclosed code block (model hit output limit)
    open_pattern = r"```(?:python)?\s*(.*)"
    match = re.search(open_pattern, text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # Remove trailing refusal messages
        for cutoff in ["I'm sorry", "I cannot", "I apologize"]:
            idx = code.find(cutoff)
            if idx > 0:
                code = code[:idx].rstrip()
        return code

    return text
