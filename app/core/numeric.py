from __future__ import annotations

import re

NUMERIC_VALUE_RE = re.compile(r"^(?:\d+|\d{1,3}(?: \d{3})+)(?:\.\d+)?$")


def is_valid_numeric_value(value: str) -> bool:
    return bool(NUMERIC_VALUE_RE.fullmatch(value.strip()))


def format_numeric_value(value: str) -> str:
    normalized = value.strip()
    if not is_valid_numeric_value(normalized):
        raise ValueError(f"Invalid numeric value: {value}")

    compact = normalized.replace(" ", "")
    if "." in compact:
        integer_part, fractional_part = compact.split(".", 1)
    else:
        integer_part, fractional_part = compact, ""

    canonical_integer = str(int(integer_part)) if integer_part else "0"
    grouped_integer_parts: list[str] = []
    remaining = canonical_integer
    while len(remaining) > 3:
        grouped_integer_parts.append(remaining[-3:])
        remaining = remaining[:-3]
    grouped_integer_parts.append(remaining)
    formatted_integer = " ".join(reversed(grouped_integer_parts))

    if fractional_part:
        return f"{formatted_integer}.{fractional_part}"
    return formatted_integer
