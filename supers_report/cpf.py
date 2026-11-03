"""Algorithmic CPF (Brazilian individual taxpayer number) validation.

Only the check-digit algorithm lives here. No real CPF is stored anywhere in
this repository; tests and demo data use synthetic numbers produced by
``generate_cpf``. They are FICTIONAL.
"""
from __future__ import annotations

import random
import re


def normalize_cpf(value: str) -> str:
    """Keep only digits."""
    return re.sub(r"\D", "", value or "")


def _check_digit(digits: str) -> str:
    weight = len(digits) + 1
    total = sum(int(d) * w for d, w in zip(digits, range(weight, 1, -1)))
    rest = (total * 10) % 11
    return str(0 if rest == 10 else rest)


def is_valid_cpf(value: str) -> bool:
    """True when the value has 11 digits, is not a repeated digit and both
    check digits match."""
    digits = normalize_cpf(value)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    first = _check_digit(digits[:9])
    second = _check_digit(digits[:9] + first)
    return digits[9:] == first + second


def is_masked_cpf(value: str) -> bool:
    """True for partially hidden values such as ``123.XXX.XXX-45``. They keep
    only a few real digits, so they are not unique and must never be used as a
    grouping key."""
    return bool(value) and bool(re.search(r"[xX*]", value))


def generate_cpf(rng: random.Random) -> str:
    """Generate a synthetic, algorithmically valid (fictional) CPF."""
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(9))
        if len(set(base)) == 1:
            continue
        first = _check_digit(base)
        return base + first + _check_digit(base + first)


def mask_cpf(value: str) -> str:
    """Mask the way the source system does: keep 3 leading and 2 trailing digits."""
    d = normalize_cpf(value)
    return f"{d[:3]}.XXX.XXX-{d[9:]}"
