"""Explicit, opt-in Stanford §4 admission rules; listing remains the default."""
from dataclasses import dataclass
import re

VARIANTS = {'listing': 0, 'narrow': 1, 'checks': 2, 'wide': 3}
MAX_CHECKS = 99
LABELS = {'listing': 'по листингу', 'narrow': 'узкий: только взятия',
          'checks': 'лимит шахов на сторону', 'wide': 'широкий: все шахи'}


@dataclass(frozen=True)
class ForcedPlay:
    variant: str = 'listing'
    checks_per_side: int = 2

    def __post_init__(self):
        if self.variant not in VARIANTS:
            raise ValueError('Неизвестный вариант форсированной игры.')
        if type(self.checks_per_side) is not int or not 0 <= self.checks_per_side <= MAX_CHECKS:
            raise ValueError(f'Число шахов на сторону: целое от 0 до {MAX_CHECKS}.')

    def metadata(self):
        n=self.checks_per_side
        noun='шахов' if n%100 in range(11,15) or n%10 not in (1,2,3,4) else ('шаха' if n%10!=1 else 'шах')
        return {'variant': self.variant, 'checks_per_side': self.checks_per_side,
                'label': (f'лимит {n} {noun} на сторону'
                          if self.variant == 'checks' else LABELS[self.variant])}

    def tag(self):
        return f'checks:{self.checks_per_side}' if self.variant == 'checks' else self.variant

    @classmethod
    def from_metadata(cls, value):
        value = value or {}
        return cls(value.get('variant', 'listing'), value.get('checks_per_side', 2))

    @classmethod
    def from_headers(cls, headers):
        # Absence of the new tag always means listing, including old PGNs.
        return cls(headers.get('M20ForcedPlay', 'listing'),
                   int(headers.get('M20ChecksPerSide', '2')))


def comment_tag(comment, fallback='listing'):
    tags = re.findall(r'\[%m20_forced (listing|narrow|wide|checks:\d+)\]', comment)
    if not tags:
        return fallback
    tag = tags[-1]
    if tag.startswith('checks:'):
        ForcedPlay('checks', int(tag.split(':')[1]))
    return tag
