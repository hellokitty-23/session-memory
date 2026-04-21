#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
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
SESSION_MEMORY_FILES = ("current.md", "history.md", "research.md", "dream-notes.md")
CONFIG_TABLE_NAMES = ("spaces", "routes")


@dataclass(frozen=True)
class SpaceRoute:
    name: str
    relative_path: str
    root: Path


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


def session_memory_dir(root: Path) -> Path:
    return root / ".codex" / "session-memory"


def session_memory_config_path(root: Path) -> Path:
    return session_memory_dir(root) / "config.toml"


def has_session_memory_state(root: Path) -> bool:
    target_dir = session_memory_dir(root)
    if not target_dir.exists():
        return False
    return any((target_dir / name).exists() for name in SESSION_MEMORY_FILES)


def find_nearest_config_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if session_memory_config_path(candidate).exists():
            return candidate
    return None


def find_nearest_memory_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if has_session_memory_state(candidate):
            return candidate
    return None


def normalize_route_path(project_root: Path, raw_path: str) -> tuple[str, Path]:
    raw_text = raw_path.strip()
    if not raw_text:
        raise SystemExit("Invalid session-memory config: route path cannot be empty.")

    candidate = Path(raw_text)
    if candidate.is_absolute():
        raise SystemExit(
            f"Invalid session-memory config: absolute paths are not allowed: {raw_text}"
        )

    clean_parts = [part for part in candidate.parts if part not in ("", ".")]
    if not clean_parts:
        raise SystemExit(
            f"Invalid session-memory config: route path must point to a subdirectory: {raw_text}"
        )
    if any(part == ".." for part in clean_parts):
        raise SystemExit(
            f"Invalid session-memory config: route path cannot escape project root: {raw_path}"
        )

    relative_path = Path(*clean_parts)
    resolved_root = (project_root / relative_path).resolve()
    if not resolved_root.is_relative_to(project_root):
        raise SystemExit(
            f"Invalid session-memory config: route path must stay inside project root: {raw_path}"
        )

    return relative_path.as_posix(), resolved_root


def load_space_routes(project_root: Path) -> tuple[Path | None, list[SpaceRoute]]:
    config_path = session_memory_config_path(project_root)
    if not config_path.exists():
        return None, []

    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"Invalid session-memory config {config_path}: {exc}") from exc

    route_entries: list[tuple[str, str]] = []
    for table_name in CONFIG_TABLE_NAMES:
        table = payload.get(table_name)
        if table is None:
            continue
        if not isinstance(table, dict):
            raise SystemExit(
                f"Invalid session-memory config {config_path}: [{table_name}] must be a table."
            )
        for name, route_path in table.items():
            if not isinstance(route_path, str):
                raise SystemExit(
                    f"Invalid session-memory config {config_path}: route {name!r} must map to a string path."
                )
            route_entries.append((str(name).strip(), route_path))

    if not route_entries:
        for name, route_path in payload.items():
            if name in CONFIG_TABLE_NAMES or not isinstance(route_path, str):
                continue
            route_entries.append((str(name).strip(), route_path))

    routes: list[SpaceRoute] = []
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    for name, route_path in route_entries:
        if not name:
            raise SystemExit(
                f"Invalid session-memory config {config_path}: route name cannot be empty."
            )
        if name in seen_names:
            raise SystemExit(
                f"Invalid session-memory config {config_path}: duplicated route name {name!r}."
            )
        seen_names.add(name)
        relative_path, route_root = normalize_route_path(project_root, route_path)
        if relative_path in seen_paths:
            raise SystemExit(
                f"Invalid session-memory config {config_path}: duplicated route path {relative_path!r}."
            )
        seen_paths.add(relative_path)
        routes.append(
            SpaceRoute(name=name, relative_path=relative_path, root=route_root)
        )

    routes.sort(key=lambda item: len(item.root.parts), reverse=True)
    return config_path, routes


def match_space_route(base: Path, routes: list[SpaceRoute]) -> SpaceRoute | None:
    current = base.resolve()
    for route in routes:
        if current == route.root or current.is_relative_to(route.root):
            return route
    return None


def resolve_project_root(base: Path) -> tuple[Path, str]:
    git_root = find_git_root(base)
    if git_root is not None:
        return git_root, "git-root"

    config_root = find_nearest_config_root(base)
    if config_root is not None:
        return config_root, "project-root"

    memory_root = find_nearest_memory_root(base)
    if memory_root is not None:
        return memory_root, "project-root"

    return base.resolve(), "workspace"


