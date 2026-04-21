#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from session_memory_common import (
    iter_resolution_summary,
    resolve_memory_paths,
    run_preflight,
)


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
        description="Search hot session memory files, with optional research and archive layers."
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
        help="auto=shared project memory, optionally routed by config.toml; workspace=current path only; global=${CODEX_HOME:-$HOME/.codex}/session-memory/global",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        help="Maximum number of matched lines returned per file.",
    )
    parser.add_argument(
        "--include-research",
        action="store_true",
        help="Also search research.md. Use only when the user explicitly asks for research context.",
    )
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Also search cold archive files. Use only when the user explicitly asks for archived context.",
    )
    args = parser.parse_args()

    paths = resolve_memory_paths(Path(args.workspace).resolve(), args.scope)
    preflight = run_preflight(paths, action="search")
    current_path = paths["current"]
    history_path = paths["history"]
    research_path = paths["research"]
    dream_notes_path = paths["dream_notes"]
    archive_history_path = Path(paths["target_dir"]) / "archive" / "history-archive.md"

    current_matches = iter_matches(current_path, args.query, args.limit)
    history_matches = iter_matches(history_path, args.query, args.limit)
    research_matches = (
        iter_matches(research_path, args.query, args.limit)
        if args.include_research
        else []
    )
    dream_matches = iter_matches(dream_notes_path, args.query, args.limit)
    archive_history_matches = (
        iter_matches(archive_history_path, args.query, args.limit)
        if args.include_archive
        else []
    )

    for line in iter_resolution_summary(paths):
        print(line)
    print(f"query={args.query}")
    print(f"include_research={'yes' if args.include_research else 'no'}")
    print(f"include_archive={'yes' if args.include_archive else 'no'}")
    print(f"preflight_sleep_status={preflight['sleep_check']['status']}")

    if (
        not current_path.exists()
        and not history_path.exists()
        and not dream_notes_path.exists()
        and (not args.include_research or not research_path.exists())
        and (not args.include_archive or not archive_history_path.exists())
    ):
        print("status=missing")
        print("hint=run init_session_memory.py first")
        return 1

    if (
        not current_matches
        and not history_matches
        and not research_matches
        and not dream_matches
        and not archive_history_matches
    ):
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

    if research_matches:
        print("\n[research.md]")
        for lineno, line in research_matches:
            print(f"{lineno}: {line}")

    if dream_matches:
        print("\n[dream-notes.md]")
        for lineno, line in dream_matches:
            print(f"{lineno}: {line}")

    if archive_history_matches:
        print("\n[archive/history-archive.md]")
        for lineno, line in archive_history_matches:
            print(f"{lineno}: {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
