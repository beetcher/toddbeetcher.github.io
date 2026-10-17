"""The ports: what the product supplies to Discovery (plan section 7). The core knows only these shapes (D-1).

The product implements them in its own package (step 3 of the plan). Memory versions for tests live in memory_stores.py, and
contract_kit.py holds the tests every implementation must pass.
"""
from __future__ import annotations

from typing import Optional, Protocol

from .contract import (AreaEntry, ModelEntry, ProviderRequest, ProviderResult, PromptEntry, Limits, Candidate, SinkContext, SinkResult,
                       TypeEntry, WithdrawResult)


class ModelProvider(Protocol):
    """One AI company's service. Never raises; never returns provider text or a key (D-2, D-11)."""
    name: str

    def generate(self, request: ProviderRequest) -> ProviderResult: ...


class AreaDirectory(Protocol):
    def resolve(self, area_ids: tuple) -> list:
        """AreaEntry for each id that exists (unknown ids are simply missing from the list)."""


class Catalog(Protocol):
    """The settings the operator edits as data."""
    def get_model(self, model_id: str) -> Optional[ModelEntry]: ...
    def list_types(self, finder_key: str) -> list: ...                       # every TypeEntry of the finder, active or not
    def published_prompt(self, finder_key: str) -> Optional[PromptEntry]: ...  # the standing published prompt, or None
    def get_prompt(self, prompt_id: str) -> Optional[PromptEntry]: ...
    def limits(self) -> Limits: ...


class RunStore(Protocol):
    """Run records. There is deliberately NO delete: the run record is history and is never removed (D-12)."""
    def create(self, run: dict, by: str, now) -> str: ...
    def update(self, run_id: str, changes: dict, by: str, now) -> None: ...
    def get(self, run_id: str) -> Optional[dict]: ...


class CandidateSink(Protocol):
    def save(self, candidate: Candidate, ctx: SinkContext) -> SinkResult:
        """Save one candidate as an INACTIVE record, or report it a duplicate or a rejection (D-6, D-7)."""

    def withdraw(self, run: dict, by: str, now) -> WithdrawResult:
        """Take back what the run created (the run's created_* lists), except records a person has activated, edited or used (D-13)."""
