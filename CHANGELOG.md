# Changelog

## [1.0.0] - 2026-05-22

First public release.

### Added

- **Import / output** — read dashboard layout JSON from the hub, a file, or the clipboard (default); write the modified layout back to the hub, a file, the terminal, or the clipboard. Multiple output destinations are supported.
- **Tile actions** — `move`, `copy`, and `merge` (from another dashboard) tiles by row, column, or rectangular range; `clear` tiles in place; and `prune` / `prune_except` tiles by tile id or device id (with explicit values, comparisons, and ranges).
- **Layout actions** — `insert` and `delete` full or partial rows/columns, `crop` to a region, `spacing` to add/set uniform spacing between tiles, and `trim` empty rows/columns from the top and left.
- **Selection modes** — `--select:include_partial`, `--select:exclude_partial`, and `--select:only_partial` to control how tiles crossing target boundaries are handled.
- **Conflict handling** — destination-overlap detection that aborts by default, with `--overlaps:allow` and `--overlaps:skip` options; `--overlaps:remove_all` / `--overlaps:remove_partial` for distributing overlapping tiles during spacing.
- **CSS support** — duplicate and remap tile-scoped `customCSS` rules when tiles are copied/merged; remove rules for deleted tiles (`--css:cleanup`); scrub orphaned rules (`--scrub_css`); copy rules between tiles (`--copy_css` with merge/replace/overwrite/add modes); clear rules (`--clear_css`); and reformat/sort rules (`--compact_css`). Handles selector lists, `@media` blocks, declaration-block tile references, and CSS comments (including commented-out rules).
- **Visual layout maps** — `--show_map` (full / no_scale / conflicts) with optional tile ids (`--show_ids`) and axis labels (`--show_axis`) to preview changes and conflicts in the terminal.
- **Tile lists** — `--list_tiles` (plain / tree / overlap / nested / conflicts) with configurable sort keys.
- **JSON sorting** — `--sort_json` to reorder how tiles are listed in the layout JSON (cosmetic only).
- **Undo / backup** — automatic backups before changes, `--undo_last` to restore, `--lock_backup` for batch workflows, and `--confirm_keep` to review and keep or undo an action. Direct-to-hub restores include safeguards against overwriting a different dashboard, restoring stale backups, or clobbering hub-side edits.
- **Output / debug controls** — `--quiet`, `--verbose`, and `--debug`, plus `--force` to suppress confirmation prompts.
- **Cross-platform support** — Windows, macOS, and Linux on Python 3.8+ with no third-party dependencies.

[1.0.0]: https://github.com/<your-username>/dashboard_tile_utility/releases/tag/v1.0.0
