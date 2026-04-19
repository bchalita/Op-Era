"""Conductor — decides which expert speaks next."""

from typing import Optional

from agents import AgentPersona
from stackai import call_llm


class Conductor:
    """Expert selection — sequential for small counts, LLM-driven for scale."""

    def __init__(self, agents: list[AgentPersona], mode: str = "sequential",
                 conductor_model: str = "mini"):
        self.agents = agents
        self.mode = mode
        self.conductor_model = conductor_model
        self._index = 0
        self._called = set()

    def next(self, problem_description: str = "", comments_text: str = "") -> Optional[AgentPersona]:
        """Return the next agent to activate, or None if done."""
        if self.mode == "sequential":
            if self._index >= len(self.agents):
                return None
            agent = self.agents[self._index]
            self._index += 1
            return agent

        elif self.mode == "llm":
            remaining = [a for a in self.agents if a.name not in self._called]
            if not remaining:
                return None

            experts_info = "\n".join(
                f"- {a.name}: {a.description}" for a in self.agents
            )
            already_called = ", ".join(sorted(self._called)) if self._called else "None yet"
            remaining_names = ", ".join(a.name for a in remaining)

            instructions = (
                "You are the conductor of a multi-expert system solving an optimization problem. "
                "Choose which expert should speak NEXT based on what has been discussed and what gaps remain.\n\n"
                f"Available experts:\n{experts_info}\n\n"
                f"Already consulted: {already_called}\n"
                f"Remaining: {remaining_names}\n\n"
                "Output ONLY the exact name of the next expert."
            )
            prompt = (
                f"Problem: {problem_description[:500]}...\n\n"
                f"Discussion so far:\n{comments_text[:2000]}...\n\n"
                "Which expert should speak next?"
            )

            response = call_llm(instructions, prompt, model=self.conductor_model)
            chosen_name = response.strip().strip("*").strip()

            # Match response to an agent
            for agent in remaining:
                if agent.name.lower() in chosen_name.lower() or chosen_name.lower() in agent.name.lower():
                    self._called.add(agent.name)
                    return agent

            # Fallback: pick the first remaining
            agent = remaining[0]
            self._called.add(agent.name)
            return agent

        else:
            raise NotImplementedError(f"Conductor mode '{self.mode}' not implemented")

    def reset(self):
        """Reset for a new round."""
        self._index = 0
        self._called.clear()