def resolve_target_dir(base: Path, scope: str) -> tuple[Path, str]:
    paths = resolve_memory_paths(base, scope)
    return Path(paths["target_dir"]), str(paths["scope"])


def resolve_memory_paths(base: Path, scope: str) -> dict[str, Any]:
    workspace = base.resolve()
    if scope == "global":
        target_dir = GLOBAL_SESSION_MEMORY_DIR / "global"
        return {
            "workspace": workspace,
            "project_root": target_dir,
            "context_root": target_dir,
            "scope": "global",
            "root_scope": "global",
            "target_dir": target_dir,
            "current": target_dir / "current.md",
            "history": target_dir / "history.md",
            "research": target_dir / "research.md",
            "dream_notes": target_dir / "dream-notes.md",
            "config_path": "",
            "space_name": "",
            "space_path": "",
        }

    if scope == "workspace":
        project_root = workspace
        context_root = workspace
        target_dir = session_memory_dir(workspace)
        resolved_scope = "workspace"
        root_scope = "workspace"
        config_path = ""
        space_name = ""
        space_path = ""
    else:
        project_root, root_scope = resolve_project_root(workspace)
        config_candidate, routes = load_space_routes(project_root)
        matched_route = match_space_route(workspace, routes) if routes else None
        context_root = matched_route.root if matched_route else project_root
        target_dir = session_memory_dir(context_root)
        resolved_scope = "configured-space" if matched_route else root_scope
        config_path = str(config_candidate) if config_candidate else ""
        space_name = matched_route.name if matched_route else ""
        space_path = matched_route.relative_path if matched_route else ""

    return {
        "workspace": workspace,
        "project_root": project_root,
        "context_root": context_root,
        "scope": resolved_scope,
        "root_scope": root_scope,
        "target_dir": target_dir,
        "current": target_dir / "current.md",
        "history": target_dir / "history.md",
        "research": target_dir / "research.md",
        "dream_notes": target_dir / "dream-notes.md",
        "config_path": config_path,
        "space_name": space_name,
        "space_path": space_path,
    }


def iter_resolution_summary(paths: dict[str, Any]) -> list[str]:
    lines = [
        f"workspace={paths['workspace']}",
        f"project_root={paths['project_root']}",
        f"context_root={paths['context_root']}",
        f"scope={paths['scope']}",
        f"target_dir={paths['target_dir']}",
    ]
    if paths.get("config_path"):
        lines.append(f"config_path={paths['config_path']}")
    if paths.get("space_name"):
        lines.append(f"space_name={paths['space_name']}")
    if paths.get("space_path"):
        lines.append(f"space_path={paths['space_path']}")
    return lines


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


def project_key(paths: dict[str, Any]) -> str:
    return str(paths["target_dir"])


def upsert_project_registry(
    paths: dict[str, Any],
    action: str,
    active_at: str | None = None,
    mark_active: bool = False,
) -> dict[str, Any]:
    registry = load_registry()
    key = project_key(paths)
    now = active_at or iso_now()
    projects = registry["projects"]
    entry = projects.get(key, {})
    entry.update(
        {
            "workspace": str(paths["workspace"]),
            "project_root": str(paths["project_root"]),
            "context_root": str(paths["context_root"]),
            "scope": str(paths["scope"]),
            "root_scope": str(paths.get("root_scope") or paths["scope"]),
            "target_dir": str(paths["target_dir"]),
            "current_path": str(paths["current"]),
            "history_path": str(paths["history"]),
            "research_path": str(paths["research"]),
            "dream_notes_path": str(paths["dream_notes"]),
            "config_path": str(paths.get("config_path") or ""),
            "space_name": str(paths.get("space_name") or ""),
            "space_path": str(paths.get("space_path") or ""),
            "last_action": action,
            "last_seen_at": now,
        }
    )
    if mark_active or not entry.get("last_active_at"):
        entry["last_active_at"] = now
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


def get_project_entry(paths: dict[str, Any]) -> dict[str, Any] | None:
    registry = load_registry()
    return registry.get("projects", {}).get(project_key(paths))


def record_dream_consumed(paths: dict[str, Any], consumed_at: str) -> None:
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
        research_path = Path(
            entry.get("research_path") or Path(entry["target_dir"]) / "research.md"
        )
        if not current_path.exists() and not history_path.exists() and not research_path.exists():
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
    paths: dict[str, Any],
    action: str,
    sleep_threshold_hours: float = 5.0,
    mark_active: bool = False,
) -> dict[str, Any]:
    now = iso_now()
    upsert_project_registry(paths, action=action, active_at=now, mark_active=mark_active)

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
