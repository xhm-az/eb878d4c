"""Run the public contract suite only: standard library, no models/benchmarks."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from tools.model_free_guard import model_free_boundary


def contract_exit_code(result: unittest.TestResult) -> int:
    """An empty or partially skipped run is not completed contract validation."""
    complete = result.testsRun > 0 and not result.skipped and not result.expectedFailures
    return 0 if complete and result.wasSuccessful() else 1


def main() -> int:
    with model_free_boundary():
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("Scope: model-free synthetic contracts only; not PTA or benchmark validation.")
    status = contract_exit_code(result)
    if status:
        print("Contract validation failed or was incomplete; empty/skipped cases are not accepted.")
    return status


if __name__ == "__main__":
    sys.exit(main())
