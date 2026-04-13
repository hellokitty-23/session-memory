#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
GLOBAL_SESSION_MEMORY_DIR = CODEX_HOME / "session-memory"
REGISTRY_PATH = GLOBAL_SESSION_MEMORY_DIR / "registry.json"
STATE_PATH = GLOBAL_SESSION_MEMORY_DIR / "state.json"
SLEEP_LOCK_PATH = GLOBAL_SESSION_MEMORY_DIR / "sleep.lock"
DREAMS_DIR = GLOBAL_SESSION_MEMORY_DIR / "dreams"
LOGS_DIR = GLOBAL_SESSION_MEMORY_DIR / "logs"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_if_missing(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(content, encoding="utf-8")


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_target_dir(base: Path, scope: str) -> tuple[Path, str]:
    if scope == "global":
        return GLOBAL_SESSION_MEMORY_DIR / "global", "global"

    if scope == "workspace":
        return base / ".codex" / "session-memory", "workspace"

    git_root = find_git_root(base)
    if git_root is not None:
        return git_root / ".codex" / "session-memory", "git-root"

    return base / ".codex" / "session-memory", "workspace"


def resolve_memory_paths(base: Path, scope: str) -> dict[str, Path | str]:
    target_dir, resolved_scope = resolve_target_dir(base, scope)
    return {
        "workspace": base,
        "scope": resolved_scope,
        "target_dir": target_dir,
        "current": target_dir / "current.md",
        "history": target_dir / "history.md",
        "dream_notes": target_dir / "dream-notes.md",
    }


def ensure_global_layout() -> None:
    GLOBAL_SESSION_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    DREAMS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def load_registry() -> dict[str, Any]:
    ensure_global_layout()
    registry = _read_json(REGISTRY_PATH, {"version": 1, "projects": {}})
    registry.setdefault("version", 1)
    registry.setdefault("projects", {})
    return registry


def save_registry(registry: dict[str, Any]) -> None:
    ensure_global_layout()
    _write_json(REGISTRY_PATH, registry)


def load_state() -> dict[str, Any]:
    ensure_global_layout()
    state = _read_json(STATE_PATH, {"version": 1})
    state.setdefault("version", 1)
    return state


def save_state(state: dict[str, Any]) -> None:
    ensure_global_layout()
    _write_json(STATE_PATH, state)


def project_key(paths: dict[str, Path | str]) -> str:
    return str(paths["target_dir"])


def upsert_project_registry(
    paths: dict[str, Path | str],
    action: str,
    active_at: str | None = None,
) -> dict[str, Any]:
    registry = load_registry()
    key = project_key(paths)
    now = active_at or iso_now()
    projects = registry["projects"]
    entry = projects.get(key, {})
    entry.update(
        {
            "workspace": str(paths["workspace"]),
            "scope": str(paths["scope"]),
            "target_dir": str(paths["target_dir"]),
            "current_path": str(paths["current"]),
            "history_path": str(paths["history"]),
            "dream_notes_path": str(paths["dream_notes"]),
            "last_action": action,
            "last_seen_at": now,
            "last_active_at": now,
        }
    )
    projects[key] = entry
    save_registry(registry)
    return entry


def update_project_registry(
    target_dir: str,
    **updates: Any,
) -> dict[str, Any] | None:
    registry = load_registry()
    entry = registry.get("projects", {}).get(target_dir)
    if entry is None:
        return None
    entry.update(updates)
    registry["projects"][target_dir] = entry
    save_registry(registry)
    return entry


def get_project_entry(paths: dict[str, Path | str]) -> dict[str, Any] | None:
    registry = load_registry()
    return registry.get("projects", {}).get(project_key(paths))


def record_dream_consumed(paths: dict[str, Path | str], consumed_at: str) -> None:
    update_project_registry(project_key(paths), last_dream_consumed_at=consumed_at)


def due_for_dream(entry: dict[str, Any]) -> bool:
    last_active = parse_iso(entry.get("last_active_at"))
    last_dream = parse_iso(entry.get("last_dream_at"))
    if last_active is None:
        return False
    if last_dream is None:
        return True
    return last_active > last_dream


def iter_due_projects() -> list[dict[str, Any]]:
    registry = load_registry()
    due_entries: list[dict[str, Any]] = []
    for entry in registry.get("projects", {}).values():
        current_path = Path(entry["current_path"])
        history_path = Path(entry["history_path"])
        if not current_path.exists() and not history_path.exists():
            continue
        if due_for_dream(entry):
            due_entries.append(entry)
    return due_entries


def _process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_sleep_lock() -> dict[str, Any] | None:
    if not SLEEP_LOCK_PATH.exists():
        return None
    return _read_json(SLEEP_LOCK_PATH, {})


def release_sleep_lock() -> None:
    if SLEEP_LOCK_PATH.exists():
        SLEEP_LOCK_PATH.unlink()


def lock_is_active(grace_minutes: int = 10) -> bool:
    lock = read_sleep_lock()
    if not lock:
        return False

    pid = int(lock.get("pid") or 0)
    if pid > 0 and _process_running(pid):
        return True

    started_at = parse_iso(lock.get("started_at"))
    if pid == 0 and started_at is not None:
        if datetime.now(UTC) - started_at < timedelta(minutes=grace_minutes):
            return True

    release_sleep_lock()
    return False


def acquire_sleep_lock(trigger_action: str, due_count: int) -> bool:
    ensure_global_layout()
    if lock_is_active():
        return False

    payload = {
        "started_at": iso_now(),
        "pid": 0,
        "trigger_action": trigger_action,
        "due_count": due_count,
    }

    try:
        fd = os.open(SLEEP_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except Exception:
        try:
            SLEEP_LOCK_PATH.unlink()
        except FileNotFoundError:
            pass
        raise

    return True


def update_sleep_lock(**updates: Any) -> None:
    lock = read_sleep_lock() or {}
    lock.update(updates)
    _write_json(SLEEP_LOCK_PATH, lock)


def spawn_background_dream(trigger_action: str) -> int:
    ensure_global_layout()
    script_path = Path(__file__).resolve().parent / "dream_session_memory.py"
    log_path = LOGS_DIR / "dream.log"
    log_handle = open(log_path, "a", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(script_path), "--trigger-action", trigger_action],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    update_sleep_lock(pid=process.pid, started_at=iso_now())
    return process.pid


def run_preflight(
    paths: dict[str, Path | str],
    action: str,
    sleep_threshold_hours: float = 5.0,
) -> dict[str, Any]:
    now = iso_now()
    upsert_project_registry(paths, action=action, active_at=now)

    state = load_state()
    last_check = parse_iso(state.get("last_sleep_check_at"))
    threshold = timedelta(hours=sleep_threshold_hours)
    result: dict[str, Any] = {
        "registered": True,
        "project": project_key(paths),
        "sleep_check": {
            "status": "not-run",
            "threshold_hours": sleep_threshold_hours,
        },
    }

    if last_check is not None and datetime.now(UTC) - last_check < threshold:
        result["sleep_check"]["status"] = "threshold-not-met"
        result["sleep_check"]["last_sleep_check_at"] = state.get("last_sleep_check_at")
        return result

    state["last_sleep_check_at"] = now
    save_state(state)

    due_projects = iter_due_projects()
    result["sleep_check"]["due_projects"] = len(due_projects)
    result["sleep_check"]["last_sleep_check_at"] = now

    if not due_projects:
        result["sleep_check"]["status"] = "no-dream-needed"
        return result

    if not acquire_sleep_lock(trigger_action=action, due_count=len(due_projects)):
        result["sleep_check"]["status"] = "already-running"
        return result

    try:
        pid = spawn_background_dream(trigger_action=action)
    except Exception:
        release_sleep_lock()
        raise

    result["sleep_check"]["status"] = "started"
    result["sleep_check"]["pid"] = pid
    return result
