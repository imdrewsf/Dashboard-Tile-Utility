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

import copy
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .geometry import rects_overlap
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
    if mode != "push":
        die(f"Invalid overlap push mode: {mode!r}. Use --overlaps:push BUFFER.")
    try:
        buffer_i = int(buffer)
    except Exception:
        die(f"--overlaps:push BUFFER must be an integer, got {buffer!r}.")
    if buffer_i < 0:
        die(f"--overlaps:push BUFFER must be >= 0, got {buffer_i}.")
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


def _shift_rect(r: Rect, *, row_delta: int = 0, col_delta: int = 0) -> Rect:
    r1, r2, c1, c2 = r
    return (r1 + row_delta, r2 + row_delta, c1 + col_delta, c2 + col_delta)


def _rect_overlaps_any(r: Rect, rects: Iterable[Rect]) -> bool:
    return any(rects_overlap(r, other) for other in rects)


def _remaining_destination_conflicts(stationary_tiles: List[Dict[str, Any]], destination_rects: List[Rect]) -> bool:
    if not destination_rects:
        return False
    for t in stationary_tiles:
        try:
            if _rect_overlaps_any(rect(t), destination_rects):
                return True
        except Exception:
            continue
    return False


def _overlapping_ids(tiles: List[Dict[str, Any]], area: Rect) -> set[int]:
    ids: set[int] = set()
    for t in tiles:
        try:
            if rects_overlap(rect(t), area):
                ids.add(as_int(t, "id"))
        except Exception:
            continue
    return ids


def _count_area_overlaps(tiles: List[Dict[str, Any]], area: Rect) -> int:
    return len(_overlapping_ids(tiles, area))


def _count_destination_conflicts(tiles: List[Dict[str, Any]], destination_rects: List[Rect]) -> int:
    if not destination_rects:
        return 0
    count = 0
    for t in tiles:
        try:
            r = rect(t)
        except Exception:
            continue
        if _rect_overlaps_any(r, destination_rects):
            count += 1
    return count


def _reserve_bounds(bounds: Rect, buffer: int) -> Rect:
    top, bottom, left, right = bounds
    return (top, bottom + buffer, left, right + buffer)


def _row_seed_ids(original_rects: Dict[int, Rect], bounds: Rect, reserve: Rect) -> set[int]:
    """Tiles below the destination/buffer column band that must move down.

    Row pushing is only for the portion of the reserved space below the
    destination footprint.  Tiles in the destination row band are handled by the
    column push.  This keeps the layout change localized to the right and below
    the destination instead of choosing an arbitrary direction for conflicts.
    """
    _top, bottom, _left, _right = bounds
    _rtop, rbottom, left, right = reserve
    if rbottom <= bottom:
        return set()
    seed_area = (bottom + 1, rbottom, left, right)
    return {
        tid
        for tid, r in original_rects.items()
        if r[0] > bottom and rects_overlap(r, seed_area)
    }


def _col_seed_ids(original_rects: Dict[int, Rect], bounds: Rect, reserve: Rect) -> set[int]:
    """Tiles to the right/inside the destination row band that must move right.

    Column pushing is for tiles in the destination's row band, including tiles
    occupying the destination footprint and the requested right-side buffer.
    Tiles that start left of the destination and merely span into it are not
    swept into the push.
    """
    top, bottom, _left, _right = bounds
    _rtop, _rbottom, left, right = reserve
    seed_area = (top, bottom, left, right)
    return {
        tid
        for tid, r in original_rects.items()
        if r[2] >= left and rects_overlap(r, seed_area)
    }


def _spans_overlap(a1: int, a2: int, b1: int, b2: int) -> bool:
    return a1 <= b2 and b1 <= a2




