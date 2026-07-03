from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class Change:
    title: str
    desc: str | None
    shoulds: list[str]
    musts: list[str]
    approvals: list[str]

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            {
                "title": self.title,
                "desc": self.desc,
                "shoulds": self.shoulds,
                "musts": self.musts,
                "approvals": self.approvals,
            },
            sort_keys=False,
        )

    @classmethod
    def from_yaml(cls, value: str) -> "Change":
        data = yaml.safe_load(value)
        return cls(**data)
