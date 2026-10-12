"""Deterministic, run-scoped guardrails for stalled tool traces.

This module detects observable repetition and audits claims about tool execution.
It does not infer whether arbitrary natural-language claims are true.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable


def _fingerprint(value: Any) -> str:
    """Hash JSON-compatible data without storing raw arguments in findings."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ToolObservation:
    tool_name: str
    arguments: Any
    result: Any = None
    status: str = "success"
    progress: bool = False
    event_id: str | None = None

    def __post_init__(self) -> None:
        if not self.tool_name.strip():
            raise ValueError("tool_name must be non-empty")
        if not self.status.strip():
            raise ValueError("status must be non-empty")
        _fingerprint(self.arguments)
        _fingerprint(self.result)

    @property
    def call_fingerprint(self) -> str:
        return _fingerprint({"tool": self.tool_name, "arguments": self.arguments})

    @property
    def outcome_fingerprint(self) -> str:
        return _fingerprint({"status": self.status, "result": self.result})


@dataclass(frozen=True)
class GuardrailFinding:
    code: str
    severity: str
    message: str
    event_ids: tuple[str, ...]
    recommendation: str


@dataclass(frozen=True)
class ExecutionClaimAudit:
    status: str
    reason: str
    matched_event_ids: tuple[str, ...]


class LoopDetector:
    """Detect exact repeats, short oscillations, and failure cascades.

    progress=True must be supplied by the harness from an observable milestone,
    not from model self-assessment alone. This detector sees only supplied events.
    """

    FAILURE_STATUSES = frozenset({"error", "failed", "blocked", "timeout"})

    def __init__(
        self,
        *,
        window_size: int = 12,
        repeat_threshold: int = 3,
        cycle_repeats: int = 3,
        failure_threshold: int = 4,
        max_cycle_length: int = 4,
    ) -> None:
        if window_size < 3:
            raise ValueError("window_size must be at least 3")
        if repeat_threshold < 3 or cycle_repeats < 2 or failure_threshold < 2:
            raise ValueError("thresholds are too small to distinguish a pattern")
        if max_cycle_length < 2:
            raise ValueError("max_cycle_length must be at least 2")
        self.window_size = window_size
        self.repeat_threshold = repeat_threshold
        self.cycle_repeats = cycle_repeats
        self.failure_threshold = failure_threshold
        self.max_cycle_length = max_cycle_length
        self._events: deque[ToolObservation] = deque(maxlen=window_size)

    @property
    def observations(self) -> tuple[ToolObservation, ...]:
        return tuple(self._events)

    def reset(self) -> None:
        self._events.clear()

    def observe(self, event: ToolObservation) -> tuple[GuardrailFinding, ...]:
        if event.progress:
            self._events.clear()
        self._events.append(event)
        events = tuple(self._events)
        findings: list[GuardrailFinding] = []

        if len(events) >= self.repeat_threshold:
            tail = events[-self.repeat_threshold:]
            same_call = len({item.call_fingerprint for item in tail}) == 1
            same_outcome = len({item.outcome_fingerprint for item in tail}) == 1
            if same_call and same_outcome:
                findings.append(GuardrailFinding(
                    code="EXACT_REPEAT_NO_PROGRESS",
                    severity="high",
                    message=f"The same tool call and outcome repeated {len(tail)} times without an observed progress milestone.",
                    event_ids=tuple(item.event_id for item in tail if item.event_id),
                    recommendation="Stop automatic retries; inspect the repeated result and require a changed strategy or verified progress.",
                ))

        if not findings:
            cycle = self._repeated_cycle(events)
            if cycle:
                findings.append(GuardrailFinding(
                    code="OSCILLATION_NO_PROGRESS",
                    severity="high",
                    message=f"A tool-call cycle of length {cycle[0]} repeated {cycle[1]} times without an observed progress milestone.",
                    event_ids=tuple(item.event_id for item in events[-cycle[0] * cycle[1]:] if item.event_id),
                    recommendation="Break the cycle and re-plan using recorded observations; do not replay the same sequence automatically.",
                ))

        if len(events) >= self.failure_threshold:
            tail = events[-self.failure_threshold:]
            if all(item.status.lower() in self.FAILURE_STATUSES for item in tail):
                findings.append(GuardrailFinding(
                    code="CONSECUTIVE_FAILURE_CASCADE",
                    severity="critical",
                    message=f"{len(tail)} consecutive tool observations failed or were blocked.",
                    event_ids=tuple(item.event_id for item in tail if item.event_id),
                    recommendation="Stop further automated tool calls and surface the distinct failures for diagnosis.",
                ))
        return tuple(findings)

    def _repeated_cycle(self, events: tuple[ToolObservation, ...]) -> tuple[int, int] | None:
        signatures = tuple((e.call_fingerprint, e.outcome_fingerprint) for e in events)
        max_len = min(self.max_cycle_length, len(signatures) // self.cycle_repeats)
        for length in range(2, max_len + 1):
            suffix = signatures[-length * self.cycle_repeats:]
            pattern = suffix[:length]
            if all(
                suffix[start:start + length] == pattern
                for start in range(length, len(suffix), length)
            ):
                return length, self.cycle_repeats
        return None


def audit_execution_claim(
    *,
    tool_name: str,
    claimed_success: bool,
    observations: Iterable[ToolObservation],
    trace_complete: bool,
) -> ExecutionClaimAudit:
    """Audit a claim that a named tool ran successfully.

    SUPPORTED means only that a matching successful observation exists; it does
    not prove the tool's output is correct. Missing evidence is UNKNOWN unless
    the caller can attest that the supplied trace is complete.
    """
    matching = tuple(event for event in observations if event.tool_name == tool_name)
    ids = tuple(event.event_id for event in matching if event.event_id)
    successful = tuple(event for event in matching if event.status.lower() in {"success", "ok", "passed"})
    if claimed_success and successful:
        return ExecutionClaimAudit(
            "SUPPORTED",
            "A matching successful tool observation exists; semantic correctness remains unverified.",
            tuple(event.event_id for event in successful if event.event_id),
        )
    if claimed_success and not successful:
        if trace_complete and matching:
            return ExecutionClaimAudit("CONTRADICTED", "The complete trace contains the named tool, but no successful outcome.", ids)
        if trace_complete:
            return ExecutionClaimAudit("CONTRADICTED", "The complete trace contains no observation of the claimed tool execution.", ())
        return ExecutionClaimAudit("UNKNOWN", "No successful observation was found, and trace completeness is not established.", ids)
    if not claimed_success and successful:
        return ExecutionClaimAudit("CONTRADICTED", "The trace records a successful outcome despite the claim that execution did not succeed.", tuple(event.event_id for event in successful if event.event_id))
    if matching:
        return ExecutionClaimAudit("SUPPORTED", "The trace contains no successful outcome for the named tool.", ids)
    if trace_complete:
        return ExecutionClaimAudit("SUPPORTED", "The complete trace contains no execution of the named tool.", ())
    return ExecutionClaimAudit("UNKNOWN", "The trace is incomplete, so absence of an execution cannot be established.", ())