def _tiles_touch(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """Return True when two tiles share an edge but do not overlap.

    This mirrors the GUI push cluster rule: touch-only clusters move together,
    while existing overlaps are handled separately as container/content groups.
    """
    ar1, ar2, ac1, ac2 = rect(a)
    br1, br2, bc1, bc2 = rect(b)
    if rects_overlap((ar1, ar2, ac1, ac2), (br1, br2, bc1, bc2)):
        return False
    v_adj = (ac2 + 1 == bc1 or bc2 + 1 == ac1) and _spans_overlap(ar1, ar2, br1, br2)
    h_adj = (ar2 + 1 == br1 or br2 + 1 == ar1) and _spans_overlap(ac1, ac2, bc1, bc2)
    return v_adj or h_adj


def _build_push_clusters(tiles: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    seen = [False] * len(tiles)
    for i in range(len(tiles)):
        if seen[i]:
            continue
        stack = [i]
        comp: List[int] = []
        seen[i] = True
        while stack:
            k = stack.pop()
            comp.append(k)
            for j in range(len(tiles)):
                if not seen[j] and _tiles_touch(tiles[k], tiles[j]):
                    seen[j] = True
                    stack.append(j)
        groups.append([tiles[idx] for idx in comp])
    return groups


def _rect_to_blocker(r: Rect, n: int) -> Dict[str, Any]:
    r1, r2, c1, c2 = r
    return {
        "id": -(n + 1),
        "row": r1,
        "col": c1,
        "rowSpan": r2 - r1 + 1,
        "colSpan": c2 - c1 + 1,
    }


def _tile_height(t: Dict[str, Any]) -> int:
    r1, r2, _c1, _c2 = rect(t)
    return r2 - r1 + 1


def _tile_width(t: Dict[str, Any]) -> int:
    _r1, _r2, c1, c2 = rect(t)
    return c2 - c1 + 1


def _cascade_push_preserve(
    tiles: List[Dict[str, Any]],
    blockers: List[Dict[str, Any]],
    buffer: int,
) -> List[Dict[str, Any]]:
    """GUI-equivalent preserve-mode cascade push.

    This is the same model used by Dashboard Layout Studio for move/copy with
    push: directly-conflicting tiles choose a right/down push direction
    individually, then each direction expands to include any touched cluster,
    container/content partner, and downstream tile that would be overlapped by
    the shifted result.
    """
    working = [copy.deepcopy(t) for t in tiles]
    original_by_id: Dict[int, Dict[str, Any]] = {}
    original_rects: Dict[int, Rect] = {}
    for t in tiles:
        try:
            tid = as_int(t, "id")
            original_by_id[tid] = t
            original_rects[tid] = rect(t)
        except Exception:
            continue

    groups = _build_push_clusters(working)
    id_to_group: Dict[int, List[Dict[str, Any]]] = {}
    for group in groups:
        for wt in group:
            try:
                id_to_group[as_int(wt, "id")] = group
            except Exception:
                continue

    def is_inside(a_id: int, b_id: int) -> bool:
        ar = original_rects.get(a_id)
        br = original_rects.get(b_id)
        if ar is None or br is None:
            return False
        return ar[0] >= br[0] and ar[2] >= br[2] and ar[1] <= br[1] and ar[3] <= br[3]

    def expanded_group(tile_id: int) -> List[Dict[str, Any]]:
        ids = {as_int(t, "id") for t in id_to_group.get(tile_id, [])}
        for wt in working:
            try:
                wid = as_int(wt, "id")
            except Exception:
                continue
            if is_inside(wid, tile_id) or is_inside(tile_id, wid):
                ids.add(wid)
        return [wt for wt in working if as_int(wt, "id") in ids]

    right_set: Dict[int, int] = {}
    down_set: Dict[int, int] = {}

    for t in working:
        try:
            tid = as_int(t, "id")
            tr1, _tr2, tc1, tc2 = rect(t)
        except Exception:
            continue
        best_dir: Optional[str] = None
        best_amt = 0
        for bl in blockers:
            if not rects_overlap(rect(t), rect(bl)):
                continue
            br1, _br2, bc1, bc2 = rect(bl)
            d_amt = br1 + _tile_height(bl) + buffer - tr1
            r_amt = bc1 + _tile_width(bl) + buffer - tc1
            col_contained = tc1 >= bc1 and (tc2 + 1) <= (bc2 + 1)
            if col_contained:
                direction = "right"
                amount = max(0, r_amt)
            elif d_amt > 0 and r_amt > 0:
                if d_amt < r_amt:
                    direction = "down"
                    amount = d_amt
                else:
                    direction = "right"
                    amount = r_amt
            elif d_amt > 0:
                direction = "down"
                amount = d_amt
            elif r_amt > 0:
                direction = "right"
                amount = r_amt
            else:
                continue

            if amount > best_amt:
                best_dir = direction
                best_amt = amount

        if best_dir == "right":
            right_set[tid] = best_amt
        elif best_dir == "down":
            down_set[tid] = best_amt

    max_right = max(right_set.values()) if right_set else 0
    max_down = max(down_set.values()) if down_set else 0
    if not max_right and not max_down:
        return working

    def expand_apply(direct_ids: Iterable[int], shift_down: int, shift_right: int) -> None:
        affected: set[int] = set()
        for direct_id in direct_ids:
            for member in expanded_group(int(direct_id)):
                affected.add(as_int(member, "id"))

        grew = True
        while grew:
            grew = False
            affected_now = set(affected)
            for t in working:
                tid = as_int(t, "id")
                if tid in affected_now:
                    continue
                for a in working:
                    aid = as_int(a, "id")
                    if aid not in affected_now:
                        continue
                    shifted_a = copy.deepcopy(a)
                    if shift_down:
                        set_int_like(shifted_a, "row", as_int(shifted_a, "row") + shift_down)
                    if shift_right:
                        set_int_like(shifted_a, "col", as_int(shifted_a, "col") + shift_right)
                    if rects_overlap(rect(t), rect(shifted_a)):
                        for member in expanded_group(tid):
                            affected.add(as_int(member, "id"))
                        grew = True
                        break

        for t in working:
            tid = as_int(t, "id")
            if tid not in affected:
                continue
            if shift_down:
                set_int_like(t, "row", as_int(t, "row") + shift_down)
            if shift_right:
                set_int_like(t, "col", as_int(t, "col") + shift_right)

    if max_right:
        expand_apply(right_set.keys(), 0, max_right)
    if max_down:
        expand_apply(down_set.keys(), max_down, 0)

    return working

def _expand_push_chain(
    original_rects: Dict[int, Rect],
    initial_ids: set[int],
    reserve: Rect,
    *,
    row_delta: int = 0,
    col_delta: int = 0,
) -> set[int]:
    """Expand a push chain just far enough to preserve following tile order.

    Starting with tiles occupying the reserved destination area, include only
    downstream tiles that would be crossed, overtaken, or collided with by a
    pushed tile.  All tiles in a directional push chain move by the same delta,
    preserving the spacing between them.
    """
    affected = set(initial_ids)
    if not affected:
        return affected

    top, _bottom, left, _right = reserve
    changed = True
    while changed:
        changed = False
        affected_rects = [original_rects[tid] for tid in affected if tid in original_rects]
        for tid, r in original_rects.items():
            if tid in affected:
                continue

            # Keep the push directional.  Push may affect tiles at/right of the
            # destination or at/below it, but not tiles that originate above/left
            # and merely hang into the destination.
            if row_delta and r[0] < top:
                continue
            if col_delta and r[2] < left:
                continue

            include = False
            for ar in affected_rects:
                shifted = _shift_rect(ar, row_delta=row_delta, col_delta=col_delta)

                if row_delta:
                    # Same/overlapping column lane and candidate starts within
                    # the vertical sweep of the pushed tile.
                    if (
                        _spans_overlap(r[2], r[3], ar[2], ar[3])
                        and r[0] >= ar[0]
                        and r[0] <= shifted[1]
                    ):
                        include = True
                        break

                if col_delta:
                    # Same/overlapping row lane and candidate starts within the
                    # horizontal sweep of the pushed tile.
                    if (
                        _spans_overlap(r[0], r[1], ar[0], ar[1])
                        and r[2] >= ar[2]
                        and r[2] <= shifted[3]
                    ):
                        include = True
                        break

            if include:
                affected.add(tid)
                changed = True

    return affected


def _current_rects(stationary_tiles: List[Dict[str, Any]]) -> Dict[int, Rect]:
    rects: Dict[int, Rect] = {}
    for t in stationary_tiles:
        try:
            rects[as_int(t, "id")] = rect(t)
        except Exception:
            continue
    return rects


def _plan_col_push(original_rects: Dict[int, Rect], bounds: Rect, reserve: Rect) -> Tuple[int, set[int]]:
    _top, _bottom, _left, right = reserve
    seed_ids = _col_seed_ids(original_rects, bounds, reserve)
    if not seed_ids:
        return (0, set())
    seed_left = min(original_rects[tid][2] for tid in seed_ids if tid in original_rects)
    col_delta = max(0, right + 1 - seed_left)
    if col_delta <= 0:
        return (0, set())
    affected_ids = _expand_push_chain(original_rects, seed_ids, reserve, col_delta=col_delta)
    return (col_delta, affected_ids)


def _plan_row_push(original_rects: Dict[int, Rect], bounds: Rect, reserve: Rect) -> Tuple[int, set[int]]:
    _top, bottom, _left, _right = reserve
    seed_ids = _row_seed_ids(original_rects, bounds, reserve)
    if not seed_ids:
        return (0, set())
    seed_top = min(original_rects[tid][0] for tid in seed_ids if tid in original_rects)
    row_delta = max(0, bottom + 1 - seed_top)
    if row_delta <= 0:
        return (0, set())
    affected_ids = _expand_push_chain(original_rects, seed_ids, reserve, row_delta=row_delta)
    return (row_delta, affected_ids)


def _apply_delta(
    tiles: List[Dict[str, Any]],
    affected_ids: set[int],
    *,
    row_delta: int = 0,
    col_delta: int = 0,
) -> int:
    changed = 0
    for t in tiles:
        try:
            tid = as_int(t, "id")
        except Exception:
            continue
        if tid not in affected_ids:
            continue
        if row_delta:
            set_int_like(t, "row", as_int(t, "row") + row_delta)
        if col_delta:
            set_int_like(t, "col", as_int(t, "col") + col_delta)
        changed += 1
    return changed


def _simulate_push_plan(
    stationary_tiles: List[Dict[str, Any]],
    destination_rects: List[Rect],
    bounds: Rect,
    reserve: Rect,
    order: Sequence[str],
) -> Dict[str, Any]:
    tiles = [copy.deepcopy(t) for t in stationary_tiles]
    steps: List[Tuple[str, int, int, set[int]]] = []
    moved_ids: set[int] = set()
    total_distance = 0

    for axis in order:
        if _count_area_overlaps(tiles, reserve) == 0:
            break

        original_rects = _current_rects(tiles)
        if axis == "cols":
            delta, affected_ids = _plan_col_push(original_rects, bounds, reserve)
            if delta > 0 and affected_ids:
                changed = _apply_delta(tiles, affected_ids, col_delta=delta)
                steps.append((axis, delta, changed, set(affected_ids)))
                moved_ids |= affected_ids
                total_distance += delta * changed
        elif axis == "rows":
            delta, affected_ids = _plan_row_push(original_rects, bounds, reserve)
            if delta > 0 and affected_ids:
                changed = _apply_delta(tiles, affected_ids, row_delta=delta)
                steps.append((axis, delta, changed, set(affected_ids)))
                moved_ids |= affected_ids
                total_distance += delta * changed
        else:
            raise ValueError(f"Unknown push axis: {axis}")

    return {
        "tiles": tiles,
        "steps": steps,
        "moved_ids": moved_ids,
        "total_distance": total_distance,
        "reserve_overlaps": _count_area_overlaps(tiles, reserve),
        "destination_conflicts": _count_destination_conflicts(tiles, destination_rects),
    }


def _plan_score(plan: Dict[str, Any]) -> Tuple[int, int, int, int]:
    # Prefer a plan that clears the actual destination, then one that also clears
    # the requested buffer.  Among successful plans, move fewer tiles and fewer
    # total cells.
    return (
        int(plan["destination_conflicts"]),
        int(plan["reserve_overlaps"]),
        len(plan["moved_ids"]),
        int(plan["total_distance"]),
    )


def _choose_push_plan(
    stationary_tiles: List[Dict[str, Any]],
    destination_rects: List[Rect],
    bounds: Rect,
    reserve: Rect,
) -> Dict[str, Any]:
    # Push works like a localized insert around the destination: first clear the
    # destination row band to the right, then clear the bottom buffer downward.
    # This preserves the order/spacing of following tiles instead of choosing an
    # arbitrary direction for the initial conflict.
    return _simulate_push_plan(stationary_tiles, destination_rects, bounds, reserve, ("cols", "rows"))


def _final_positions_by_id(tiles: List[Dict[str, Any]]) -> Dict[int, Tuple[int, int]]:
    positions: Dict[int, Tuple[int, int]] = {}
    for t in tiles:
        try:
            positions[as_int(t, "id")] = (as_int(t, "row"), as_int(t, "col"))
        except Exception:
            continue
    return positions


def _apply_final_positions(
    stationary_tiles: List[Dict[str, Any]],
    final_positions: Dict[int, Tuple[int, int]],
    *,
    verbose: bool,
    debug: bool,
    label: str,
) -> Tuple[int, int]:
    shifted = 0
    total_distance = 0
    for t in stationary_tiles:
        try:
            tid = as_int(t, "id")
            old_row = as_int(t, "row")
            old_col = as_int(t, "col")
        except Exception:
            continue
        if tid not in final_positions:
            continue
        new_row, new_col = final_positions[tid]
        if new_row == old_row and new_col == old_col:
            continue
        set_int_like(t, "row", new_row)
        set_int_like(t, "col", new_col)
        shifted += 1
        total_distance += abs(new_row - old_row) + abs(new_col - old_col)
        dlog(debug, f"[{label}] --overlaps:push id={tid}: row {old_row} -> {new_row}, col {old_col} -> {new_col}")

    if shifted:
        vlog(verbose, f"[{label}] overlap push shifted {shifted} needed tile(s); total movement={total_distance} cell(s)")
    return (shifted, total_distance)


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
    """Resolve destination conflicts by pushing existing tiles right/down.

    This intentionally mirrors the Dashboard Layout Studio move/copy push logic
    in preserve mode.  A tile that overlaps the placed destination can be pushed
    right or down even when its upper-left corner is outside the destination
    footprint; this is required for edge-overlap cases such as a tile that starts
    left of the destination and crosses into it.
    """
    normalized = normalize_push_spec(push_spec)
    if normalized is None or not conflicts_by_moving_id:
        return (0, 0)

    _mode, buffer = normalized
    if not destination_rects:
        return (0, 0)

    blockers = [_rect_to_blocker(r, i) for i, r in enumerate(destination_rects)]
    worked = _cascade_push_preserve(stationary_tiles, blockers, buffer)
    final_positions = _final_positions_by_id(worked)
    shifted, total_distance = _apply_final_positions(
        stationary_tiles,
        final_positions,
        verbose=verbose,
        debug=debug,
        label=label,
    )

    if not shifted:
        bounds = union_rects(destination_rects)
        if bounds is not None:
            vlog(verbose, f"[{label}] --overlaps:push found no pushable tiles for destination r{bounds[0]}..{bounds[1]},c{bounds[2]}..{bounds[3]}")

    return (shifted, total_distance)
