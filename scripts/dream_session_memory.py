#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from archive_session_memory import (
    DEFAULT_DREAM_KEEP_DAYS,
    DEFAULT_HISTORY_KEEP_ENTRIES,
    archive_project_history_after_dream,
    archive_project_research_after_dream,
    move_old_dream_snapshots,
)
from session_memory_common import (
    DREAMS_DIR,
    load_registry,
    load_state,
    parse_iso,
    read_text,
    release_sleep_lock,
    save_registry,
    save_state,
    update_sleep_lock,
)

AGENTS_RULE_MARKER = ".codex/session-memory/dream-notes.md"
AGENTS_RULE_BLOCK = """## Session Memory Dream Notes
- 如果存在 `.codex/session-memory/dream-notes.md`，在恢复或进入项目上下文时一并读取，作为补充上下文。
- `dream-notes.md` 只补充经验、风险、提醒，不覆盖 `current.md` 的优先级。
- `research.md` 是研究层，不是默认主线恢复入口；只有用户明确要求查看研究上下文时才读取。
- `.codex/session-memory/archive/` 属于冷层；除非用户明确要求查看归档，否则默认不要读取。
"""


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "__root__"
    sections[current] = []
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def extract_list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if value:
                items.append(value)
            continue

        match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if match and match.group(1).strip():
            items.append(match.group(1).strip())
    return items


def extract_table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if set(stripped.replace("|", "").replace("-", "").replace(" ", "")) == set():
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if any(parts):
            rows.append(parts)
    return rows[1:] if len(rows) > 1 else []


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def normalize_item(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    prefixes = (
        "当前采用的方案：",
        "为什么现在采用这个方案：",
        "当前约束：",
        "当前目标：",
        "从哪里继续：",
        "需要避免：",
        "需要检查：",
        "下一步先做什么：",
        "触发原因：",
        "分支研究：",
        "发生了什么变化：",
        "研究主题：",
        "研究结果：",
        "当前结论：",
        "是否有效：",
        "是否并入主线：",
        "为什么变：",
        "证据：",
        "关键词 / 标签：",
        "关键文件与路径：",
        "下一步：",
    )
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break
    return normalized


def compact_text(value: str, max_len: int = 120) -> str:
    normalized = normalize_item(value)
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 1].rstrip() + "…"


def limit_items(items: list[str], limit: int, max_len: int = 120) -> list[str]:
    compacted: list[str] = []
    for item in dedupe(items):
        text = compact_text(item, max_len=max_len).strip()
        if not text:
            continue
        compacted.append(text)
        if len(compacted) >= limit:
            break
    return compacted


def parse_history_entries(text: str, limit: int = 4) -> list[str]:
    entries: list[str] = []
    current_title: str | None = None
    bullets: list[str] = []

    def flush() -> None:
        nonlocal current_title, bullets
        normalized_bullets = [normalize_item(item) for item in bullets]
        normalized_bullets = [item for item in normalized_bullets if item]
        if current_title and normalized_bullets:
            entries.append(compact_text(f"{current_title}: {'; '.join(normalized_bullets[:2])}", 140))
        current_title = None
        bullets = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("### "):
            flush()
            current_title = stripped[4:].strip()
        elif stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    flush()
    return entries[-limit:]


