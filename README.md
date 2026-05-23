# Dashboard Tile Utility

A command-line tool to import, modify, and output [Hubitat](https://hubitat.com/) dashboard tile layouts.

Dashboard Tile Utility (`dtu`) edits the `tiles` list inside a Hubitat dashboard layout JSON while preserving everything else unchanged. It lets you move, copy, merge, delete, clear, prune, crop, space, and trim tiles — individually, by row or column, or by rectangular range — with conflict detection, visual previews, and custom-CSS handling. Layouts can be read from and written back to the hub directly, to files, the clipboard, or the terminal.

## Features

- **Tile actions** — move, copy, merge (from another dashboard), clear, and prune tiles by row, column, range, tile id, or device id.
- **Layout actions** — insert/delete rows or columns, crop to a region, adjust uniform spacing, and trim empty space.
- **CSS support** — duplicate, remap, remove, and reformat tile-scoped rules in `customCSS`, with comment-block awareness and orphan cleanup.
- **Conflict prevention** — actions abort (or skip/allow on request) when tiles would overlap.
- **Visual maps** — preview proposed changes, tile ids, and conflicts in the terminal before committing.
- **Tile lists** — generate tables of tiles and their attributes.
- **Undo / backup** — automatic backups before changes, with safeguards for direct-to-hub restores.

See the **[full documentation](Documentation/README.md)** for every action, option, and example.  
For the most up to date documentation refer to the **[PDF Version](Documentation/DTU_Documentation_v1.0.0.pdf)** .

## Requirements

- **Python 3.8 or higher** — no third-party packages required.
- **Operating systems:** Windows, macOS, Linux.
- **Clipboard (optional, used by default):** built in on Windows (PowerShell) and macOS (`pbpaste`/`pbcopy`); on Linux install `wl-clipboard` (Wayland) or `xclip` (X11), or fall back to `python3-tk`.
- **Hub access (optional):** must be on the same local network as the hub, with hub security disabled and a local dashboard URL (including the access token).

## Installation

No installation or dependencies are required — clone the repository and run the script directly:

```bash
git clone https://github.com/<your-username>/dashboard_tile_utility.git
cd dashboard_tile_utility
python dtu.py --help
```

## Quick Start

By default, `dtu` reads a layout from the clipboard and writes the modified layout back to the clipboard. Copy your dashboard layout JSON, run an action, then paste the result back into Hubitat.

```bash
# Show the short help / full help
python dtu.py --help
python dtu.py --help:full

# Move columns 1-14 to start at column 85, importing/exporting via the hub,
# and show before/after maps
python dtu.py --import:hub "<dashboard_local_url>" --move:cols 1 14 85 --output:hub --show_map:no_scale

# Copy a rectangular range of tiles to a new location (clipboard in/out)
python dtu.py --copy:range 1 1 20 20 40 40

# Crop to a region, clean up orphaned CSS, and save to a file
python dtu.py --crop:range 1 1 85 85 --force --css:cleanup --output:file "layout.json"

# Undo the last run
python dtu.py --undo_last
```

A typical hub dashboard URL (found in your Hubitat dashboard settings) looks like:

```
http://<hub-ip>/apps/api/<dashId>/dashboard/<dashId>?access_token=<token>&local=true
```

> **Tip:** Use `--show_map` to preview changes and `--confirm_keep` to review an action before keeping it. Backups are written automatically so you can always `--undo_last`.

## Documentation

The complete reference — every action, selection mode, CSS-handling rule, and worked example, with diagrams — is in **[Documentation/README.md](Documentation/README.md)**.

## License

Copyright 2026 Andrew Peck

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
