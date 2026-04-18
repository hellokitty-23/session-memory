#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from session_memory_common import resolve_memory_paths, run_preflight


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare session memory save by running preflight and ensuring files exist."
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
        "--init-if-missing",
        action="store_true",
        help="Initialize current/history templates if missing.",
    )
    parser.add_argument(
        "--stage",
        choices=("prepare", "commit"),
        default="prepare",
        help="prepare=ensure files and print paths; commit=register activity after you updated memory files.",
    )
    args = parser.parse_args()

    paths = resolve_memory_paths(Path(args.workspace).resolve(), args.scope)
    current_path = paths["current"]
    history_path = paths["history"]

    print(f"workspace={paths['workspace']}")
    print(f"scope={paths['scope']}")
    print(f"target_dir={paths['target_dir']}")
    print(f"stage={args.stage}")

    if args.init_if_missing and (not current_path.exists() or not history_path.exists()):
        init_script = Path(__file__).resolve().parent / "init_session_memory.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(init_script),
                "--workspace",
                str(args.workspace),
                "--scope",
                str(args.scope),
            ],
            check=False,
        )
        if completed.returncode != 0:
            return completed.returncode

    if args.stage == "commit":
        preflight = run_preflight(paths, action="save", mark_active=True)
        print(f"preflight_sleep_status={preflight['sleep_check']['status']}")

    print(f"current={current_path}")
    print(f"history={history_path}")
    print("status=ready")
    if args.stage == "prepare":
        print("next_action=update current.md and append history.md if needed, then rerun with --stage commit")
    else:
        print("next_action=save committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
