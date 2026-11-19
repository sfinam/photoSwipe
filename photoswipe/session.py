from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import Config, ConfigStore, Source, now_iso
from .i18n import tr
from .models import PhotoGroup, natural_key
from .paths import ensure_dirs, sessions_dir
from .scanner import ProgressFn, scan_source

VERDICTS = ("favorite", "trash", "maybe", "round2")
MOVE_VERDICTS = ("favorite", "trash", "maybe")


class SessionError(RuntimeError):
    pass


def _state_path(source_id: str) -> Path:
    return sessions_dir() / f"{source_id}.json"


def _empty_stats() -> dict[str, int]:
    return {"favorite": 0, "trash": 0, "maybe": 0}


@dataclass
class UndoResult:
    restored: list[PhotoGroup]
    session: "SortSession"


@dataclass
class DecisionResult:
    decided: list[PhotoGroup]
    destinations: dict[str, str]
    session: "SortSession"


def _conflict_name(file_name: str, stem: str, number: int) -> str:
    suffix = f" ({number})" if number else ""
    if file_name.casefold().startswith(stem.casefold()):
        return f"{stem}{suffix}{file_name[len(stem) :]}"
    path = Path(file_name)
    return f"{path.stem}{suffix}{path.suffix}"


def _plan_targets(
    group: PhotoGroup,
    destination: Path,
    reserved: set[Path],
) -> dict[str, Path]:
    files = group.files
    number = 0
    while True:
        targets: dict[str, Path] = {}
        collision = False
        for item in files:
            name = _conflict_name(item.name, group.stem, number)
            target = destination / name
            if target.exists() or target in reserved or target in targets.values():
                collision = True
                break
            targets[item.path] = target
        if not collision:
            return targets
        number += 1
        if number > 9999:
            raise SessionError(tr("Could not find a free file name"))


def _move_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise SessionError(tr("File not found: {name}", name=source.name))
    if target.exists():
        raise SessionError(tr("File already exists: {name}", name=target.name))
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.rename(source, target)
        return
    except OSError as error:
        if getattr(error, "errno", None) not in (
            18,
            13,
            1,
        ):  # EXDEV and common cross-device errors
            raise
    shutil.copy2(source, target)
    try:
        source.unlink()
    except OSError:
        try:
            target.unlink()
        except OSError:
            pass
        raise


def _rollback_moves(moves: list[tuple[Path, Path]]) -> None:
    for source, target in reversed(moves):
        try:
            if not target.exists() or source.exists():
                continue
            source.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.rename(target, source)
            except OSError:
                shutil.copy2(target, source)
                target.unlink()
        except OSError:
            pass


def _natural_name(path: Path) -> list:
    return natural_key(path.name)


