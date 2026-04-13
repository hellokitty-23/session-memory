#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from session_memory_common import resolve_memory_paths, run_preflight


def iter_matches(path: Path, query: str, limit: int) -> list[tuple[int, str]]:
    if not path.exists():
        return []

    query_lower = query.lower()
    matches: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if query_lower in line.lower():
            matches.append((lineno, line.strip()))
        if len(matches) >= limit:
            break
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search current and history session memory files."
    )
    parser.add_argument("--query", required=True, help="Keyword or phrase to search.")
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
        "--limit",
        type=int,
        default=8,
        help="Maximum number of matched lines returned per file.",
    )
    args = parser.parse_args()

    paths = resolve_memory_paths(Path(args.workspace).resolve(), args.scope)
    preflight = run_preflight(paths, action="search")
    current_path = paths["current"]
    history_path = paths["history"]
    dream_notes_path = paths["dream_notes"]

    current_matches = iter_matches(current_path, args.query, args.limit)
    history_matches = iter_matches(history_path, args.query, args.limit)
    dream_matches = iter_matches(dream_notes_path, args.query, args.limit)

    print(f"workspace={paths['workspace']}")
    print(f"scope={paths['scope']}")
    print(f"target_dir={paths['target_dir']}")
    print(f"query={args.query}")
    print(f"preflight_sleep_status={preflight['sleep_check']['status']}")

    if not current_path.exists() and not history_path.exists() and not dream_notes_path.exists():
        print("status=missing")
        print("hint=run init_session_memory.py first")
        return 1

    if not current_matches and not history_matches and not dream_matches:
        print("status=no-match")
        return 0

    if current_matches:
        print("\n[current.md]")
        for lineno, line in current_matches:
            print(f"{lineno}: {line}")

    if history_matches:
        print("\n[history.md]")
        for lineno, line in history_matches:
            print(f"{lineno}: {line}")

    if dream_matches:
        print("\n[dream-notes.md]")
        for lineno, line in dream_matches:
            print(f"{lineno}: {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
