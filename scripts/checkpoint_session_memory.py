#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from session_memory_common import (
    iter_resolution_summary,
    resolve_memory_paths,
    run_preflight,
)

SAVE_EVENTS = {
    "goal-changed",
    "approach-changed",
    "research-confirmed",
    "blocker-cleared",
    "next-step-changed",
    "task-completed",
    "session-ending",
}


def minutes_since_mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    delta = datetime.now(timezone.utc) - modified
    return int(delta.total_seconds() // 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decide whether session memory should be updated now."
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
        "--event",
        action="append",
        default=[],
        choices=sorted(SAVE_EVENTS),
        help="Signal that a high-value state transition happened. May be passed multiple times.",
    )
    parser.add_argument(
        "--stale-minutes",
        type=int,
        default=180,
        help="Recommend saving if current.md is older than this threshold.",
    )
    args = parser.parse_args()

    paths = resolve_memory_paths(Path(args.workspace).resolve(), args.scope)
    preflight = run_preflight(paths, action="checkpoint")
    current_path = paths["current"]
    history_path = paths["history"]

    for line in iter_resolution_summary(paths):
        print(line)
    print(f"preflight_sleep_status={preflight['sleep_check']['status']}")

    if not current_path.exists() or not history_path.exists():
        print("decision=INIT_FIRST")
        print("reason=memory files are missing")
        print("next_action=run init_session_memory.py")
        return 1

    current_age = minutes_since_mtime(current_path)
    history_age = minutes_since_mtime(history_path)
    events = sorted(set(args.event))

    print(f"current_age_minutes={current_age}")
    print(f"history_age_minutes={history_age}")
    print(f"events={','.join(events) if events else '-'}")

    reasons: list[str] = []
    if events:
        reasons.append("high-value event detected")
    if current_age is not None and current_age >= args.stale_minutes:
        reasons.append("current.md is stale")

    if reasons:
        print("decision=SAVE_NOW")
        print(f"reason={'; '.join(reasons)}")
        if events:
            print(
                "suggestion=update current.md and append history.md if the change affects direction, conclusions, or next step"
            )
        else:
            print("suggestion=refresh current.md if the project state has moved")
        return 0

    print("decision=SKIP")
    print("reason=no high-value trigger and current.md is fresh")
    print("next_action=continue current task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
