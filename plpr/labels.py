"""Character classes of the character model (CharsYolo), in class-index order.

Each entry is (code, persian). `code` is the Latin code used in database keys
(e.g. ``34D31966``), kept identical to v1 so existing databases still match.
"""

CHAR_CLASSES: list[tuple[str, str]] = [
    ("0", "۰"), ("1", "۱"), ("2", "۲"), ("3", "۳"), ("4", "۴"),
    ("5", "۵"), ("6", "۶"), ("7", "۷"), ("8", "۸"), ("9", "۹"),
    ("A", "الف"), ("B", "ب"), ("P", "پ"), ("Taxi", "ت"), ("ث", "ث"),
    ("J", "ج"), ("چ", "چ"), ("ح", "ح"), ("خ", "خ"), ("D", "د"),
    ("ذ", "ذ"), ("ر", "ر"), ("ز", "ز"), ("ژ", "ژ"), ("Sin", "س"),
    ("ش", "ش"), ("Sad", "ص"), ("ض", "ض"), ("T", "ط"), ("ظ", "ظ"),
    ("PuV", "ع"), ("غ", "غ"), ("ف", "ف"), ("Gh", "ق"), ("ک", "ک"),
    ("گ", "گ"), ("L", "ل"), ("M", "م"), ("N", "ن"), ("H", "ه"),
    ("V", "و"), ("Y", "ی"), ("PwD", "ژ"),  # PwD: disabled / veterans plate
]

CODE_TO_PERSIAN = {code: fa for code, fa in CHAR_CLASSES}

# Letters that appear on civilian Iranian plates. Anything else is still returned,
# but the read is marked invalid so callers can ask for more frames.
VALID_LETTERS = {"A", "B", "P", "Taxi", "J", "D", "Sin", "Sad", "T", "PuV", "Gh", "L", "M", "N", "H", "V", "Y", "PwD", "ژ", "ش", "ک", "ز"}

# Plate type implied by the letter (colour classifier is future work, see PLAN).
LETTER_TYPE = {
    "Taxi": "taxi", "PuV": "public", "A": "government", "PwD": "disabled",
    "Sad": "police", "P": "police", "Sin": "public", "Gh": "military", "ش": "military",
}

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_TO_LATIN = str.maketrans({**{fa: str(i) for i, fa in enumerate(FA_DIGITS)}, **{"٠١٢٣٤٥٦٧٨٩"[i]: str(i) for i in range(10)}})
_TO_PERSIAN = str.maketrans({str(i): fa for i, fa in enumerate(FA_DIGITS)})


def to_latin_digits(s: str) -> str:
    """Persian and Arabic-Indic digits -> ASCII digits."""
    return s.translate(_TO_LATIN)


def to_persian_digits(s: str) -> str:
    return s.translate(_TO_PERSIAN)


def normalize_persian(s: str) -> str:
    """Arabic presentation letters -> Persian (ي->ی, ك->ک), strip ZWJ/ZWNJ."""
    return s.replace("ي", "ی").replace("ك", "ک").replace("‍", "").replace("‌", "")
