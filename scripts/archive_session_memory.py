#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from session_memory_common import (
    DREAMS_DIR,
    GLOBAL_SESSION_MEMORY_DIR,
    get_project_entry,
    parse_iso,
    resolve_memory_paths,
    update_project_registry,
)

HISTORY_ARCHIVE_HEADER = """# 会话记忆历史归档

这是 dream 之后转冷的旧条目。除非用户明确要求查看归档，否则默认不要读取这里。
"""

RESEARCH_ARCHIVE_HEADER = """# 会话记忆研究归档

这是 dream 之后从 `research.md` 转冷的研究条目，只保留已并入主线或已判定无效的旧研究记录。除非用户明确要求查看归档，否则默认不要读取这里。
"""

DEFAULT_HISTORY_KEEP_ENTRIES = 20
DEFAULT_DREAM_KEEP_DAYS = 30


@dataclass
class HistoryArchivePlan:
    source_path: Path
    archive_path: Path
    total_entries: int
    kept_entries: int
    archived_entries: int
    new_history_text: str | None
    new_archive_text: str | None


@dataclass
class ResearchArchivePlan:
    source_path: Path
    archive_path: Path
    total_entries: int
    kept_entries: int
    archived_entries: int
    new_research_text: str | None
    new_archive_text: str | None


@dataclass
class ProjectArchiveResult:
    status: str
    archive_path: Path
    total_entries: int = 0
    kept_entries: int = 0
    archived_entries: int = 0


def parse_document_entries(text: str) -> tuple[str, list[str]]:
    preamble: list[str] = []
    entries: list[str] = []
    current_entry: list[str] = []
    in_entries = False

    for line in text.splitlines():
        if line.startswith("### "):
            if current_entry:
                entries.append("\n".join(current_entry).rstrip())
            current_entry = [line]
            in_entries = True
            continue

        if in_entries:
            current_entry.append(line)
        else:
            preamble.append(line)

    if current_entry:
        entries.append("\n".join(current_entry).rstrip())

    return "\n".join(preamble).rstrip(), entries


