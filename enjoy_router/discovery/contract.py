"""The Discovery contract: the shapes the core and the product exchange (claude/discovery-module-plan.md sections 6, 7 and 14).

Product-blind (rule D-1): standard library only, and no word about what a finder finds. A finder is DATA plus two small functions;
the product supplies everything else through the ports in ports.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

CONTRACT_VERSION = 1

MODES = ("off", "dry_run", "live")
RUN_STATUSES = ("planned", "running", "finished", "stopped", "failed", "withdrawn")
STOP_REASONS = ("cap_reached", "results_limit", "operator", "mode_off", "too_many_no_answers")
STEP_STATUSES = ("ok", "no_answer", "rejected", "skipped")
MARKS = ("sure", "verify")
TIERS = ("needed", "optional")
ATTENTION_CODES = ("no_street_address", "address_not_matched", "operator_unconfirmed")
SINK_STATUSES = ("saved", "duplicate", "rejected")

# Limits that keep one run record small enough for the database (discovery_run.schema.json mirrors them).
MAX_STEPS = 40
MAX_STORED_PROMPT = 8000
MAX_IDS = 1000
MAX_REJECTIONS = 100
MAX_SOURCE_URLS = 20


@dataclass(frozen=True)
class FieldSpec:
    """One thing the AI is asked for. tier: needed (a candidate without it is rejected) or optional (simply absent when unknown).
    schema is a JSON Schema fragment for the value; the product builds it from the target record's own schema, so there is
    one definition of types and limits."""
    key: str
    description: str
    tier: str
    schema: dict


@dataclass(frozen=True)
class Finder:
    """What a run looks for. dedupe_key(values) -> a string that is equal for two candidates that are the same thing, or None.
    must_be_true maps a needed yes/no field to the rejection reason used when the AI does not say true (for example a
    'open to the public' field). attention_if_missing maps an optional field to the attention code used when it is absent.
    assume_if_missing maps a needed field to the value assumed when the AI leaves that field out entirely: the candidate is kept
    with that value marked verify (Check) instead of being rejected. A value the AI DOES give (for example false) is never overridden."""
    key: str
    name: str
    result_key: str
    ask_fields: tuple
    dedupe_key: Callable[[dict], Optional[str]]
    placeholders: tuple = ("territory", "types", "fields", "max_results")
    must_be_true: dict = field(default_factory=dict)
    attention_if_missing: dict = field(default_factory=dict)
    assume_if_missing: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelEntry:
    id: str
    provider: str
    model_name: str
    label: str
    price_input_per_million_cents: int
    price_output_per_million_cents: int
    price_search_per_1000_cents: Optional[int] = None
    max_output_tokens: Optional[int] = None
    has_grounding: bool = False
    key_name: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class AreaEntry:
    """A state or a region. state_is_active is the switch of the state a region lies in (a region inside an off state cannot run)."""
    id: str
    label: str
    kind: str
    state_code: str
    is_active: bool
    state_is_active: bool
    zip_codes: tuple = ()


@dataclass(frozen=True)
class TypeEntry:
    key: str
    label: str
    search_hint: str = ""
    is_chain: bool = False
    is_active: bool = True


@dataclass(frozen=True)
class PromptEntry:
    id: str
    version: int
    text: str


@dataclass(frozen=True)
class Limits:
    max_spend_cap_cents: int
    max_results_per_run: int
    results_per_step: int
    default_spend_cap_cents: int = 0
    default_model_id: Optional[str] = None


@dataclass(frozen=True)
class RunRequest:
    finder_key: str
    model_id: str
    area_ids: tuple
    type_keys: tuple
    max_results: int
    spend_cap_cents: int


@dataclass(frozen=True)
class ProviderRequest:
    """What an adapter receives. It carries the NAME of the setting that holds the key (key_name), never a key (D-11)."""
    provider: str
    model_name: str
    key_name: Optional[str]
    prompt: str
    max_output_tokens: int
    max_searches: int
    use_grounding: bool
    timeout_s: int = 45


@dataclass(frozen=True)
class ProviderResult:
    """outcome: ok (answered), rejected (the provider refused it) or no_answer (we cannot say). error_code is a short code, never
    provider text (D-2). Usage is what the provider reported."""
    outcome: str
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0
    error_code: Optional[str] = None


@dataclass
class Candidate:
    """One result before a person activates it. fields: {key: {"value", "mark", "source_url"?}}. block is the AI block for the
    record (see schemas/discovery_mark.fragment.json), built by marks.build_block."""
    key: str
    label: str
    fields: dict
    source_urls: list = field(default_factory=list)
    attention_reasons: list = field(default_factory=list)
    block: dict = field(default_factory=dict)

    def values(self) -> dict:
        return {k: v["value"] for k, v in self.fields.items()}


@dataclass(frozen=True)
class SinkContext:
    run_id: str
    finder_key: str
    model_name: str
    prompt_version: int
    by: str
    now: Any


@dataclass(frozen=True)
class SinkResult:
    """status: saved, duplicate or rejected. record_status must be 'inactive' when saved (D-6). ids: {kind: [id, ...]} for every
    record the save created (the core files them on the run as created_<kind> so Withdraw can take them back).
    attention_reasons: extra reasons the sink found (for example the address did not match)."""
    status: str
    reason: Optional[str] = None
    record_status: Optional[str] = None
    ids: dict = field(default_factory=dict)
    attention_reasons: tuple = ()


@dataclass(frozen=True)
class WithdrawResult:
    removed: dict
    kept: list = field(default_factory=list)


@dataclass(frozen=True)
class Reply:
    """What the engine's calls return. ok False carries a closed reason in code and a plain message."""
    ok: bool
    code: str = "ok"
    message: str = ""
    data: dict = field(default_factory=dict)
