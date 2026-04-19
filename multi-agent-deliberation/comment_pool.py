"""Comment pool — tracks the full discussion state across rounds."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Comment:
    agent_name: str
    content: str
    round_num: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "content": self.content,
            "round_num": self.round_num,
            "timestamp": self.timestamp,
        }


class CommentPool:
    """Stores all agent comments with round summarization support."""

    def __init__(self):
        self.comments: list[Comment] = []
        self.round_summaries: dict[int, str] = {}  # round_num -> summary text

    def add(self, comment: Comment):
        self.comments.append(comment)

    def set_round_summary(self, round_num: int, summary: str):
        """Store a condensed summary for a completed round."""
        self.round_summaries[round_num] = summary

    def get_visible_comments(self, current_round: int = None) -> str:
        """Return formatted comments visible to agents.

        If round summaries exist for prior rounds, show those instead of raw comments.
        Raw comments from the CURRENT round are always shown in full.
        """
        if not self.comments and not self.round_summaries:
            return "No prior comments from other experts yet."

        lines = []

        if current_round and self.round_summaries:
            # Show summaries for completed rounds
            for rnd in sorted(self.round_summaries.keys()):
                if rnd < current_round:
                    lines.append(
                        f"[Round {rnd} Summary]\n{self.round_summaries[rnd]}"
                    )

            # Show raw comments from current round only
            current_comments = [c for c in self.comments if c.round_num == current_round]
            for c in current_comments:
                lines.append(f"[Round {current_round}] {c.agent_name}:\n{c.content}")
        else:
            # No summarization — show everything raw (round 1 or no summaries)
            for c in self.comments:
                lines.append(f"[Round {c.round_num}] {c.agent_name}:\n{c.content}")

        return "\n\n---\n\n".join(lines) if lines else "No prior comments from other experts yet."

    def get_all_as_dicts(self) -> list[dict]:
        return [c.to_dict() for c in self.comments]

    def get_round_comments_text(self, round_num: int) -> str:
        """Get raw text of all comments from a specific round."""
        round_comments = [c for c in self.comments if c.round_num == round_num]
        if not round_comments:
            return ""
        lines = []
        for c in round_comments:
            lines.append(f"{c.agent_name}:\n{c.content}")
        return "\n\n---\n\n".join(lines)

    def __len__(self):
        return len(self.comments)
