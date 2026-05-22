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

from typing import Any, Dict, List, Optional, Tuple, Union

from .geometry import ranges_overlap, rects_overlap
from .tiles import as_int, rect, tile_col_extent, tile_row_extent

SelectionMode = Union[str, bool, None]


# Cell-based selection model:
# - target ranges are inclusive (spreadsheet-style)
# - default selection uses the tile's upper-left cell
# - partial selection means the tile occupies at least one target cell and at least one non-target cell

def normalize_selection_mode(mode: SelectionMode) -> str:
    if mode is True:
        return "include_partial"
    if mode in (False, None, "", "default"):
        return "default"
    mode_s = str(mode)
    if mode_s not in {"default", "include_partial", "exclude_partial", "only_partial"}:
        raise ValueError(f"Unknown selection mode: {mode_s}")
    return mode_s


def _row_default(tile: Dict[str, Any], start_row: int, end_row: int) -> bool:
    r0 = as_int(tile, "row")
    return start_row <= r0 <= end_row


def _row_intersects(tile: Dict[str, Any], start_row: int, end_row: int) -> bool:
    r1, r2 = tile_row_extent(tile)
    return ranges_overlap(r1, r2, start_row, end_row)


def _row_contained(tile: Dict[str, Any], start_row: int, end_row: int) -> bool:
    r0 = as_int(tile, "row")
    _r1, r2 = tile_row_extent(tile)
    return start_row <= r0 <= end_row and r2 <= end_row


def _col_default(tile: Dict[str, Any], start_col: int, end_col: int) -> bool:
    c0 = as_int(tile, "col")
    return start_col <= c0 <= end_col


def _col_intersects(tile: Dict[str, Any], start_col: int, end_col: int) -> bool:
    c1, c2 = tile_col_extent(tile)
    return ranges_overlap(c1, c2, start_col, end_col)


def _col_contained(tile: Dict[str, Any], start_col: int, end_col: int) -> bool:
    c0 = as_int(tile, "col")
    _c1, c2 = tile_col_extent(tile)
    return start_col <= c0 <= end_col and c2 <= end_col


def _rect_default(tile: Dict[str, Any], top_row: int, left_col: int, bottom_row: int, right_col: int) -> bool:
    r0 = as_int(tile, "row")
    c0 = as_int(tile, "col")
    return top_row <= r0 <= bottom_row and left_col <= c0 <= right_col


def _rect_intersects(tile: Dict[str, Any], top_row: int, left_col: int, bottom_row: int, right_col: int) -> bool:
    return rects_overlap(rect(tile), (top_row, bottom_row, left_col, right_col))


def _rect_contained(tile: Dict[str, Any], top_row: int, left_col: int, bottom_row: int, right_col: int) -> bool:
    r0 = as_int(tile, "row")
    c0 = as_int(tile, "col")
    r1, r2, c1, c2 = rect(tile)
    return top_row <= r0 <= bottom_row and left_col <= c0 <= right_col and r2 <= bottom_row and c2 <= right_col


def _apply_mode(default: bool, intersects: bool, contained: bool, mode: SelectionMode) -> bool:
    mode_s = normalize_selection_mode(mode)
    if mode_s == "default":
        return default
    if mode_s == "include_partial":
        return default or (intersects and not default)
    if mode_s == "exclude_partial":
        return contained
    if mode_s == "only_partial":
        return intersects and not contained
    return default


# Row/col range matching is used for insert/delete range filters too. There, "contained"
# means the tile must start inside the filter range and must not extend beyond its far edge.
# This matches the documented selection meaning when partial tiles are excluded.
def tile_matches_row_range(tile: Dict[str, Any], row_range: Optional[Tuple[int, int]], include_overlap: SelectionMode) -> bool:
    if row_range is None:
        return True
    r1, r2 = row_range
    return _apply_mode(
        _row_default(tile, r1, r2),
        _row_intersects(tile, r1, r2),
        _row_contained(tile, r1, r2),
        include_overlap,
    )


def tile_matches_col_range(tile: Dict[str, Any], col_range: Optional[Tuple[int, int]], include_overlap: SelectionMode) -> bool:
    if col_range is None:
        return True
    c1, c2 = col_range
    return _apply_mode(
        _col_default(tile, c1, c2),
        _col_intersects(tile, c1, c2),
        _col_contained(tile, c1, c2),
        include_overlap,
    )


def select_tiles_by_row_range(
    tiles: List[Dict[str, Any]],
    start_row: int,
    end_row: int,
    include_overlap: SelectionMode,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for t in tiles:
        if _apply_mode(
            _row_default(t, start_row, end_row),
            _row_intersects(t, start_row, end_row),
            _row_contained(t, start_row, end_row),
            include_overlap,
        ):
            selected.append(t)
    return selected


def select_tiles_by_col_range(
    tiles: List[Dict[str, Any]],
    start_col: int,
    end_col: int,
    include_overlap: SelectionMode,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for t in tiles:
        if _apply_mode(
            _col_default(t, start_col, end_col),
            _col_intersects(t, start_col, end_col),
            _col_contained(t, start_col, end_col),
            include_overlap,
        ):
            selected.append(t)
    return selected


def select_tiles_by_rect_range(
    tiles: List[Dict[str, Any]],
    top_row: int,
    left_col: int,
    bottom_row: int,
    right_col: int,
    include_overlap: SelectionMode,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for t in tiles:
        if _apply_mode(
            _rect_default(t, top_row, left_col, bottom_row, right_col),
            _rect_intersects(t, top_row, left_col, bottom_row, right_col),
            _rect_contained(t, top_row, left_col, bottom_row, right_col),
            include_overlap,
        ):
            selected.append(t)
    return selected


def find_straddlers_rows(tiles: List[Dict[str, Any]], start_row: int, end_row: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in tiles:
        if _row_intersects(t, start_row, end_row) and not _row_default(t, start_row, end_row):
            out.append(t)
    return out


def find_straddlers_cols(tiles: List[Dict[str, Any]], start_col: int, end_col: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in tiles:
        if _col_intersects(t, start_col, end_col) and not _col_default(t, start_col, end_col):
            out.append(t)
    return out
