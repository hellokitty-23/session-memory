#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from session_memory_common import (
    iter_resolution_summary,
    resolve_memory_paths,
    run_preflight,
)


def detect_git_branch(workspace: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "--abbrev-ref", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None

    branch = completed.stdout.strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def detect_work_context(workspace: Path, paths: dict[str, object]) -> str:
    branch = detect_git_branch(workspace)
    space_name = str(paths.get("space_name") or "").strip()
    context_root = Path(paths.get("context_root") or workspace)
    project_root = Path(paths.get("project_root") or workspace)

    if space_name:
        name = space_name
    elif context_root != project_root:
        name = context_root.name or "workspace"
    else:
        name = workspace.name or context_root.name or "workspace"

    if branch and branch != name:
        return f"{branch}@{name}"
    return branch or name


def join_values(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip()]
    return "; ".join(cleaned)


def build_research_entry(
    work_context: str,
    topic: str,
    conclusion: str,
    valid: str,
    merged: str,
    evidence: list[str],
    key_paths: list[str],
    next_step: str,
    tags: list[str],
) -> str:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"### {timestamp} [context: {work_context}]",
        f"- 研究主题：{topic.strip()}",
        f"- 当前结论：{conclusion.strip()}",
        f"- 是否有效：{valid}",
        f"- 是否并入主线：{merged}",
        f"- 关键证据：{join_values(evidence)}",
        f"- 关键文件与路径：{join_values(key_paths)}",
        f"- 下一步：{next_step.strip()}",
        f"- 关键词 / 标签：{join_values(tags)}",
    ]
    return "\n".join(lines) + "\n"


def ensure_initialized(workspace: str, scope: str) -> int:
    init_script = Path(__file__).resolve().parent / "init_session_memory.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(init_script),
            "--workspace",
            str(workspace),
            "--scope",
            str(scope),
        ],
        check=False,
    )
    return completed.returncode


def append_entry(path: Path, entry: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    separator = "\n" if existing.strip() else ""
    path.write_text(existing + separator + entry, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append a research checkpoint into research.md without touching current.md."
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Starting directory used to resolve the target location.",
    )
    parser.add_argument(
        "--scope",
        choices=("auto", "workspace", "global"),
        default="auto",
        help="auto=shared project memory, optionally routed by config.toml; workspace=current path only; global=${CODEX_HOME:-$HOME/.codex}/session-memory/global",
    )
    parser.add_argument(
        "--init-if-missing",
        action="store_true",
        help="Initialize current/history/research templates if missing.",
    )
    parser.add_argument(
        "--stage",
        choices=("prepare", "commit"),
        default="prepare",
        help="prepare=ensure research.md exists; commit=append one research entry and register activity.",
    )
    parser.add_argument(
        "--work-context",
        help="Explicit work context such as fork-1, main-local, feature-auth, or another local research copy.",
    )
    parser.add_argument("--topic", help="Research topic for this checkpoint.")
    parser.add_argument("--conclusion", help="Current conclusion for this checkpoint.")
    parser.add_argument(
        "--valid",
        choices=("yes", "no", "partial", "unknown"),
        default="unknown",
        help="Whether this research path is currently considered valid.",
    )
    parser.add_argument(
        "--merged",
        choices=("yes", "no"),
        default="no",
        help="Whether this research result has been merged into the main line.",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Key evidence. May be passed multiple times.",
    )
    parser.add_argument(
        "--key-path",
        action="append",
        default=[],
        help="Relevant file path, directory, or document. May be passed multiple times.",
    )
    parser.add_argument("--next-step", default="", help="What to do next for this research path.")
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Search tag for this research checkpoint. May be passed multiple times.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    paths = resolve_memory_paths(workspace, args.scope)
    research_path = paths["research"]

    for line in iter_resolution_summary(paths):
        print(line)
    print(f"stage={args.stage}")
    print(f"research={research_path}")

    if args.init_if_missing and not research_path.exists():
        init_code = ensure_initialized(str(args.workspace), str(args.scope))
        if init_code != 0:
            return init_code

    if not research_path.exists():
        print("status=missing")
        print("hint=run init_session_memory.py first or retry with --init-if-missing")
        return 1

    work_context = (args.work_context or detect_work_context(workspace, paths)).strip()
    print(f"work_context={work_context}")

    if args.stage == "prepare":
        print("status=ready")
        print("next_action=provide topic/conclusion and rerun with --stage commit")
        return 0

    if not (args.topic or "").strip():
        print("status=invalid")
        print("reason=--topic is required for --stage commit")
        return 1
    if not (args.conclusion or "").strip():
        print("status=invalid")
        print("reason=--conclusion is required for --stage commit")
        return 1

    entry = build_research_entry(
        work_context=work_context,
        topic=args.topic,
        conclusion=args.conclusion,
        valid=args.valid,
        merged=args.merged,
        evidence=args.evidence,
        key_paths=args.key_path,
        next_step=args.next_step,
        tags=args.tag,
    )
    append_entry(research_path, entry)

    preflight = run_preflight(paths, action="research-save", mark_active=True)
    print(f"preflight_sleep_status={preflight['sleep_check']['status']}")
    print(f"topic={args.topic.strip()}")
    print(f"valid={args.valid}")
    print(f"merged={args.merged}")
    print("status=saved")
    print("next_action=research checkpoint appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
