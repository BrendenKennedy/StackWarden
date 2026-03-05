"""Typed errors for application-layer flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppConflictError(Exception):
    message: str


@dataclass
class AppValidationError(Exception):
    errors: list[dict[str, str]]


@dataclass
class AppNotFoundError(Exception):
    message: str


@dataclass
class AppInternalError(Exception):
    message: str
