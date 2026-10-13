"""Fail-closed per-action authorization contracts.

The caller must supply subject_id from an authenticated identity source.
This module does not authenticate identities or create an OS security boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from .models import Task


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    subject_id: str
    action: str
    resource_id: str
    target_field: str

    def __post_init__(self) -> None:
        for name in ("subject_id", "action", "resource_id", "target_field"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    decision_id: str
    reason: str

    def __post_init__(self) -> None:
        if type(self.allowed) is not bool:
            raise TypeError("allowed must be a bool")
        for name in ("decision_id", "reason"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")


class Authorizer(Protocol):
    def authorize(
        self, task: Task, request: AuthorizationRequest
    ) -> AuthorizationDecision: ...


class ExactMatchAuthorizer:
    """Reference policy for exact (subject, action, resource) grants.

    Production callers must obtain subject_id from a trusted authentication
    layer and load grants from an authoritative policy source.
    """

    def __init__(self, grants: set[tuple[str, str, str]] | frozenset[tuple[str, str, str]]) -> None:
        normalized = frozenset(grants)
        if any(
            not isinstance(grant, tuple)
            or len(grant) != 3
            or any(not isinstance(part, str) or not part.strip() for part in grant)
            for grant in normalized
        ):
            raise ValueError("grants must contain (subject_id, action, resource_id) string tuples")
        self._grants = normalized

    def authorize(
        self, task: Task, request: AuthorizationRequest
    ) -> AuthorizationDecision:
        allowed = (request.subject_id, request.action, request.resource_id) in self._grants
        return AuthorizationDecision(
            allowed=allowed,
            decision_id=uuid4().hex,
            reason="exact grant matched" if allowed else "no exact grant matched",
        )
