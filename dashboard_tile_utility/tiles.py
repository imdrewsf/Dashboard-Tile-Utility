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

import re

from typing import Any, Dict, List, Tuple, Optional

from .util import die


_INT_RE = re.compile(r"^[+-]?\d+$")


def _int_from_string_or_none(value: str) -> Optional[int]:
    s = value.strip()
    if not _INT_RE.fullmatch(s):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def as_int(tile: Dict[str, Any], key: str) -> int:
    if key not in tile:
        die(f"Tile missing required key '{key}': {tile}")
    v = tile[key]
    if isinstance(v, bool):
        die(f"Tile key '{key}' must be an int, got bool: {tile}")
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        n = _int_from_string_or_none(v)
        if n is not None:
            return n
    die(f"Tile key '{key}' must be an int, got {type(v).__name__}={v!r}: {tile}")
    return 0  # unreachable


def _pos_int_from_value(tile: Dict[str, Any], key: str, v: Any) -> int:
    if isinstance(v, bool):
        die(f"Tile key '{key}' must be a positive int, got bool: {tile}")
    if isinstance(v, int):
        n = v
    elif isinstance(v, float) and float(v).is_integer():
        n = int(v)
    elif isinstance(v, str):
        n0 = _int_from_string_or_none(v)
        if n0 is not None:
            n = n0
        else:
            # Allow numeric strings like "2.0" (some exporters stringify numbers).
            try:
                f = float(v.strip())
                if float(f).is_integer():
                    n = int(f)
                else:
                    raise ValueError()
            except Exception:
                die(f"Tile key '{key}' must be a positive int, got {type(v).__name__}={v!r}: {tile}")
    else:
        die(f"Tile key '{key}' must be a positive int, got {type(v).__name__}={v!r}: {tile}")
    if n < 1:
        die(f"Tile key '{key}' must be >= 1, got {n}: {tile}")
    return n


def _ci_key(tile: Dict[str, Any], target_lower: str) -> Optional[str]:
    """Return the first key in tile whose lowercase matches target_lower."""
    for k in tile.keys():
        if isinstance(k, str) and k.lower() == target_lower:
            return k
    return None


def _nested_span(tile: Dict[str, Any], axis: str) -> Optional[int]:
    """Best-effort span lookup from nested objects.

    Some exporters store spans as nested objects, e.g.
      {"size": {"x": 2, "y": 1}}

    axis: "x" for col span, "y" for row span
    """
    if axis not in ("x", "y"):
        return None
    containers = ["size", "Size", "dimensions", "Dimensions", "dim", "Dim"]
    x_keys = ["x", "w", "width", "cols", "col", "spanX", "xSpan"]
    y_keys = ["y", "h", "height", "rows", "row", "spanY", "ySpan"]
    want = x_keys if axis == "x" else y_keys

    for ck in containers:
        obj = tile.get(ck)
        if isinstance(obj, dict):
            for kk in want:
                k_actual = _ci_key(obj, kk.lower())
                if k_actual is not None:
                    return _pos_int_from_value(tile, f"{ck}.{k_actual}", obj.get(k_actual))
    return None


def _ci_get_pos_int(tile: Dict[str, Any], key_lower: str) -> Optional[int]:
    k = _ci_key(tile, key_lower)
    if k is None:
        return None
    return _pos_int_from_value(tile, k, tile.get(k))


def get_span(tile: Dict[str, Any], keys: List[str], default: int = 1) -> int:
    """Strict synonym span lookup.

    If more than one of the provided keys exists and values differ, this errors.
    """
    found: List[Tuple[str, int]] = []
    for k in keys:
        if k in tile:
            found.append((k, _pos_int_from_value(tile, k, tile[k])))

    if not found:
        return default

    vals = {v for _, v in found}
    if len(vals) > 1:
        die(f"Conflicting span values for {keys}: {found} in tile {tile}")

    return found[0][1]


