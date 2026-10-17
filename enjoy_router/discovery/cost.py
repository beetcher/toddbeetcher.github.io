"""Cost: the estimate shown before Go, the exact cost of a step, and the per-step limits that keep a run inside its cap (rule D-4).

Product-blind. Money is whole US cents, always rounded UP, so a cap is never underestimated. Prices are per million tokens
(and per 1,000 searches) and come from the model entry. The numbers below are named so they can be tuned in one place; the
Console's estimate is a range, and the hard cap is enforced by the per-step check, not by the estimate.
"""
from __future__ import annotations

import math
from fractions import Fraction

CHARS_PER_TOKEN = 3                 # conservative: real text is nearer 4 characters a token, so input is overestimated
PROMPT_OVERHEAD_TOKENS = 50
EXPECTED_TOKENS_PER_RESULT = 260
EXPECTED_OVERHEAD_TOKENS = 150
LOW_FACTOR = Fraction(6, 10)
MAX_SEARCHES_PER_STEP = 5
DEFAULT_MAX_OUTPUT_TOKENS = 8192
MIN_USEFUL_OUTPUT_TOKENS = 400


def tokens_from_chars(n: int) -> int:
    return -(-int(n) // CHARS_PER_TOKEN) + PROMPT_OVERHEAD_TOKENS


def _exact(model, input_tokens: int, output_tokens: int, searches: int) -> Fraction:
    total = Fraction(input_tokens * model.price_input_per_million_cents, 1_000_000)
    total += Fraction(output_tokens * model.price_output_per_million_cents, 1_000_000)
    if model.price_search_per_1000_cents:
        total += Fraction(searches * model.price_search_per_1000_cents, 1000)
    return total


def cost_cents(model, input_tokens: int, output_tokens: int, searches: int = 0) -> int:
    """What a call costs, in whole cents, rounded up."""
    return math.ceil(_exact(model, max(0, input_tokens), max(0, output_tokens), max(0, searches)))


def max_searches(model) -> int:
    return MAX_SEARCHES_PER_STEP if model.has_grounding else 0


def output_cap(model) -> int:
    return model.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS


def step_limits(model, prompt_chars: int, remaining_cents: int):
    """(max_output_tokens, max_searches) for one step so its WORST case cannot exceed remaining_cents, or None when even a
    minimal useful answer would not fit (the run then stops: cap_reached)."""
    n_in, searches, cap_out = tokens_from_chars(prompt_chars), max_searches(model), output_cap(model)
    if cost_cents(model, n_in, cap_out, searches) <= remaining_cents:
        return cap_out, searches
    base = _exact(model, n_in, 0, searches)
    room = Fraction(remaining_cents) - base
    if room < 0:
        return None
    price = model.price_output_per_million_cents
    out = cap_out if price == 0 else min(cap_out, math.floor(room * 1_000_000 / price))
    if out < MIN_USEFUL_OUTPUT_TOKENS:
        return None
    return out, searches


def estimate(model, prompt_chars_per_step: list, results_per_step: list):
    """(low, high) in cents for the whole run. High is every step at its output cap with the most searches; low is an expected
    answer at 60% with one search. Both are rounded up."""
    low = high = 0
    cap_out, s_hi = output_cap(model), max_searches(model)
    for chars, n in zip(prompt_chars_per_step, results_per_step):
        n_in = tokens_from_chars(chars)
        expected = min(cap_out, n * EXPECTED_TOKENS_PER_RESULT + EXPECTED_OVERHEAD_TOKENS)
        high += cost_cents(model, n_in, cap_out, s_hi)
        low += math.ceil(_exact(model, n_in, math.ceil(expected * LOW_FACTOR), 1 if s_hi else 0))
    return min(low, high), high