class SortSession:
    def __init__(
        self,
        manager: "SessionManager",
        source: Source,
        config: Config,
        state: dict,
        groups: list[PhotoGroup],
        meta_cache: dict[str, dict],
        *,
        scanned_files: int = 0,
        scanned_bytes: int = 0,
        sidecars: int = 0,
    ) -> None:
        self.manager = manager
        self.source = source
        self.config = config
        self.state = state
        self.groups = groups
        self.meta_cache = meta_cache
        self.scanned_files = scanned_files
        self.scanned_bytes = scanned_bytes
        self.sidecar_count = sidecars
        self._lock = threading.RLock()
        self._by_key = {group.key: group for group in groups}
        self.deferred_set = {
            key for key in state.get("deferred", []) if key in self._by_key
        }
        self.state["deferred"] = sorted(self.deferred_set)
        self.destinations = {
            verdict: path
            for verdict, path in config.destinations.for_source(source).items()
        }
        self.refresh_queue()

    # ---- view/statistics -------------------------------------------------

    def refresh_queue(self) -> None:
        mode = self.state.get("mode", "first")
        if mode == "second":
            self.queue = [
                group for group in self.groups if group.key in self.deferred_set
            ]
            self.first_round_pending = [
                group for group in self.groups if group.key not in self.deferred_set
            ]
        else:
            self.queue = [
                group for group in self.groups if group.key not in self.deferred_set
            ]
            self.first_round_pending = []
        self.first_round_pending.sort(
            key=lambda g: (g.sort_time, natural_key(g.display_name))
        )
        self.queue.sort(key=lambda g: (g.sort_time, natural_key(g.display_name)))

    @property
    def mode(self) -> str:
        return self.state.get("mode", "first")

    @property
    def round_number(self) -> int:
        return int(self.state.get("round_number", 1))

    @property
    def stats(self) -> dict[str, int]:
        return self.state.setdefault("stats", _empty_stats())

    @property
    def processed(self) -> int:
        return sum(int(self.stats.get(key, 0)) for key in MOVE_VERDICTS)

    @property
    def deferred_count(self) -> int:
        return len(self.deferred_set)

    @property
    def undo_depth(self) -> int:
        return len(self.state.get("journal", []))

    @property
    def total(self) -> int:
        return (
            self.processed
            + self.deferred_count
            + len(self.first_round_pending)
            + (len(self.queue) if self.mode == "first" else 0)
        )

    @property
    def remaining(self) -> int:
        return len(self.queue) + len(self.first_round_pending)

    @property
    def progress(self) -> float:
        total = self.total
        return min(1.0, self.processed / total) if total else 1.0

    @property
    def can_undo(self) -> bool:
        return bool(self.state.get("journal"))

    @property
    def complete(self) -> bool:
        return not self.queue and not self.deferred_set and not self.first_round_pending

    def destination_for(self, verdict: str) -> Path:
        if verdict == "round2":
            raise SessionError(tr("Files are not moved in the second round"))
        try:
            return self.destinations[verdict]
        except KeyError as error:
            raise SessionError(tr("Unknown decision")) from error

    # ---- persistence -----------------------------------------------------

    def save(self) -> None:
        self.state["source_id"] = self.source.id
        self.state["source_path"] = self.source.path
        self.state["updated_at"] = now_iso()
        self.state["deferred"] = sorted(self.deferred_set)
        self.state["last_remaining"] = len(self.queue) + len(self.first_round_pending)
        self.state["meta_cache"] = self.meta_cache
        undo_limit = int(getattr(self.config.behavior, "undo_limit", 120))
        self.state["journal"] = self.state.get("journal", [])[-max(1, undo_limit) :]
        self.manager.write_state(self.state)

    # ---- decisions -------------------------------------------------------

    def decide(self, groups: list[PhotoGroup], verdicts: list[str]) -> DecisionResult:
        with self._lock:
            if not groups or len(groups) != len(verdicts):
                raise SessionError(tr("Invalid decision set"))
            ids = [group.id for group in groups]
            if len(set(ids)) != len(ids):
                raise SessionError(tr("The same photo was selected twice"))
            active_ids = {group.id for group in self.groups}
            for group in groups:
                if group.id not in active_ids:
                    raise SessionError(tr("This photo has already been processed"))
                if group.key in self.deferred_set and self.mode != "second":
                    # Deferred groups should not be in the first-round queue,
                    # but keep the check tolerant for recovered sessions.
                    pass
                for variant in group.files:
                    if not Path(variant.path).is_file():
                        raise SessionError(
                            tr("File not found: {name}", name=variant.name)
                        )
            for verdict in verdicts:
                if verdict not in VERDICTS:
                    raise SessionError(tr("Unknown decision"))
                if self.mode == "second" and verdict == "round2":
                    raise SessionError(
                        tr(
                            "The second round is already in progress — choose Favorite, Trash or Maybe"
                        )
                    )

            journal_entries: list[dict] = []
            moves: list[tuple[Path, Path]] = []
            stats_delta = _empty_stats()
            reserved: set[Path] = set()
            try:
                for group, verdict in zip(groups, verdicts):
                    was_deferred = group.key in self.deferred_set
                    journal_entries.append(
                        {
                            "group": group.to_dict(),
                            "verdict": verdict,
                            "was_deferred": was_deferred,
                        }
                    )
                    if verdict == "round2":
                        self.deferred_set.add(group.key)
                        continue
                    destination = self.destination_for(verdict)
                    destination.mkdir(parents=True, exist_ok=True)
                    targets = _plan_targets(group, destination, reserved)
                    for source_name, target in targets.items():
                        _move_file(Path(source_name), target)
                        moves.append((Path(source_name), target))
                        reserved.add(target)
                    stats_delta[verdict] += 1
            except Exception as error:
                _rollback_moves(moves)
                raise SessionError(str(error)) from error

            for group, verdict in zip(groups, verdicts):
                if verdict == "round2":
                    continue
                self.deferred_set.discard(group.key)
                self.stats[verdict] = int(self.stats.get(verdict, 0)) + 1

            decided_ids = {
                group.id
                for group, verdict in zip(groups, verdicts)
                if verdict != "round2"
            }
            entry = {
                "id": uuid.uuid4().hex,
                "at": now_iso(),
                "mode": self.mode,
                "round": self.round_number,
                "entries": journal_entries,
                "moves": [
                    {"from": str(source), "to": str(target)} for source, target in moves
                ],
                "stats_delta": stats_delta,
            }
            self.state.setdefault("journal", []).append(entry)
            self.groups = [
                group for group in self.groups if group.id not in decided_ids
            ]
            self._by_key = {group.key: group for group in self.groups}
            self.refresh_queue()
            self.save()
            destinations = {
                verdict: str(self.destinations[verdict])
                for verdict in MOVE_VERDICTS
                if any(v == verdict for v in verdicts)
            }
            return DecisionResult(
                decided=groups, destinations=destinations, session=self
            )

    def undo(self) -> UndoResult:
        with self._lock:
            journal = self.state.get("journal", [])
            if not journal:
                raise SessionError(tr("Nothing to undo"))
            entry = journal[-1]
            moves = entry.get("moves", [])
            # Verify every move can be reversed before touching files.
            for move in reversed(moves):
                original = Path(move["from"])
                current = Path(move["to"])
                if not current.is_file():
                    raise SessionError(
                        tr(
                            "Could not undo: file {name} is no longer there",
                            name=current.name,
                        )
                    )
                if original.exists():
                    raise SessionError(
                        tr(
                            "Could not undo: {name} already exists at the original location",
                            name=original.name,
                        )
                    )
            reversed_moves: list[tuple[Path, Path]] = []
            try:
                for move in reversed(moves):
                    original = Path(move["from"])
                    current = Path(move["to"])
                    _move_file(current, original)
                    reversed_moves.append((current, original))
            except Exception as error:
                _rollback_moves(reversed_moves)
                raise SessionError(
                    tr("Could not undo: {error}", error=error)
                ) from error

            for item in entry.get("entries", []):
                verdict = item["verdict"]
                was_deferred = bool(item.get("was_deferred"))
                if verdict == "round2":
                    if not was_deferred:
                        self.deferred_set.discard(item["group"]["key"])
                else:
                    self.stats[verdict] = max(0, int(self.stats.get(verdict, 0)) - 1)
                    if was_deferred:
                        self.deferred_set.add(item["group"]["key"])
            self.state["journal"] = journal[:-1]
            restored: list[PhotoGroup] = []
            for item in entry.get("entries", []):
                try:
                    group = PhotoGroup.from_dict(item["group"])
                except (KeyError, ValueError):
                    continue
                restored.append(group)
            existing_ids = {group.id for group in self.groups}
            restored = [group for group in restored if group.id not in existing_ids]
            self.groups.extend(restored)
            self._by_key = {group.key: group for group in self.groups}
            self.refresh_queue()
            # Put restored photos at the front of the current round so the user
            # immediately sees what was undone, preserving the original order.
            restored_keys = {group.key for group in restored}
            self.queue = [
                *restored,
                *[group for group in self.queue if group.key not in restored_keys],
            ]
            self.save()
            return UndoResult(restored=restored, session=self)

    # ---- round transitions ----------------------------------------------

    def start_second_round(self) -> "SortSession":
        if not self.deferred_set:
            raise SessionError(tr("No photos for the second round"))
        self.state["mode"] = "second"
        self.state["round_number"] = max(2, self.round_number + 1)
        self.refresh_queue()
        self.save()
        return self

    def back_to_first_round(self) -> "SortSession":
        self.state["mode"] = "first"
        self.state["round_number"] = 1
        self.refresh_queue()
        self.save()
        return self

    def reset(self) -> "SortSession":
        self.manager.reset_state(self.source)
        return self.manager.open(self.source)


