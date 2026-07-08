---
name: codex-project-zip
description: Package a Codex workspace or software project into a clean, shareable ZIP archive. Use when the user asks to compress, zip, export, send, hand off, share, archive, or deliver a Codex project/workspace/folder while excluding heavy, generated, cache, VCS, dependency, and sensitive files.
---

# Codex Project ZIP

## Overview

Create a portable ZIP of the current project for sharing with another person. Prefer the bundled script because it applies repeatable exclusions, writes a manifest, computes SHA256, and verifies the archive.

## Workflow

1. Identify the project root. Default to the current working directory unless the user names another folder.
2. Decide whether to include local outputs. Exclude dependency folders, build artifacts, caches, VCS metadata, logs, and secret-bearing files by default.
3. Run `scripts/package_project.py` with the source directory and a destination ZIP path.
4. Inspect the JSON result. Report the ZIP path, size, file count, SHA256, and any skipped-sensitive files.
5. If the user explicitly wants secrets, credentials, `.env`, `.git`, dependency folders, or build outputs included, warn first and use explicit `--include` patterns only for the requested files.

## Quick Commands

Package the current directory:

```bash
python scripts/package_project.py . --output ./outputs/project-share.zip
```

Package a named folder:

```bash
python scripts/package_project.py /path/to/project --output /path/to/project-share.zip
```

Add extra exclusions:

```bash
python scripts/package_project.py . --output ./outputs/project-share.zip --exclude "screenshots/**" --exclude "*.mp4"
```

Force-include an otherwise excluded file only after confirming it is safe:

```bash
python scripts/package_project.py . --output ./outputs/project-share.zip --include ".env.example"
```

## Default Exclusions

The script excludes common non-shareable paths:

- VCS and editor state: `.git`, `.svn`, `.hg`, `.idea`, `.vscode`
- Dependencies and caches: `node_modules`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
- Build output: `dist`, `build`, `.next`, `.nuxt`, `target`, `coverage`
- Logs and temporary files: `*.log`, `*.tmp`, `*.bak`, `.DS_Store`, `Thumbs.db`
- Sensitive files: `.env`, `.env.*` except `.env.example`, credentials, private keys, token files

## Output

The ZIP contains:

- the selected project files under a single top-level folder,
- `PACKAGE_MANIFEST.json` with included and excluded counts,
- `PACKAGE_README.txt` with source, creation time, SHA256, and review notes.

Treat the output as a shareable artifact, but still remind the user to review it if the project may contain private data.
