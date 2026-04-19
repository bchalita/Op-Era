"""LLM interface for the multi-agent deliberation engine.

Supports OpenAI and Anthropic backends. Set OPENAI_API_KEY (primary)
or ANTHROPIC_API_KEY (fallback) as environment variables.
"""

import os
import time

# Model mappings
OPENAI_MODELS = {
    "mini": "gpt-4o-mini",
    "opus": "gpt-4o",
}

ANTHROPIC_MODELS = {
    "mini": "claude-haiku-4-5-20251001",
    "opus": "claude-sonnet-4-20250514",
}

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


def call_llm(instructions: str, prompt: str, model: str = "mini") -> str:
    """Call an LLM with system instructions and a user prompt.

    Args:
        instructions: System-level instructions for the model.
        prompt: User prompt / content to process.
        model: Model tier -- "mini" (fast/cheap) or "opus" (capable).

    Returns:
        The model's text response.

    Raises:
        RuntimeError: If no API key is set or all retries fail.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if openai_key:
        return _call_openai(instructions, prompt, model, openai_key)
    elif anthropic_key:
        return _call_anthropic(instructions, prompt, model, anthropic_key)
    else:
        raise RuntimeError(
            "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY "
            "as an environment variable."
        )


def _call_openai(instructions: str, prompt: str, model: str, api_key: str) -> str:
    """Call OpenAI API with retry logic."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model_name = OPENAI_MODELS.get(model, model)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"OpenAI API call failed after {MAX_RETRIES} attempts: {e}"
                ) from e
            backoff = INITIAL_BACKOFF * (2 ** attempt)
            print(f"  [retry {attempt + 1}/{MAX_RETRIES}] {e} -- waiting {backoff:.0f}s")
            time.sleep(backoff)


def _call_anthropic(instructions: str, prompt: str, model: str, api_key: str) -> str:
    """Call Anthropic API with retry logic."""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    model_name = ANTHROPIC_MODELS.get(model, model)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=model_name,
                max_tokens=4096,
                system=instructions,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            return response.content[0].text
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"Anthropic API call failed after {MAX_RETRIES} attempts: {e}"
                ) from e
            backoff = INITIAL_BACKOFF * (2 ** attempt)
            print(f"  [retry {attempt + 1}/{MAX_RETRIES}] {e} -- waiting {backoff:.0f}s")
            time.sleep(backoff)
