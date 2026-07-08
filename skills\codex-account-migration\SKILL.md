---
name: codex-account-migration
description: Export and restore a portable Codex local setup bundle for moving usable Codex materials to another computer or another Codex account while keeping the original account intact. Use when the user asks to migrate, transfer, copy, back up, restore, move, or continue their Codex setup/workspaces/skills/agents/configuration on a different machine or account.
---

# Codex Account Migration

## Overview

Create a migration bundle for local Codex materials, then restore it on another computer after the user logs into the destination Codex account. This skill does not clone cloud account identity, subscriptions, permissions, login sessions, or server-side history that is not locally available.

## Safety Rules

- Preserve the source account and source files. Never delete source data.
- Do not migrate auth/session files, API keys, tokens, `.env`, SSH keys, private keys, credentials, or browser/login state by default.
- Treat the bundle as private. It can contain project names, prompts, local instructions, and custom skills.
- On import, preview first. Require `--apply` before writing files.
- Back up destination files before overwriting.
- Tell the user to log into the destination Codex account normally before importing local materials.

## Export Workflow

1. Identify the local Codex home. Default to `$CODEX_HOME`, then `~/.codex`.
2. Identify workspace roots to carry over if requested. Use `--workspace-root` for each local workspace folder.
3. Run the script in export mode.
4. Review the JSON result and mention excluded sensitive paths.
5. Share the generated ZIP with the destination computer.

```bash
python scripts/codex_migration.py export --output ./outputs/codex-migration.zip
```

Include workspaces:

```bash
python scripts/codex_migration.py export --output ./outputs/codex-migration.zip --workspace-root /path/to/Codex
```

## Import Workflow

1. On the destination computer, install/open Codex and log into the destination account.
2. Put the migration ZIP somewhere accessible.
3. Preview import without writing:

```bash
python scripts/codex_migration.py import --input ./codex-migration.zip
```

4. If the preview looks right, apply:

```bash
python scripts/codex_migration.py import --input ./codex-migration.zip --apply
```

5. Restart Codex if imported skills, plugins, agents, or configuration are not immediately visible.

## What Gets Packaged

Default local Codex home content:

- custom skills under `skills/`, excluding bundled `.system` skills,
- agents metadata and local agent configuration when present,
- non-sensitive user configuration files,
- plugin metadata when present, excluding large caches and auth material.

Optional workspace content:

- selected workspace roots passed with `--workspace-root`,
- local `.agents` and `.codex` directories under those workspaces,
- project files, excluding `.git`, dependencies, build output, caches, logs, and secrets.

## What Does Not Migrate

- OpenAI/Codex account identity, subscription, billing, cloud access, workspace membership, or org permissions.
- Login sessions, browser cookies, OAuth tokens, API keys, SSH keys, private keys, `.env`, and credential stores.
- Server-side thread history that is not stored locally or not exposed as files.
- Installed app binaries unless the user separately asks for a full machine/app backup.

## Script

Use `scripts/codex_migration.py`. It writes `MIGRATION_MANIFEST.json` and `MIGRATION_README.txt` into the ZIP, verifies the archive, and reports skipped sensitive paths.

Use explicit `--include-sensitive` only after the user confirms they understand the risk. Prefer re-authentication on the destination computer instead.
