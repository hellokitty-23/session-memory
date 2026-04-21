#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from session_memory_common import (
    get_project_entry,
    iter_resolution_summary,
    record_dream_consumed,
    resolve_memory_paths,
    run_preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore current project session memory and optionally consume new dream notes."
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
    args = parser.parse_args()

    paths = resolve_memory_paths(Path(args.workspace).resolve(), args.scope)
    preflight = run_preflight(paths, action="restore")
    current_path = paths["current"]
    history_path = paths["history"]
    dream_notes_path = paths["dream_notes"]

    for line in iter_resolution_summary(paths):
        print(line)
    print(f"preflight_sleep_status={preflight['sleep_check']['status']}")

    if not current_path.exists() and not history_path.exists():
        print("status=missing")
        print("hint=run init_session_memory.py first")
        return 1

    if current_path.exists():
        print("\n[current.md]")
        print(current_path.read_text(encoding="utf-8").rstrip())

    if history_path.exists():
        print("\n[history.md]")
        print(history_path.read_text(encoding="utf-8").rstrip())

    entry = get_project_entry(paths) or {}
    last_dream_at = entry.get("last_dream_at")
    last_consumed_at = entry.get("last_dream_consumed_at")
    should_consume_dream = (
        dream_notes_path.exists()
        and last_dream_at is not None
        and (last_consumed_at is None or last_dream_at > last_consumed_at)
    )

    print(f"\ninclude_dream={'yes' if should_consume_dream else 'no'}")
    if should_consume_dream:
        print("\n[dream-notes.md]")
        print(dream_notes_path.read_text(encoding="utf-8").rstrip())
        record_dream_consumed(paths, consumed_at=last_dream_at)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
