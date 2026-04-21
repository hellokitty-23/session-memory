#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from session_memory_common import (
    iter_resolution_summary,
    read_text,
    resolve_memory_paths,
    write_if_missing,
)


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
        help="auto=shared project memory, optionally routed by config.toml; workspace=current path only; global=${CODEX_HOME:-$HOME/.codex}/session-memory/global",
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
    paths = resolve_memory_paths(workspace, args.scope)
    target_dir = Path(paths["target_dir"])
    current_path = Path(paths["current"])
    history_path = Path(paths["history"])
    research_path = Path(paths["research"])

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

    for line in iter_resolution_summary(paths):
        print(line)
    print(f"current={current_path}")
    print(f"history={history_path}")
    print(f"research={research_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