class SessionManager:
    def __init__(self, store: ConfigStore | None = None) -> None:
        ensure_dirs()
        self.store = store or ConfigStore()
        self.config = self.store.load()

    def state_path(self, source: Source | str) -> Path:
        source_id_value = source.id if isinstance(source, Source) else source
        return _state_path(source_id_value)

    def _empty_state(self, source: Source) -> dict:
        return {
            "version": 1,
            "source_id": source.id,
            "source_path": source.path,
            "stats": _empty_stats(),
            "deferred": [],
            "mode": "first",
            "round_number": 1,
            "journal": [],
            "meta_cache": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "last_remaining": 0,
        }

    def load_state(self, source: Source) -> dict:
        path = self.state_path(source)
        state = self._empty_state(source)
        if not path.exists():
            return state
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return state
        if not isinstance(raw, dict):
            return state
        stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
        state.update(
            {
                "version": 1,
                "source_id": source.id,
                "source_path": source.path,
                "stats": {
                    key: max(0, int(stats.get(key, 0) or 0)) for key in MOVE_VERDICTS
                },
                "deferred": [
                    key for key in raw.get("deferred", []) if isinstance(key, str)
                ]
                if isinstance(raw.get("deferred"), list)
                else [],
                "mode": "second" if raw.get("mode") == "second" else "first",
                "round_number": max(1, int(raw.get("round_number") or 1)),
                "journal": raw.get("journal", [])
                if isinstance(raw.get("journal"), list)
                else [],
                "meta_cache": raw.get("meta_cache", {})
                if isinstance(raw.get("meta_cache"), dict)
                else {},
                "created_at": str(raw.get("created_at") or now_iso()),
                "updated_at": str(raw.get("updated_at") or now_iso()),
                "last_remaining": max(0, int(raw.get("last_remaining") or 0)),
            }
        )
        return state

    def write_state(self, state: dict) -> None:
        ensure_dirs()
        path = _state_path(str(state["source_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, ensure_ascii=False, indent=1, default=str)
        fd, tmp = tempfile.mkstemp(prefix="session-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def open(self, source: Source, progress: ProgressFn | None = None) -> SortSession:
        if not source.exists:
            raise SessionError(tr("Source folder not found"))
        state = self.load_state(source)
        result = scan_source(
            source,
            self.config.destinations,
            sort_by=self.config.behavior.sort_by,
            meta_cache=state.get("meta_cache", {}),
            progress=progress,
        )
        present = {group.key: group for group in result.groups}
        deferred = [key for key in state.get("deferred", []) if key in present]
        # Deferred photos that vanished are dropped; they were never moved, so
        # likely the user deleted or moved them outside the app.
        state["deferred"] = deferred
        if state.get("mode") == "second" and not deferred:
            # No deferred photos remain, but there may be new unsorted files.
            if result.groups:
                state["mode"] = "first"
                state["round_number"] = 1
            else:
                state["mode"] = "second"
        session = SortSession(
            self,
            source,
            self.config,
            state,
            result.groups,
            result.meta_cache,
            scanned_files=result.total_files,
            scanned_bytes=result.total_bytes,
            sidecars=result.sidecars,
        )
        session.save()
        return session

    def summary(self, source: Source) -> dict:
        state = self.load_state(source)
        stats = state["stats"]
        processed = sum(int(stats.get(key, 0)) for key in MOVE_VERDICTS)
        deferred = len(state.get("deferred", []))
        last_remaining = int(state.get("last_remaining") or 0)
        total = (
            processed
            + last_remaining
            + (deferred if state.get("mode") == "first" else 0)
        )
        return {
            "stats": stats,
            "processed": processed,
            "deferred": deferred,
            "remaining": last_remaining,
            "total": total,
            "mode": state.get("mode", "first"),
            "round_number": state.get("round_number", 1),
            "updated_at": state.get("updated_at"),
            "has_session": self.state_path(source).exists(),
            "undo_depth": len(state.get("journal", [])),
        }

    def reset_state(self, source: Source) -> None:
        try:
            self.state_path(source).unlink(missing_ok=True)
        except OSError as error:
            raise SessionError(
                tr("Could not reset the session: {error}", error=error)
            ) from error
