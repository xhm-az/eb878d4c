"""Block model runtimes and socket networking for the supplied local checks.

This is an accidental-use guard for trusted tests, not a security sandbox for
arbitrary code. It does not certify isolation against malicious subprocesses.
"""
from __future__ import annotations

import importlib.abc
import sys
from contextlib import contextmanager
from unittest.mock import patch


BLOCKED_IMPORTS = frozenset({"torch", "transformers", "accelerate", "datasets",
                             "huggingface_hub", "tokenizers", "requests", "httpx", "pacc"})


class ModelRuntimeBlocked(ImportError):
    pass


class NetworkBlocked(RuntimeError):
    pass


class _RejectRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in BLOCKED_IMPORTS:
            raise ModelRuntimeBlocked("Model/network runtime excluded from model-free checks")
        return None


@contextmanager
def model_free_boundary():
    if any(name.split(".", 1)[0] in BLOCKED_IMPORTS for name in sys.modules):
        raise RuntimeError("Start a fresh interpreter without model/network runtimes")
    guard = _RejectRuntime()
    sys.meta_path.insert(0, guard)
    try:
        with patch("socket.socket", side_effect=NetworkBlocked("Networking disabled")), \
                patch("socket.create_connection", side_effect=NetworkBlocked("Networking disabled")):
            yield
    finally:
        sys.meta_path.remove(guard)
