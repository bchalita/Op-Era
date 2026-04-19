"""Evaluator — runs generated code against ground truth from sample.json."""

import importlib
import json
import os
import sys
import tempfile
import traceback
from enum import Enum


class Result(Enum):
    ACCEPT = "ACCEPT"
    WRONG_ANSWER = "WRONG_ANSWER"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    COMPILE_ERROR = "COMPILE_ERROR"


# Path to the ComplexOR dataset
DATASET_BASE = os.path.join(
    os.path.dirname(__file__), "..", "ComplexOR", "dataset"
)


def read_test_samples(dataset: str, problem: str) -> list[dict]:
    """Load ground-truth test samples from sample.json."""
    path = os.path.join(DATASET_BASE, dataset, problem, "sample.json")
    with open(path, "r", encoding="utf8") as f:
        return json.load(f)


def read_problem(dataset: str, problem: str) -> dict:
    """Load problem description and code example."""
    base = os.path.join(DATASET_BASE, dataset, problem)
    with open(os.path.join(base, "description.txt"), "r", encoding="utf8") as f:
        description = f.read().strip()
    with open(os.path.join(base, "code_example.py"), "r", encoding="utf8") as f:
        code_example = f.read().strip()
    return {"description": description, "code_example": code_example}


def evaluate(problem_name: str, generated_code: str, dataset: str = "ComplexOR",
             sample_data: list = None) -> dict:
    """Execute generated code against ground truth.

    Args:
        problem_name: Name of the problem (e.g., 'knapsack_optimization').
        generated_code: The Python source code to evaluate.
        dataset: Dataset name (default 'ComplexOR').
        sample_data: Pre-loaded sample data (skips reading from file if provided).

    Returns:
        Dict with keys: result, output, expected, error, details
    """
    samples = sample_data if sample_data is not None else read_test_samples(dataset, problem_name)

    # Write code to a temp module and import it
    tmp_dir = tempfile.mkdtemp()
    module_path = os.path.join(tmp_dir, "generated_code.py")
    with open(module_path, "w", encoding="utf8") as f:
        f.write(generated_code)

    # Add tmp_dir to sys.path so we can import
    sys.path.insert(0, tmp_dir)
    try:
        # Import (or re-import) the generated module
        if "generated_code" in sys.modules:
            del sys.modules["generated_code"]
        try:
            import generated_code
        except Exception as e:
            return {
                "result": Result.COMPILE_ERROR.value,
                "output": None,
                "expected": None,
                "error": f"Compile error: {e}\n{traceback.format_exc()}",
                "details": [],
            }

        # Find the function by problem name
        func = getattr(generated_code, problem_name, None)
        if func is None:
            return {
                "result": Result.COMPILE_ERROR.value,
                "output": None,
                "expected": None,
                "error": f"Function '{problem_name}' not found in generated code.",
                "details": [],
            }

        # Run each test sample
        details = []
        all_passed = True
        any_runtime_error = False

        for i, sample in enumerate(samples):
            expected = sample["output"][0] if len(sample["output"]) == 1 else tuple(sample["output"])
            try:
                output = func(**sample["input"])
            except Exception as e:
                any_runtime_error = True
                details.append({
                    "sample": i,
                    "passed": False,
                    "output": None,
                    "expected": expected,
                    "error": f"{e}\n{traceback.format_exc()}",
                })
                continue

            # Compare with tolerance for floats
            if isinstance(expected, (int, float)) and isinstance(output, (int, float)):
                passed = abs(output - expected) < max(1e-4, abs(expected) * 1e-4)
            else:
                passed = output == expected

            if not passed:
                all_passed = False

            details.append({
                "sample": i,
                "passed": passed,
                "output": output,
                "expected": expected,
                "error": None,
            })

        if any_runtime_error:
            result = Result.RUNTIME_ERROR
        elif all_passed:
            result = Result.ACCEPT
        else:
            result = Result.WRONG_ANSWER

        return {
            "result": result.value,
            "output": details[-1]["output"] if details else None,
            "expected": details[-1]["expected"] if details else None,
            "error": None if result == Result.ACCEPT else "See details",
            "details": details,
        }

    finally:
        sys.path.remove(tmp_dir)
        if "generated_code" in sys.modules:
            del sys.modules["generated_code"]


def evaluate_custom(generated_code: str, expected_value: float, problem_description: str = "") -> dict:
    """Evaluate generated code for custom problems (no sample.json).

    Executes the code and looks for a solve_optimization() function or
    just runs the module and captures the printed output / return value.

    Args:
        generated_code: Python source code.
        expected_value: Expected optimal objective value.
        problem_description: The raw problem text to pass to solve_optimization().

    Returns:
        Dict with result, output, expected, error, details.
    """
    tmp_dir = tempfile.mkdtemp()
    module_path = os.path.join(tmp_dir, "generated_code.py")
    with open(module_path, "w", encoding="utf8") as f:
        f.write(generated_code)

    sys.path.insert(0, tmp_dir)
    try:
        if "generated_code" in sys.modules:
            del sys.modules["generated_code"]

        # Capture stdout during import (some code prints results at module level)
        import io
        from contextlib import redirect_stdout
        stdout_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture):
                import generated_code
        except Exception as e:
            return {
                "result": Result.COMPILE_ERROR.value,
                "output": None,
                "expected": expected_value,
                "error": f"Compile error: {e}\n{traceback.format_exc()}",
                "details": [],
            }

        captured = stdout_capture.getvalue()
        output = None

        # Try calling solve_optimization() if it exists
        func = getattr(generated_code, "solve_optimization", None)
        if func is not None:
            try:
                output = func(problem_description)
            except Exception as e:
                # Try with no args
                try:
                    output = func()
                except Exception:
                    return {
                        "result": Result.RUNTIME_ERROR.value,
                        "output": None,
                        "expected": expected_value,
                        "error": f"Runtime error calling solve_optimization: {e}\n{traceback.format_exc()}",
                        "details": [],
                    }

        # If no function found, look for module-level result variable
        if output is None:
            for attr_name in ["optimal_cost", "result", "optimal_value", "obj_value", "total_cost"]:
                output = getattr(generated_code, attr_name, None)
                if output is not None:
                    break

        # Last resort: try to parse a number from stdout
        if output is None and captured:
            import re
            numbers = re.findall(r"[-+]?\d*\.?\d+", captured)
            if numbers:
                output = float(numbers[-1])  # Take the last number printed

        if output is None:
            return {
                "result": Result.RUNTIME_ERROR.value,
                "output": None,
                "expected": expected_value,
                "error": f"Could not extract result. Stdout: {captured[:500]}",
                "details": [],
            }

        # Compare
        output = float(output)
        tolerance = max(1.0, abs(expected_value) * 0.02)  # 2% tolerance
        passed = abs(output - expected_value) < tolerance

        return {
            "result": Result.ACCEPT.value if passed else Result.WRONG_ANSWER.value,
            "output": output,
            "expected": expected_value,
            "error": None if passed else f"Output {output} != expected {expected_value} (tolerance {tolerance})",
            "details": [{"sample": 0, "passed": passed, "output": output, "expected": expected_value, "error": None}],
            "stdout": captured[:2000] if captured else None,
        }

    finally:
        sys.path.remove(tmp_dir)
        if "generated_code" in sys.modules:
            del sys.modules["generated_code"]
