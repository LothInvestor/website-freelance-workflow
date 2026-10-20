"""Common output format for every agent."""

from dataclasses import dataclass, field


@dataclass
class Report:
    agent: str
    issues: list[tuple[int, str]] = field(default_factory=list)  # (penalty, clause)
    data: dict = field(default_factory=dict)
    quality_override: int | None = None  # agents that score directly (e.g. visual)
    skipped: str = ""

    def add(self, penalty: int, clause: str) -> None:
        """clause is phrased so it follows 'le site de X …', e.g. "affiche un copyright de 2016"."""
        self.issues.append((penalty, clause))

    @property
    def quality(self) -> int:
        if self.quality_override is not None:
            return self.quality_override
        return max(0, 100 - sum(p for p, _ in self.issues))
