"""Persian plate grammar: 2 digits, letter, 3 digits, 2-digit province code."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .labels import CODE_TO_PERSIAN, LETTER_TYPE, VALID_LETTERS, to_latin_digits, to_persian_digits

_KEY_RE = re.compile(r"^(\d{2})([A-Za-z]+|[؀-ۿ])(\d{3})(\d{2})$")


@dataclass(frozen=True)
class PlateNumber:
    left: str    # 2 digits
    letter: str  # Latin code, e.g. "B", "Sin", "Taxi"
    middle: str  # 3 digits
    region: str  # 2 digits (province code in the "ایران" box)

    @property
    def key(self) -> str:
        """Database key, same format as v1: ``34D31966``."""
        return f"{self.left}{self.letter}{self.middle}{self.region}"

    @property
    def latin(self) -> str:
        return f"{self.left} {self.letter} {self.middle} - {self.region}"

    @property
    def persian(self) -> str:
        return to_persian_digits(f"{self.left} {CODE_TO_PERSIAN.get(self.letter, self.letter)} {self.middle} - ایران {self.region}")

    @property
    def valid(self) -> bool:
        return self.letter in VALID_LETTERS and self.region != "00"

    @property
    def plate_type(self) -> str:
        return LETTER_TYPE.get(self.letter, "private")

    @classmethod
    def from_key(cls, key: str) -> PlateNumber | None:
        m = _KEY_RE.match(to_latin_digits(key.replace(" ", "").replace("-", "")))
        return cls(*m.groups()) if m else None


def parse_codes(codes: list[str]) -> PlateNumber | None:
    """Turn left-to-right character codes into a plate, or None if the layout is wrong.

    Expects exactly 8 symbols: d d L d d d d d. Extra boxes (duplicates, the
    "ایران" text, the flag) should already be filtered by the caller.
    """
    if len(codes) != 8:
        return None
    digits_ok = all(c.isdigit() for i, c in enumerate(codes) if i != 2)
    if not digits_ok or codes[2].isdigit():
        return None
    return PlateNumber("".join(codes[0:2]), codes[2], "".join(codes[3:6]), "".join(codes[6:8]))
