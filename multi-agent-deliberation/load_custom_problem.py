"""Loader for custom problem formats outside the ComplexOR dataset.

Handles two formats:
  - Easy: directory with description.txt, code_example.py, sample.json, ground_truth.md
  - Hard: directory with email_thread.txt, CSV files, ground_truth.md
"""

import json
import os
import re
from typing import Optional


def load_from_directory(problem_dir: str) -> dict:
    """Load a problem from a directory.

    Auto-detects easy vs hard format based on presence of sample.json.

    Returns:
        dict with keys:
            description: str — problem text
            code_example: str — function signature
            ground_truth_value: float or None — expected optimal (hard problems)
            sample_data: list or None — test samples (easy problems)
            format: "easy" or "hard"
    """
    has_sample = os.path.exists(os.path.join(problem_dir, "sample.json"))
    has_code_example = os.path.exists(os.path.join(problem_dir, "code_example.py"))

    if has_sample and has_code_example:
        return _load_easy(problem_dir)
    else:
        return _load_hard(problem_dir)


def _load_easy(problem_dir: str) -> dict:
    """Load easy-format problem (ComplexOR-style)."""
    with open(os.path.join(problem_dir, "description.txt"), "r", encoding="utf8") as f:
        description = f.read().strip()
    with open(os.path.join(problem_dir, "code_example.py"), "r", encoding="utf8") as f:
        code_example = f.read().strip()
    with open(os.path.join(problem_dir, "sample.json"), "r", encoding="utf8") as f:
        sample_data = json.load(f)

    return {
        "description": description,
        "code_example": code_example,
        "ground_truth_value": None,
        "sample_data": sample_data,
        "format": "easy",
        "source_dir": problem_dir,
    }


def _load_hard(problem_dir: str) -> dict:
    """Load hard-format problem (email thread + CSVs)."""
    files_content = []
    txt_files = []
    csv_files = []

    for fname in sorted(os.listdir(problem_dir)):
        fpath = os.path.join(problem_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if fname in ("ground_truth.md", "problem_name.txt"):
            continue
        if fname.endswith(".txt"):
            txt_files.append((fname, fpath))
        elif fname.endswith(".csv"):
            csv_files.append((fname, fpath))

    for fname, fpath in txt_files:
        with open(fpath, "r", encoding="utf8") as f:
            content = f.read().strip()
        files_content.append(f"=== {fname} ===\n{content}")

    for fname, fpath in csv_files:
        with open(fpath, "r", encoding="utf8") as f:
            content = f.read().strip()
        files_content.append(f"=== {fname} ===\n{content}")

    description = "\n\n".join(files_content)

    # Use code_example.py if present, otherwise default
    code_example_path = os.path.join(problem_dir, "code_example.py")
    if os.path.exists(code_example_path):
        with open(code_example_path, "r", encoding="utf8") as f:
            code_example = f.read().strip()
    else:
        code_example = (
            "from pulp import *\n\n"
            "def solve_optimization(problem_data: str):\n"
            '    """\n'
            "    Given the raw problem data (email thread + CSV files),\n"
            "    formulate and solve the optimization problem.\n\n"
            "    Returns:\n"
            "        optimal_value: a float, the optimal objective value\n"
            '    """\n'
            "    # Parse data, formulate, solve\n"
            "    optimal_value = 0.0\n"
            "    return optimal_value\n"
        )

    gt_value = _extract_ground_truth(problem_dir)

    return {
        "description": description,
        "code_example": code_example,
        "ground_truth_value": gt_value,
        "sample_data": None,
        "format": "hard",
        "source_dir": problem_dir,
    }


def _extract_ground_truth(problem_dir: str) -> Optional[float]:
    """Extract numeric ground truth from ground_truth.md."""
    gt_path = os.path.join(problem_dir, "ground_truth.md")
    if not os.path.exists(gt_path):
        return None

    with open(gt_path, "r", encoding="utf8") as f:
        content = f.read()

    # Look for optimal value in various formats
    patterns = [
        r"Verified optimal:\s*\$?([\d,]+\.?\d*)",
        r"\*\*Verified optimal:\s*\$?([\d,]+\.?\d*)",
        r"\*\*\$?([\d,]+\.?\d*)\s*(?:BRL|USD|min|minutes)\*\*",
        r"\*\*\$?([\d,]+\.?\d*)\*\*\s*[—\-]",
        r"Expected [Oo]ptimal.*?\n\*\*\$?([\d,]+\.?\d*)",
        r"Optimal:\s*\$?([\d,]+\.?\d*)",
        r"## Optimal:\s*([\d,]+\.?\d*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            val_str = match.group(1).replace(",", "")
            return float(val_str)

    return None
