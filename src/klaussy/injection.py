# Copyright 2026 Dovatech LLC. SPDX-License-Identifier: FSL-1.1-MIT
"""Prompt-injection markers, for code that runs outside the agent.

The patterns live in the read-injection guard hook, which klaussy copies into repos and so has to
stay a standalone script. This loads that file, so there's one list.
"""

from __future__ import annotations

import importlib.util
from functools import cache
from importlib import resources
from types import ModuleType

Finding = tuple[int, str, str]


@cache
def _guard() -> ModuleType:
    path = (
        resources.files("klaussy")
        .joinpath("templates")
        .joinpath("hooks")
        .joinpath("read_injection_guard.py")
    )
    spec = importlib.util.spec_from_file_location("klaussy_read_injection_guard", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"can't load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scan(text: str, path: str = "") -> list[Finding]:
    """(line, label, matched text) for each injection marker in `text`. A config `path` skips the
    role-prefix pattern, since `system:` is ordinary YAML."""
    return _guard().scan(text, path)


def is_test_source(path: str) -> bool:
    """A repo's own test code, which may hold injection strings on purpose."""
    return _guard()._is_test_source(path)
