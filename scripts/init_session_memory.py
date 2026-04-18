#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from session_memory_common import read_text, resolve_target_dir, write_if_missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize session memory files with project-aware scoping."
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
        help="auto=git root if available, else workspace; workspace=current path; global=${CODEX_HOME:-$HOME/.codex}/session-memory/global",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing memory files.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    refs_dir = skill_dir / "references"

    workspace = Path(args.workspace).resolve()
    target_dir, resolved_scope = resolve_target_dir(workspace, args.scope)
    current_path = target_dir / "current.md"
    history_path = target_dir / "history.md"
    research_path = target_dir / "research.md"

    target_dir.mkdir(parents=True, exist_ok=True)

    write_if_missing(
        current_path,
        read_text(refs_dir / "current-template.md"),
        force=args.force,
    )
    write_if_missing(
        history_path,
        read_text(refs_dir / "history-template.md"),
        force=args.force,
    )
    write_if_missing(
        research_path,
        read_text(refs_dir / "research-template.md"),
        force=args.force,
    )

    print(f"workspace={workspace}")
    print(f"scope={resolved_scope}")
    print(f"target_dir={target_dir}")
    print(f"current={current_path}")
    print(f"history={history_path}")
    print(f"research={research_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
