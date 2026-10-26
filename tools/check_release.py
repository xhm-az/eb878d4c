"""Static text/AST release check. Never imports or executes pacc_review."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


ALLOWED_FILES = frozenset({
    ".gitignore", "pyproject.toml", "README.md", "README_zh.md", "DISCLOSURE.md",
    "docs/METHOD_MAP.md", "docs/INTEGRATION.md", "docs/VALIDATION.md",
    "docs/REVIEW_GUIDE.md",
    "docs/SCORING.md",
    "configs/settings.schema.json", "examples/final_action_hook.py",
    "examples/__init__.py", "examples/synthetic_support.py", "examples/control_flow_demo.py",
    "examples/scoring_support.py", "examples/scoring_demo.py",
    "src/pacc_review/__init__.py", "src/pacc_review/config.py",
    "src/pacc_review/controller.py",
    "src/pacc_review/diagnostics.py",
    "src/pacc_review/conditions.py", "src/pacc_review/scoring.py", "src/pacc_review/scoring_evaluator.py",
    "src/pacc_review/evidence.py", "src/pacc_review/ports.py",
    "src/pacc_review/types.py", "tools/check_release.py",
    "tools/__init__.py", "tools/model_free_guard.py", "tools/run_contract_tests.py",
    "tests/__init__.py", "tests/test_controller.py", "tests/test_diagnostics.py",
    "tests/test_evidence.py", "tests/test_public_contracts.py",
    "tests/test_scoring.py",
})


def check(root: Path) -> dict:
    issues: list[str] = []
    files = {p.relative_to(root).as_posix(): p for p in root.rglob("*")
             if p.is_file() and ".git" not in p.relative_to(root).parts}
    for rel in sorted(set(files) - ALLOWED_FILES):
        issues.append("Unlisted release file: " + rel)
    for rel in sorted(ALLOWED_FILES - set(files)):
        issues.append("Missing release file: " + rel)
    trees: dict[str, ast.Module] = {}
    contents: dict[str, str] = {}
    patterns = {
        "personal absolute path": r"(?:[A-Za-z]:[/\\](?:Users|codex_workspace)|/(?:home)/[^ /]+|/(?:root)/)",
        "credential-like string": r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)",
        "percentage-like result": r"\d+(?:\.\d+)?\s*%",
        "email-like identity": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "IPv4-like endpoint": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "account-bearing repository link": r"github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+",
    }
    for rel, path in sorted(files.items()):
        if rel not in ALLOWED_FILES:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeError:
            issues.append("Invalid UTF-8: " + rel)
            continue
        contents[rel] = source
        if source.startswith("\ufeff") or "\ufffd" in source:
            issues.append("Unexpected BOM/replacement character: " + rel)
        for index, line in enumerate(source.splitlines(), start=1):
            for label, pattern in patterns.items():
                if re.search(pattern, line, re.I):
                    issues.append(f"{label}: {rel}:{index}")
        if path.suffix == ".py":
            try:
                tree = ast.parse(source, filename=rel)
                compile(tree, rel, "exec")  # Creates a code object; never executes it.
                trees[rel] = tree
            except SyntaxError as exc:
                issues.append(f"Invalid syntax: {rel}:{exc.lineno}")
        elif path.suffix == ".json":
            try:
                json.loads(source)
            except json.JSONDecodeError:
                issues.append("Invalid JSON: " + rel)
        elif path.suffix == ".toml" and tomllib is not None:
            try:
                tomllib.loads(source)
            except tomllib.TOMLDecodeError:
                issues.append("Invalid TOML: " + rel)
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", source):
                if re.match(r"(?:https?://|mailto:|#)", target):
                    continue
                local = target.split("#", 1)[0]
                if not (path.parent / local).is_file():
                    issues.append("Broken local link: " + rel)
    for rel, tree in trees.items():
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            if isinstance(node, ast.ImportFrom) and node.level:
                parts = list(Path(rel).parent.parts)
                for _ in range(node.level - 1):
                    if parts:
                        parts.pop()
                module_path = root.joinpath(*parts, *(module or "").split("."))
                if not (module_path.with_suffix(".py").is_file()
                        or (module_path / "__init__.py").is_file()):
                    issues.append(f"Unresolved local module: {rel}:{node.lineno}")
            if module and module.startswith("pacc_review"):
                module_path = root / "src" / module.replace(".", "/")
                if not (module_path.with_suffix(".py").is_file()
                        or (module_path / "__init__.py").is_file()):
                    issues.append(f"Unresolved public module: {rel}:{node.lineno}")
    try:
        schema = json.loads(contents.get("configs/settings.schema.json", "{}"))
    except json.JSONDecodeError:
        schema = {}

    def check_no_values(value):
        if isinstance(value, dict):
            if "default" in value or "examples" in value or "const" in value:
                issues.append("Settings schema contains a concrete default/example/constant")
            for child in value.values():
                check_no_values(child)
        elif isinstance(value, list):
            for child in value:
                check_no_values(child)

    check_no_values(schema)
    if set(schema.get("properties", {})) != {"variant"}:
        issues.append("Public settings schema must expose only mode selection")
    if schema.get("additionalProperties") is not False:
        issues.append("Public settings schema must reject extra configuration fields")
    config_tree = trees.get("src/pacc_review/config.py")
    if config_tree is not None:
        settings = [n for n in config_tree.body if isinstance(n, ast.ClassDef) and n.name == "PACCSettings"]
        fields = {n.target.id for c in settings for n in c.body
                  if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
        if fields != {"variant"}:
            issues.append("Public settings class must expose only mode selection")
    required_notices = {
        "README.md": ("partial source release", "No models or benchmark experiments have been run",
                      "The full source code will be released upon acceptance of the paper."),
        "README_zh.md": ("部分参考源码", "未运行模型、真实环境或基准实验", "论文接收后，将完整公开源代码"),
        "DISCLOSURE.md": ("not sufficient for independent reproduction",
                          "The full source code will be released upon acceptance of the paper."),
    }
    for rel, notices in required_notices.items():
        for notice in notices:
            if notice not in contents.get(rel, ""):
                issues.append("Missing release-scope notice: " + rel)
    for rel in ("README.md", "README_zh.md", "docs/VALIDATION.md"):
        if re.search(r"No tests, models|未运行测试、模型|Only static.*have been performed",
                     contents.get(rel, ""), re.I):
            issues.append("Outdated unrun-test notice: " + rel)
    return {"status": "passed" if not issues else "failed",
            "scope": "static text and AST only; no package imports or tests",
            "git_history_checked": False,
            "remote_hosting_checked": False,
            "withheld_implementations_checked": False,
            "python_files_checked": len(trees),
            "toml_parsed": tomllib is not None,
            "issues": issues}


def main() -> int:
    report = check(Path(__file__).resolve().parents[1])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
