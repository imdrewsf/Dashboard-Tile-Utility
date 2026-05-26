# Copyright 2026 Andrew Peck
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from .tiles import as_int, rect, set_int_like
from .util import die, dlog, vlog

PushSpec = Optional[Tuple[str, int]]
Rect = Tuple[int, int, int, int]
ConflictMap = Dict[int, List[Tuple[int, Rect]]]


def normalize_push_spec(push_spec: PushSpec) -> PushSpec:
    if push_spec is None:
        return None
    mode, buffer = push_spec
    mode = str(mode).strip().lower()
    if mode not in {"rows", "cols", "all"}:
        die(f"Invalid push mode: {mode!r}. Use --push:rows, --push:cols, or --push:all.")
    try:
        buffer_i = int(buffer)
    except Exception:
        die(f"--push:{mode} BUFFER must be an integer, got {buffer!r}.")
    if buffer_i < 0:
        die(f"--push:{mode} BUFFER must be >= 0, got {buffer_i}.")
    return (mode, buffer_i)


def union_rects(rects: Iterable[Rect]) -> Optional[Rect]:
    rect_list = list(rects)
    if not rect_list:
        return None
    return (
        min(r[0] for r in rect_list),
        max(r[1] for r in rect_list),
        min(r[2] for r in rect_list),
        max(r[3] for r in rect_list),
    )


def _push_rows_count(
    original_rects: Dict[int, Rect],
    conflicting_stationary_ids: set[int],
    bounds: Rect,
    buffer: int,
) -> int:
    top, bottom, _left, _right = bounds
    base = (bottom - top + 1) + buffer
    count = base
    target_first_open_row = bottom + buffer + 1
    for tid in conflicting_stationary_ids:
        r = original_rects.get(tid)
        if r is None:
            continue
        r1, r2, _c1, _c2 = r
        if r1 < top <= r2:
            count = max(count, target_first_open_row - r1)
    return count


def _push_cols_count(
    original_rects: Dict[int, Rect],
    conflicting_stationary_ids: set[int],
    bounds: Rect,
    buffer: int,
) -> int:
    _top, _bottom, left, right = bounds
    base = (right - left + 1) + buffer
    count = base
    target_first_open_col = right + buffer + 1
    for tid in conflicting_stationary_ids:
        r = original_rects.get(tid)
        if r is None:
            continue
        _r1, _r2, c1, c2 = r
        if c1 < left <= c2:
            count = max(count, target_first_open_col - c1)
    return count


def apply_push_for_destination(
    stationary_tiles: List[Dict[str, Any]],
    destination_rects: List[Rect],
    conflicts_by_moving_id: ConflictMap,
    push_spec: PushSpec,
    *,
    verbose: bool = False,
    debug: bool = False,
    label: str = "push",
) -> Tuple[int, int]:
    """Shift stationary tiles away from a destination footprint before conflict handling.

    The destination footprint is the union of the move/copy/merge tiles after they
    have been projected to their destination.  Rows are inserted at the footprint's
    top edge and columns are inserted at the footprint's left edge.  The inserted
    size is the footprint size plus BUFFER, which leaves BUFFER empty cells on the
    bottom/right side of the destination footprint.  If an initially conflicting
    stationary tile crosses the insertion edge, the shift is expanded enough to
    move that tile past the bottom/right buffer edge.
    """
    normalized = normalize_push_spec(push_spec)
    if normalized is None or not conflicts_by_moving_id:
        return (0, 0)

    mode, buffer = normalized
    bounds = union_rects(destination_rects)
    if bounds is None:
        return (0, 0)

    top, bottom, left, right = bounds
    original_rects: Dict[int, Rect] = {}
    for t in stationary_tiles:
        try:
            original_rects[as_int(t, "id")] = rect(t)
        except Exception:
            continue

    conflicting_stationary_ids: set[int] = set()
    for entries in conflicts_by_moving_id.values():
        for sid, _orect in entries:
            conflicting_stationary_ids.add(int(sid))

    row_count = _push_rows_count(original_rects, conflicting_stationary_ids, bounds, buffer) if mode in {"rows", "all"} else 0
    col_count = _push_cols_count(original_rects, conflicting_stationary_ids, bounds, buffer) if mode in {"cols", "all"} else 0

    rows_shifted = 0
    cols_shifted = 0

    if row_count:
        for t in stationary_tiles:
            tid = as_int(t, "id")
            r = original_rects.get(tid)
            if r is None:
                continue
            r1, r2, _c1, _c2 = r
            if r1 >= top or (r1 < top <= r2):
                old_row = as_int(t, "row")
                new_row = old_row + row_count
                set_int_like(t, "row", new_row)
                rows_shifted += 1
                dlog(debug, f"[{label}] --push:rows id={tid}: row {old_row} -> {new_row}")

    if col_count:
        for t in stationary_tiles:
            tid = as_int(t, "id")
            r = original_rects.get(tid)
            if r is None:
                continue
            _r1, _r2, c1, c2 = r
            if c1 >= left or (c1 < left <= c2):
                old_col = as_int(t, "col")
                new_col = old_col + col_count
                set_int_like(t, "col", new_col)
                cols_shifted += 1
                dlog(debug, f"[{label}] --push:cols id={tid}: col {old_col} -> {new_col}")

    if row_count or col_count:
        bounds_s = f"r{top}..{bottom},c{left}..{right}"
        parts: List[str] = []
        if row_count:
            parts.append(f"rows +{row_count} ({rows_shifted} tile(s))")
        if col_count:
            parts.append(f"cols +{col_count} ({cols_shifted} tile(s))")
        vlog(verbose, f"[{label}] push applied for destination {bounds_s}: " + ", ".join(parts))

    return (row_count, col_count)
