# Codex Migration Skills

Two local Codex skills for packaging and moving Codex work between machines.

## Skills

- `codex-project-zip`: package a Codex workspace or software project into a clean, shareable ZIP archive.
- `codex-account-migration`: export and restore a portable local Codex setup bundle for another computer or Codex account.

## Install

Copy the skill folders into your Codex skills directory:

```powershell
Copy-Item -Recurse .\skills\codex-project-zip "$env:USERPROFILE\.codex\skills\"
Copy-Item -Recurse .\skills\codex-account-migration "$env:USERPROFILE\.codex\skills\"
```

If `CODEX_HOME` is set, copy them to `$env:CODEX_HOME\skills\` instead.

## Usage

Ask Codex:

```text
Use $codex-project-zip to package this project into a clean shareable ZIP.
```

```text
Use $codex-account-migration to export my portable Codex setup for another computer.
```

## Safety Notes

These skills are conservative by default. They exclude common secret-bearing files such as `.env`, auth/session files, API keys, tokens, credentials, private keys, VCS metadata, dependency folders, caches, and build output.

`codex-account-migration` does not clone OpenAI/Codex account identity, subscriptions, org permissions, billing, login sessions, or cloud-only history. Log into the destination Codex account normally, then import local materials.

## License

MIT
