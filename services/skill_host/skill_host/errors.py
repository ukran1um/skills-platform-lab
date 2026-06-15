"""Host errors, mapped to HTTP by the API layer."""

from __future__ import annotations


class HostError(Exception):
    """Base for all skill-host errors."""


class SkillNotFoundError(HostError):
    """No skill directory / registry record by that name (-> 404)."""


class SkillNotBlessedError(HostError):
    """The skill exists but reconcile did not bless it (-> 403)."""


class EntitlementError(HostError):
    """The user is unknown or lacks a scope the skill requires (-> 403)."""