def get_span_with_fallback(
    tile: Dict[str, Any],
    primary_keys: List[str],
    fallback_keys: List[str],
    default: int = 1,
) -> int:
    """Span lookup with a primary and a fallback key set.

    This preserves strict conflict detection within each set, but will only consult
    the fallback keys if none of the primary keys are present.

    Rationale: some dashboard exports use width/height instead of colSpan/rowSpan.
    """
    for keys in (primary_keys, fallback_keys):
        if any(k in tile for k in keys):
            return get_span(tile, keys, default=default)

    # Case-insensitive support (some exporters vary casing).
    for k in primary_keys:
        ki = _ci_key(tile, k.lower())
        if ki is not None:
            return get_span(tile, [ki], default=default)
    for k in fallback_keys:
        ki = _ci_key(tile, k.lower())
        if ki is not None:
            return get_span(tile, [ki], default=default)

    return default


def tile_row_extent(tile: Dict[str, Any]) -> Tuple[int, int]:
    r = as_int(tile, "row")
    # Hubitat exports commonly use rowSpan/colSpan. Some variants (including third-party tools)
    # may instead use width/height or sizeX/sizeY style keys. We support a best-effort fallback.
    rs = get_span_with_fallback(
        tile,
        ["rowSpan", "rowspan"],
        [
            "height", "Height", "h",
            "sizeY", "sizey", "SizeY",
            "ySpan", "yspan", "spanY", "spany",
            "tileHeight", "tileheight",
            "rows", "Rows",
        ],
        default=1,
    )
    if rs == 1:
        nested = _nested_span(tile, "y")
        if nested is not None:
            rs = nested
    if rs == 1:
        # Some variants store an absolute end row instead of a span.
        for end_key in ("rowend", "endrow", "row2", "bottom", "r2"):
            endv = _ci_get_pos_int(tile, end_key)
            if endv is not None:
                if endv < r:
                    die(f"Tile end-row '{end_key}' must be >= row ({r}), got {endv}: {tile}")
                rs = endv - r + 1
                break
    return (r, r + rs - 1)


def tile_col_extent(tile: Dict[str, Any]) -> Tuple[int, int]:
    c = as_int(tile, "col")
    cs = get_span_with_fallback(
        tile,
        ["colSpan", "colspan"],
        [
            "width", "Width", "w",
            "sizeX", "sizex", "SizeX",
            "xSpan", "xspan", "spanX", "spanx",
            "tileWidth", "tilewidth",
            "cols", "Cols",
        ],
        default=1,
    )
    if cs == 1:
        nested = _nested_span(tile, "x")
        if nested is not None:
            cs = nested
    if cs == 1:
        # Some variants store an absolute end col instead of a span.
        for end_key in ("colend", "endcol", "col2", "right", "c2"):
            endv = _ci_get_pos_int(tile, end_key)
            if endv is not None:
                if endv < c:
                    die(f"Tile end-col '{end_key}' must be >= col ({c}), got {endv}: {tile}")
                cs = endv - c + 1
                break
    return (c, c + cs - 1)


def rect(tile: Dict[str, Any]) -> Tuple[int, int, int, int]:
    r1, r2 = tile_row_extent(tile)
    c1, c2 = tile_col_extent(tile)
    return (r1, r2, c1, c2)


def set_int_like(tile: Dict[str, Any], key: str, new_value: int) -> None:
    old = tile.get(key, None)
    if old is None:
        die(f"Tile missing required key '{key}' (cannot set): {tile}")
    if isinstance(old, int):
        tile[key] = int(new_value)
    elif isinstance(old, str):
        tile[key] = str(int(new_value))
    else:
        die(f"Tile key '{key}' must be int or str to update, got {type(old).__name__}: {tile}")


def verify_tiles_minimum(tiles: List[Any]) -> None:
    if len(tiles) == 0:
        die("'tiles' list is empty. Expected at least one tile.")
    for t in tiles:
        if not isinstance(t, dict):
            die(f"Each tile must be an object/dict, got: {type(t).__name__}")
        _ = as_int(t, "id")
        _ = as_int(t, "row")
        _ = as_int(t, "col")