def render_document(preamble: str, entries: list[str]) -> str:
    blocks: list[str] = []
    normalized_preamble = preamble.strip()
    if normalized_preamble:
        blocks.append(normalized_preamble)
    blocks.extend(entry.strip() for entry in entries if entry.strip())
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def dedupe_entries(entries: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in entries:
        normalized = entry.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def build_history_archive_plan(
    history_path: Path,
    archive_path: Path,
    keep_entries: int,
) -> HistoryArchivePlan | None:
    if not history_path.exists():
        return None

    history_text = history_path.read_text(encoding="utf-8")
    history_preamble, history_entries = parse_document_entries(history_text)
    total_entries = len(history_entries)
    if total_entries <= keep_entries:
        return HistoryArchivePlan(
            source_path=history_path,
            archive_path=archive_path,
            total_entries=total_entries,
            kept_entries=total_entries,
            archived_entries=0,
            new_history_text=None,
            new_archive_text=None,
        )

    archive_entries = []
    if archive_path.exists():
        archive_text = archive_path.read_text(encoding="utf-8")
        _, archive_entries = parse_document_entries(archive_text)

    archived_entries = history_entries[:-keep_entries] if keep_entries > 0 else history_entries
    kept_entries = history_entries[-keep_entries:] if keep_entries > 0 else []
    merged_archive_entries = dedupe_entries(archive_entries + archived_entries)

    new_history_text = render_document(history_preamble, kept_entries)
    new_archive_text = render_document(HISTORY_ARCHIVE_HEADER, merged_archive_entries)

    return HistoryArchivePlan(
        source_path=history_path,
        archive_path=archive_path,
        total_entries=total_entries,
        kept_entries=len(kept_entries),
        archived_entries=len(archived_entries),
        new_history_text=new_history_text,
        new_archive_text=new_archive_text,
    )


def parse_entry_fields(entry: str) -> dict[str, str]:
    lines = entry.splitlines()
    header = lines[0][4:].strip() if lines else ""
    context_match = re.search(r"\[context:\s*([^\]]+)\]", header)
    fields = {
        "title": header,
        "work_context": context_match.group(1).strip() if context_match else "",
    }

    for line in lines[1:]:
        stripped = line.strip()
        match = re.match(r"^- ([^:：]+)[：:]\s*(.*)$", stripped)
        if not match:
            continue
        fields[match.group(1).strip()] = match.group(2).strip()

    return fields


def should_archive_research_entry(entry: str) -> bool:
    fields = parse_entry_fields(entry)
    valid = fields.get("是否有效", "").strip().lower()
    merged = fields.get("是否并入主线", "").strip().lower()
    return merged == "yes" or valid == "no"


def build_research_archive_plan(
    research_path: Path,
    archive_path: Path,
) -> ResearchArchivePlan | None:
    if not research_path.exists():
        return None

    research_text = research_path.read_text(encoding="utf-8")
    research_preamble, research_entries = parse_document_entries(research_text)
    total_entries = len(research_entries)

    archive_entries = []
    if archive_path.exists():
        archive_text = archive_path.read_text(encoding="utf-8")
        _, archive_entries = parse_document_entries(archive_text)

    archived_entries = [entry for entry in research_entries if should_archive_research_entry(entry)]
    kept_entries = [entry for entry in research_entries if not should_archive_research_entry(entry)]

    if not archived_entries:
        return ResearchArchivePlan(
            source_path=research_path,
            archive_path=archive_path,
            total_entries=total_entries,
            kept_entries=len(kept_entries),
            archived_entries=0,
            new_research_text=None,
            new_archive_text=None,
        )

    merged_archive_entries = dedupe_entries(archive_entries + archived_entries)
    new_research_text = render_document(research_preamble, kept_entries)
    new_archive_text = render_document(RESEARCH_ARCHIVE_HEADER, merged_archive_entries)

    return ResearchArchivePlan(
        source_path=research_path,
        archive_path=archive_path,
        total_entries=total_entries,
        kept_entries=len(kept_entries),
        archived_entries=len(archived_entries),
        new_research_text=new_research_text,
        new_archive_text=new_archive_text,
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    index = 1
    while True:
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def move_old_dream_snapshots(keep_days: int, dry_run: bool) -> list[tuple[Path, Path]]:
    if not DREAMS_DIR.exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(days=keep_days)
    archive_root = GLOBAL_SESSION_MEMORY_DIR / "archive" / "dreams"
    moved: list[tuple[Path, Path]] = []

    for source in sorted(DREAMS_DIR.iterdir()):
        if not source.is_file():
            continue

        modified_at = datetime.fromtimestamp(source.stat().st_mtime, tz=UTC)
        if modified_at >= cutoff:
            continue

        month_bucket = modified_at.strftime("%Y-%m")
        destination = unique_destination(archive_root / month_bucket / source.name)
        moved.append((source, destination))
        if dry_run:
            continue

        ensure_parent(destination)
        source.replace(destination)

    return moved


def apply_history_archive(plan: HistoryArchivePlan, dry_run: bool) -> None:
    if plan.archived_entries == 0 or dry_run:
        return

    ensure_parent(plan.archive_path)
    plan.source_path.write_text(plan.new_history_text or "", encoding="utf-8")
    plan.archive_path.write_text(plan.new_archive_text or "", encoding="utf-8")


def apply_research_archive(plan: ResearchArchivePlan, dry_run: bool) -> None:
    if plan.archived_entries == 0 or dry_run:
        return

    ensure_parent(plan.archive_path)
    plan.source_path.write_text(plan.new_research_text or "", encoding="utf-8")
    plan.archive_path.write_text(plan.new_archive_text or "", encoding="utf-8")


def get_last_archive_at(entry: dict[str, str], field_name: str) -> datetime | None:
    return parse_iso(entry.get(field_name) or entry.get("last_archive_at"))


def archive_project_history_after_dream(
    entry: dict[str, str],
    keep_entries: int = DEFAULT_HISTORY_KEEP_ENTRIES,
    dry_run: bool = False,
    force: bool = False,
    persist_state: bool = True,
) -> ProjectArchiveResult:
    target_dir = Path(entry["target_dir"])
    archive_path = target_dir / "archive" / "history-archive.md"
    history_path = Path(entry["history_path"])
    last_dream_at = parse_iso(entry.get("last_dream_at"))
    last_archive_at = get_last_archive_at(entry, "last_history_archive_at")

    if not force:
        if last_dream_at is None:
            return ProjectArchiveResult(status="waiting-dream", archive_path=archive_path)
        if last_archive_at is not None and last_archive_at >= last_dream_at:
            return ProjectArchiveResult(status="already-archived", archive_path=archive_path)

    plan = build_history_archive_plan(
        history_path=history_path,
        archive_path=archive_path,
        keep_entries=keep_entries,
    )
    if plan is None:
        return ProjectArchiveResult(status="missing-history", archive_path=archive_path)

    apply_history_archive(plan, dry_run=dry_run)
    if persist_state and not dry_run and (force or last_dream_at is not None):
        archived_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        update_project_registry(
            entry["target_dir"],
            last_history_archive_at=archived_at,
            last_archive_at=archived_at,
        )

    return ProjectArchiveResult(
        status="archived" if plan.archived_entries else "no-op",
        archive_path=archive_path,
        total_entries=plan.total_entries,
        kept_entries=plan.kept_entries,
        archived_entries=plan.archived_entries,
    )


def archive_project_research_after_dream(
    entry: dict[str, str],
    dry_run: bool = False,
    force: bool = False,
    persist_state: bool = True,
) -> ProjectArchiveResult:
    target_dir = Path(entry["target_dir"])
    archive_path = target_dir / "archive" / "research-archive.md"
    research_path = Path(entry.get("research_path") or target_dir / "research.md")
    last_dream_at = parse_iso(entry.get("last_dream_at"))
    last_archive_at = get_last_archive_at(entry, "last_research_archive_at")

    if not force:
        if last_dream_at is None:
            return ProjectArchiveResult(status="waiting-dream", archive_path=archive_path)
        if last_archive_at is not None and last_archive_at >= last_dream_at:
            return ProjectArchiveResult(status="already-archived", archive_path=archive_path)

    plan = build_research_archive_plan(
        research_path=research_path,
        archive_path=archive_path,
    )
    if plan is None:
        return ProjectArchiveResult(status="missing-research", archive_path=archive_path)

    apply_research_archive(plan, dry_run=dry_run)
    if persist_state and not dry_run and (force or last_dream_at is not None):
        archived_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        update_project_registry(
            entry["target_dir"],
            last_research_archive_at=archived_at,
            last_archive_at=archived_at,
        )

    return ProjectArchiveResult(
        status="archived" if plan.archived_entries else "no-op",
        archive_path=archive_path,
        total_entries=plan.total_entries,
        kept_entries=plan.kept_entries,
        archived_entries=plan.archived_entries,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive cold session memory data only after a dream pass."
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
        "--history-keep-entries",
        type=int,
        default=DEFAULT_HISTORY_KEEP_ENTRIES,
        help="Keep the newest N history entries in history.md and archive older ones.",
    )
    parser.add_argument(
        "--dream-keep-days",
        type=int,
        default=DEFAULT_DREAM_KEEP_DAYS,
        help="Keep global dream snapshots newer than N days in dreams/ and move older ones under archive/dreams/.",
    )
    parser.add_argument(
        "--skip-history",
        action="store_true",
        help="Do not archive project history entries.",
    )
    parser.add_argument(
        "--skip-research",
        action="store_true",
        help="Do not archive project research entries.",
    )
    parser.add_argument(
        "--skip-dreams",
        action="store_true",
        help="Do not archive global dream snapshots.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the planned archive actions without changing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow manual archive even if no new dream was generated since the last archive.",
    )
    args = parser.parse_args()

    if args.history_keep_entries < 0:
        raise SystemExit("--history-keep-entries must be >= 0")
    if args.dream_keep_days < 0:
        raise SystemExit("--dream-keep-days must be >= 0")

    paths = resolve_memory_paths(Path(args.workspace).resolve(), args.scope)
    entry = get_project_entry(paths)

    history_result: ProjectArchiveResult | None = None
    if not args.skip_history:
        if entry is None:
            history_result = ProjectArchiveResult(
                status="missing-registry",
                archive_path=Path(paths["target_dir"]) / "archive" / "history-archive.md",
            )
        else:
            history_result = archive_project_history_after_dream(
                entry=entry,
                keep_entries=args.history_keep_entries,
                dry_run=args.dry_run,
                force=args.force,
            )

    research_result: ProjectArchiveResult | None = None
    if not args.skip_research:
        if entry is None:
            research_result = ProjectArchiveResult(
                status="missing-registry",
                archive_path=Path(paths["target_dir"]) / "archive" / "research-archive.md",
            )
        else:
            research_result = archive_project_research_after_dream(
                entry=entry,
                dry_run=args.dry_run,
                force=args.force,
            )

    moved_dreams: list[tuple[Path, Path]] = []
    if not args.skip_dreams and (args.force or (entry and parse_iso(entry.get("last_dream_at")) is not None)):
        moved_dreams = move_old_dream_snapshots(
            keep_days=args.dream_keep_days,
            dry_run=args.dry_run,
        )

    print(f"workspace={paths['workspace']}")
    print(f"scope={paths['scope']}")
    print(f"target_dir={paths['target_dir']}")
    print(f"dry_run={'yes' if args.dry_run else 'no'}")
    print(f"force={'yes' if args.force else 'no'}")
    print(f"history_keep_entries={args.history_keep_entries}")
    print(f"dream_keep_days={args.dream_keep_days}")

    if history_result is None:
        print("history_status=skipped")
    else:
        print(f"history_entries_total={history_result.total_entries}")
        print(f"history_entries_kept={history_result.kept_entries}")
        print(f"history_entries_archived={history_result.archived_entries}")
        print(f"history_archive_path={history_result.archive_path}")
        print(f"history_status={history_result.status}")

    if research_result is None:
        print("research_status=skipped")
    else:
        print(f"research_entries_total={research_result.total_entries}")
        print(f"research_entries_kept={research_result.kept_entries}")
        print(f"research_entries_archived={research_result.archived_entries}")
        print(f"research_archive_path={research_result.archive_path}")
        print(f"research_status={research_result.status}")

    print(f"dream_snapshots_archived={len(moved_dreams)}")
    print(f"dream_archive_root={GLOBAL_SESSION_MEMORY_DIR / 'archive' / 'dreams'}")
    if moved_dreams:
        for source, destination in moved_dreams:
            print(f"dream_move={source} -> {destination}")
    print("status=dry-run" if args.dry_run else "status=done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
