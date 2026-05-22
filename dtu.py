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

import sys
import traceback

from dashboard_tile_utility.main import main


def _debug_enabled(argv: list[str]) -> bool:
    return "--debug" in argv


def _format_user_error(exc: BaseException) -> str:
    if isinstance(exc, FileNotFoundError):
        return f"File not found: {exc.filename!r}"
    if isinstance(exc, PermissionError):
        return f"Permission denied: {getattr(exc, 'filename', None)!r}"
    try:
        import json
        if isinstance(exc, json.JSONDecodeError):
            return f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
    except Exception:
        pass
    return str(exc) or exc.__class__.__name__


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("ERROR: cancelled.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        if _debug_enabled(sys.argv[1:]):
            traceback.print_exc()
        else:
            msg = _format_user_error(exc)
            print(f"ERROR: {msg}", file=sys.stderr)
            print("Use --debug for a full traceback.", file=sys.stderr)
        raise SystemExit(2)