def parse_research_entries(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        if not current_lines:
            return

        header = current_lines[0][4:].strip()
        context_match = re.search(r"\[context:\s*([^\]]+)\]", header)
        payload = {
            "title": header,
            "work_context": context_match.group(1).strip() if context_match else "",
        }
        for line in current_lines[1:]:
            match = re.match(r"^- ([^:：]+)[：:]\s*(.*)$", line.strip())
            if not match:
                continue
            payload[match.group(1).strip()] = match.group(2).strip()
        entries.append(payload)
        current_lines = []

    for line in text.splitlines():
        if line.startswith("### "):
            flush()
            current_lines = [line]
            continue
        if current_lines:
            current_lines.append(line)

    flush()
    return entries


def format_research_conclusion(row: list[str]) -> str | None:
    topic = normalize_item(row[0]) if len(row) > 0 else ""
    conclusion = normalize_item(row[3]) if len(row) > 3 else ""
    result = normalize_item(row[2]) if len(row) > 2 else ""

    if conclusion and topic:
        return compact_text(f"{topic}: {conclusion}", 120)
    if conclusion:
        return compact_text(conclusion, 120)
    if result and topic:
        return compact_text(f"{topic}: {result}", 120)
    if result:
        return compact_text(result, 120)
    return None


def format_branch_research_row(row: list[str]) -> tuple[str | None, str | None, str | None]:
    work_context = normalize_item(row[1]) if len(row) > 1 else ""
    branch = normalize_item(row[2]) if len(row) > 2 else ""
    topic = normalize_item(row[3]) if len(row) > 3 else ""
    conclusion = normalize_item(row[4]) if len(row) > 4 else ""
    valid = normalize_item(row[5]).lower() if len(row) > 5 else ""
    merged = normalize_item(row[6]).lower() if len(row) > 6 else ""
    next_step = normalize_item(row[7]) if len(row) > 7 else ""

    label_parts = [part for part in (work_context, branch, topic) if part]
    label = " / ".join(label_parts)
    if conclusion:
        heuristic = compact_text(f"{label}: {conclusion}" if label else conclusion, 120)
    else:
        heuristic = compact_text(label, 120) if label else None

    warning = None
    if merged == "no" and next_step:
        warning = compact_text(f"{label}: {next_step}" if label else next_step, 120)
    elif valid in {"no", "partial", "unknown"} and conclusion:
        warning = compact_text(f"{label}: {conclusion}" if label else conclusion, 120)

    mistake = None
    if valid == "no" and conclusion:
        base = f"{label}: {conclusion}" if label else conclusion
        mistake = format_mistake_item(base)

    return heuristic, warning, mistake


def format_research_log_entry(entry: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    work_context = normalize_item(entry.get("work_context", ""))
    topic = normalize_item(entry.get("研究主题", ""))
    conclusion = normalize_item(entry.get("当前结论", ""))
    valid = normalize_item(entry.get("是否有效", "")).lower()
    merged = normalize_item(entry.get("是否并入主线", "")).lower()
    next_step = normalize_item(entry.get("下一步", ""))

    label = " / ".join(part for part in (work_context, topic) if part)
    if not label:
        label = normalize_item(entry.get("title", ""))

    heuristic = None
    if conclusion and (valid in {"yes", "partial"} or merged == "yes"):
        heuristic = compact_text(f"{label}: {conclusion}" if label else conclusion, 120)

    warning = None
    if merged == "no" and next_step:
        warning = compact_text(f"{label}: {next_step}" if label else next_step, 120)
    elif valid in {"partial", "unknown"} and conclusion:
        warning = compact_text(f"{label}: {conclusion}" if label else conclusion, 120)

    mistake = None
    if valid == "no" and conclusion:
        base = f"{label}: {conclusion}" if label else conclusion
        mistake = format_mistake_item(base)

    return heuristic, warning, mistake


def format_mistake_item(value: str) -> str:
    text = compact_text(value, 110)
    if not text:
        return text
    if "->" in text or "=>" in text or "避免" in text or "改为" in text:
        return text
    return compact_text(f"{text} -> 下次先验证前提，再继续推进", 120)


def build_project_dream(entry: dict[str, str], generated_at: str) -> str | None:
    current_path = Path(entry["current_path"])
    history_path = Path(entry["history_path"])
    research_path = Path(entry.get("research_path") or Path(entry["target_dir"]) / "research.md")
    current_text = read_text(current_path) if current_path.exists() else ""
    history_text = read_text(history_path) if history_path.exists() else ""
    research_text = read_text(research_path) if research_path.exists() else ""

    if not current_text and not history_text and not research_text:
        return None

    current_sections = split_sections(current_text) if current_text else {}

    effective = extract_list_items(current_sections.get("有效做法", []))
    ineffective = extract_list_items(current_sections.get("无效或放弃的做法", []))
    unresolved = extract_list_items(current_sections.get("未决问题", []))
    next_steps = extract_list_items(current_sections.get("下一步", []))
    prompts = extract_list_items(current_sections.get("恢复提示", []))
    current_approach = extract_list_items(current_sections.get("当前思路", []))

    research_rows = extract_table_rows(current_sections.get("研究记录", []))
    research_conclusions = [
        item
        for item in (format_research_conclusion(row) for row in research_rows if any(cell for cell in row))
        if item
    ]
    branch_rows = extract_table_rows(current_sections.get("分支研究", []))
    branch_insights = [format_branch_research_row(row) for row in branch_rows if any(cell for cell in row)]
    branch_heuristics = [item[0] for item in branch_insights if item[0]]
    branch_warnings = [item[1] for item in branch_insights if item[1]]
    branch_mistakes = [item[2] for item in branch_insights if item[2]]
    research_entries = parse_research_entries(research_text)
    research_insights = [format_research_log_entry(item) for item in research_entries]
    research_heuristics = [item[0] for item in research_insights if item[0]]
    research_warnings = [item[1] for item in research_insights if item[1]]
    research_mistakes = [item[2] for item in research_insights if item[2]]
    history_signals = parse_history_entries(history_text)

    correct_trajectory = limit_items(effective + current_approach, limit=3, max_len=110)
    mistakes = [format_mistake_item(item) for item in limit_items(ineffective, limit=3, max_len=110)] + branch_mistakes + research_mistakes
    heuristics = limit_items(
        research_heuristics + research_conclusions + branch_heuristics + prompts,
        limit=3,
        max_len=120,
    )
    warnings = limit_items(
        unresolved + next_steps + research_warnings + branch_warnings + history_signals,
        limit=3,
        max_len=120,
    )
    mistakes = limit_items(mistakes, limit=3, max_len=120)

    sections: list[tuple[str, list[str]]] = []
    if correct_trajectory:
        sections.append(("正确轨迹", correct_trajectory))
    if mistakes:
        sections.append(("错误与错因", mistakes))
    if heuristics:
        sections.append(("判断准则", heuristics))
    if warnings:
        sections.append(("预警信号", warnings))

    if not sections:
        return None

    lines = [
        "# Dream Notes",
        "",
        f"- Generated At: {generated_at}",
    ]

    for title, items in sections:
        lines.extend(["", f"## {title}"])
        lines.extend(f"- {item}" for item in items)

    return "\n".join(lines) + "\n"


def ensure_agents_rule(entry: dict[str, str]) -> None:
    workspace = Path(entry["workspace"])
    agents_path = workspace / "AGENTS.md"

    if agents_path.exists():
        existing = agents_path.read_text(encoding="utf-8")
        if AGENTS_RULE_MARKER in existing:
            return

        suffix = "\n\n" if existing.rstrip() else ""
        agents_path.write_text(
            existing.rstrip() + f"{suffix}{AGENTS_RULE_BLOCK}",
            encoding="utf-8",
        )
        return

    agents_path.write_text(f"# Agent Notes\n\n{AGENTS_RULE_BLOCK}", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate project dream notes for projects that changed since last dream."
    )
    parser.add_argument(
        "--trigger-action",
        default="manual",
        help="Action that triggered the background dream run.",
    )
    args = parser.parse_args()

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    registry = load_registry()
    projects = registry.get("projects", {})
    processed: list[str] = []
    archive_summaries: list[str] = []

    try:
        update_sleep_lock(trigger_action=args.trigger_action)
        for key, entry in projects.items():
            last_active = parse_iso(entry.get("last_active_at"))
            last_dream = parse_iso(entry.get("last_dream_at"))
            if last_active is None:
                continue
            if last_dream is not None and last_active <= last_dream:
                continue

            content = build_project_dream(entry, generated_at)
            if content is None:
                continue

            dream_notes_path = Path(entry["dream_notes_path"])
            dream_notes_path.parent.mkdir(parents=True, exist_ok=True)
            dream_notes_path.write_text(content, encoding="utf-8")
            ensure_agents_rule(entry)

            snapshot_key = entry.get("target_dir", key)
            snapshot_suffix = hashlib.sha1(snapshot_key.encode("utf-8")).hexdigest()[:8]
            snapshot_name = (
                f"{generated_at.replace(':', '').replace('-', '')}"
                f"-{Path(entry.get('workspace') or entry['target_dir']).name or 'workspace'}"
                f"-{snapshot_suffix}.md"
            )
            (DREAMS_DIR / snapshot_name).write_text(content, encoding="utf-8")

            entry["last_dream_at"] = generated_at
            entry["last_dream_notes_path"] = str(dream_notes_path)
            history_archive_result = archive_project_history_after_dream(
                entry=entry,
                keep_entries=DEFAULT_HISTORY_KEEP_ENTRIES,
                persist_state=False,
            )
            research_archive_result = archive_project_research_after_dream(
                entry=entry,
                persist_state=False,
            )
            archived_at = datetime.now(UTC).replace(microsecond=0).isoformat()
            entry["last_history_archive_at"] = archived_at
            entry["last_research_archive_at"] = archived_at
            entry["last_archive_at"] = archived_at
            archive_summaries.append(
                f"{key}|history_status={history_archive_result.status}|history_archived={history_archive_result.archived_entries}|research_status={research_archive_result.status}|research_archived={research_archive_result.archived_entries}"
            )
            processed.append(key)

        if processed:
            moved_dreams = move_old_dream_snapshots(
                keep_days=DEFAULT_DREAM_KEEP_DAYS,
                dry_run=False,
            )
            save_registry(registry)
            state = load_state()
            state["last_sleep_at"] = generated_at
            state["last_sleep_trigger_action"] = args.trigger_action
            state["last_sleep_archived_dream_snapshots"] = len(moved_dreams)
            save_state(state)
        else:
            moved_dreams = []

        print(f"trigger_action={args.trigger_action}")
        print(f"generated_at={generated_at}")
        print(f"processed_projects={len(processed)}")
        for key in processed:
            print(f"project={key}")
        for item in archive_summaries:
            print(f"archive={item}")
        print(f"archived_dream_snapshots={len(moved_dreams)}")
        return 0
    finally:
        release_sleep_lock()


if __name__ == "__main__":
    raise SystemExit(main())
