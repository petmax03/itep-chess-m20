"""Explicit research settings applied after the preserved v11 base patches."""
from dataclasses import dataclass
from .native_rank_capacity import apply_native_rank_capacity


DEFAULT_PROFILE = "v11"
PROFILES = {
    "v11": dict(checks=0, evaluations=3, rank_cap=14, source_4344=False, forced_scheme="native"),
    "v12-source": dict(checks=0, evaluations=3, rank_cap=16, source_4344=True, forced_scheme="native"),
    "v12-narrow": dict(checks=0, evaluations=3, rank_cap=14, source_4344=False, forced_scheme="narrow"),
}


@dataclass(frozen=True)
class SearchSettings:
    profile: str
    checks: int
    evaluations: int
    rank_cap: int
    source_4344: bool
    forced_scheme: str
    overrides: tuple

    def metadata(self):
        return {
            "name": self.profile,
            "checks": self.checks,
            "evaluations": self.evaluations,
            "rank_cap": self.rank_cap,
            "source_4344": self.source_4344,
            "forced_scheme": self.forced_scheme,
            "rank_memory": "relocated_five_arrays" if self.rank_cap == 16 else "v11_original",
            "check_limit_reachable": self.source_4344,
            "overrides": dict(self.overrides),
            "words": {
                "4332": "016000243333636" if self.forced_scheme == "narrow" else "016000343333636",
                "4344": "033402410540000" if self.source_4344 else "033402410570000",
                "4777": f"{self.checks << 39:015o}",
                "1661": f"{self.evaluations << 36:015o}",
            },
        }


def resolve_search_settings(profile=DEFAULT_PROFILE, *, checks=None,
                            evaluations=None, rank_cap=None, source_4344=None,
                            forced_scheme=None):
    if profile not in PROFILES:
        raise ValueError("Неизвестный профиль поиска: " + str(profile))
    overrides = {k: v for k, v in dict(checks=checks, evaluations=evaluations,
                 rank_cap=rank_cap, source_4344=source_4344,
                 forced_scheme=forced_scheme).items() if v is not None}
    values = {**PROFILES[profile], **overrides}
    for name, choices in (("checks", range(5)), ("evaluations", range(1, 6)),
                          ("rank_cap", (14, 16))):
        if type(values[name]) is not int or values[name] not in choices:
            raise ValueError(f"Недопустимое значение {name}: {values[name]}")
    if type(values["source_4344"]) is not bool:
        raise ValueError("source_4344 должен быть логическим значением")
    if values["forced_scheme"] not in ("native", "narrow"):
        raise ValueError("forced_scheme должен быть native либо narrow")
    return SearchSettings(profile=profile, overrides=tuple(overrides.items()), **values)


def apply_search_settings(machine, settings):
    """Change only reconstructed control words; evaluation/CPU remain unchanged."""
    if settings.rank_cap == 16:
        apply_native_rank_capacity(machine, cap=16)
    machine.base[0o4344] = (0o033402410540000 if settings.source_4344
                            else 0o033402410570000)
    machine.base[0o4777] = settings.checks << 39
    machine.base[0o1661] = settings.evaluations << 36
    machine.base[0o4332] = (0o016000243333636 if settings.forced_scheme == "narrow"
                            else 0o016000343333636)
