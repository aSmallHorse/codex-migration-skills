#!/usr/bin/env python3
"""Export and import portable local Codex setup bundles."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile


EXCLUDE_PATTERNS = [
    ".git/**",
    ".hg/**",
    ".svn/**",
    "node_modules/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".ruff_cache/**",
    ".cache/**",
    "dist/**",
    "build/**",
    ".next/**",
    ".nuxt/**",
    "target/**",
    "coverage/**",
    "*.pyc",
    "*.log",
    "*.tmp",
    "*.bak",
    ".DS_Store",
    "Thumbs.db",
    "plugins/cache/**",
    "skills/.system/**",
]

SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "auth.json",
    "*auth*token*",
    "*session*",
    "*credential*",
    "*credentials*",
    "*secret*",
    "*secrets*",
    "*token*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
]

SAFE_EXCEPTIONS = [
    ".env.example",
    ".env.sample",
    ".env.template",
    "example.env",
]


def default_codex_home() -> Path:
    env_home = os.environ.get("CODEX_HOME")
    return Path(env_home).expanduser() if env_home else Path.home() / ".codex"


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def match_any(rel: str, patterns: list[str]) -> bool:
    rel = rel.replace("\\", "/").strip("/")
    name = PurePosixPath(rel).name
    for raw in patterns:
        pattern = raw.replace("\\", "/").strip("/")
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
            return True
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if rel == prefix or rel.startswith(prefix + "/"):
                return True
    return False


def is_sensitive(rel: str) -> bool:
    if match_any(rel, SAFE_EXCEPTIONS):
        return False
    return match_any(rel, SENSITIVE_PATTERNS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(root: Path, label: str, include_sensitive: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    included: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    if not root.exists():
        excluded.append({"root": label, "path": ".", "reason": "missing-root"})
        return included, excluded
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        rel_dir = "" if current == root else rel_posix(current, root)
        kept_dirs = []
        for dir_name in dirs:
            rel = f"{rel_dir}/{dir_name}" if rel_dir else dir_name
            if match_any(rel, EXCLUDE_PATTERNS) or match_any(rel + "/", EXCLUDE_PATTERNS):
                excluded.append({"root": label, "path": rel, "reason": "excluded-directory"})
                continue
            if is_sensitive(rel) and not include_sensitive:
                excluded.append({"root": label, "path": rel, "reason": "sensitive-directory"})
                continue
            kept_dirs.append(dir_name)
        dirs[:] = kept_dirs
        for file_name in files:
            path = current / file_name
            rel = rel_posix(path, root)
            if match_any(rel, EXCLUDE_PATTERNS):
                excluded.append({"root": label, "path": rel, "reason": "excluded-file"})
                continue
            if is_sensitive(rel) and not include_sensitive:
                excluded.append({"root": label, "path": rel, "reason": "sensitive-file"})
                continue
            included.append({"root": label, "path": rel, "source": str(path), "size": str(path.stat().st_size)})
    return included, excluded


def export_bundle(args: argparse.Namespace) -> int:
    codex_home = Path(args.codex_home).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    roots: list[tuple[str, Path]] = [("codex_home", codex_home)]
    for index, workspace in enumerate(args.workspace_root or [], start=1):
        roots.append((f"workspace_{index}", Path(workspace).expanduser().resolve()))

    included: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    for label, root in roots:
        got, skipped = collect_files(root, label, args.include_sensitive)
        included.extend(got)
        excluded.extend(skipped)

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "format": "codex-account-migration-v1",
        "created_at": created_at,
        "codex_home": str(codex_home),
        "workspace_roots": [str(Path(p).expanduser().resolve()) for p in (args.workspace_root or [])],
        "include_sensitive": bool(args.include_sensitive),
        "included_count": len(included),
        "excluded_count": len(excluded),
        "excluded_sensitive": [x for x in excluded if x["reason"].startswith("sensitive")],
        "included": [{k: v for k, v in item.items() if k != "source"} for item in included],
        "excluded": excluded,
    }

    readme = "\n".join(
        [
            "Codex local setup migration bundle",
            f"Created at: {created_at}",
            "",
            "Import after logging into the destination Codex account.",
            "This bundle does not migrate account identity, subscriptions, permissions, or cloud-only history.",
            "Sensitive auth, token, key, credential, session, and .env files are excluded by default.",
            "",
        ]
    )

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for item in included:
            arc_name = f"payload/{item['root']}/{item['path']}"
            archive.write(item["source"], arc_name)
        archive.writestr("MIGRATION_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("MIGRATION_README.txt", readme)
    with ZipFile(output, "r") as archive:
        bad = archive.testzip()
    if bad:
        raise SystemExit(f"ZIP verification failed at entry: {bad}")

    result = {
        "status": "ok",
        "mode": "export",
        "zip": str(output),
        "sha256": sha256_file(output),
        "size_bytes": output.stat().st_size,
        "included_files": len(included),
        "excluded_files": len(excluded),
        "excluded_sensitive_count": len(manifest["excluded_sensitive"]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def target_for(root_name: str, rel: str, args: argparse.Namespace) -> Path | None:
    if root_name == "codex_home":
        return Path(args.target_codex_home).expanduser().resolve() / rel
    if root_name.startswith("workspace_"):
        if not args.target_workspace_root:
            return None
        return Path(args.target_workspace_root).expanduser().resolve() / root_name / rel
    return None


def import_bundle(args: argparse.Namespace) -> int:
    bundle = Path(args.input).expanduser().resolve()
    if not bundle.is_file():
        raise SystemExit(f"Bundle not found: {bundle}")
    actions: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    backup_root = Path(args.backup_dir).expanduser().resolve() if args.backup_dir else Path(args.target_codex_home).expanduser().resolve() / f"migration-backup-{now_stamp()}"

    with ZipFile(bundle, "r") as archive:
        manifest = json.loads(archive.read("MIGRATION_MANIFEST.json").decode("utf-8"))
        if manifest.get("format") != "codex-account-migration-v1":
            raise SystemExit("Unsupported migration bundle format.")
        for entry in archive.namelist():
            if not entry.startswith("payload/") or entry.endswith("/"):
                continue
            _, root_name, rel = entry.split("/", 2)
            target = target_for(root_name, rel, args)
            if target is None:
                skipped.append({"entry": entry, "reason": "no-target-workspace-root"})
                continue
            actions.append({"entry": entry, "target": str(target)})
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    backup = backup_root / root_name / rel
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                with archive.open(entry) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

    result = {
        "status": "ok",
        "mode": "import",
        "applied": bool(args.apply),
        "bundle": str(bundle),
        "planned_or_written_files": len(actions),
        "skipped_files": len(skipped),
        "backup_dir": str(backup_root) if args.apply else None,
        "note": "Preview only. Re-run with --apply to write files." if not args.apply else "Import applied. Restart Codex if needed.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export or import local Codex setup migration bundles.")
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="Create a migration ZIP.")
    export.add_argument("--output", "-o", required=True, help="Destination ZIP path.")
    export.add_argument("--codex-home", default=str(default_codex_home()), help="Source Codex home. Defaults to CODEX_HOME or ~/.codex.")
    export.add_argument("--workspace-root", action="append", help="Workspace root to include. Repeatable.")
    export.add_argument("--include-sensitive", action="store_true", help="Include files that look sensitive. Use only after explicit confirmation.")
    export.set_defaults(func=export_bundle)

    restore = sub.add_parser("import", help="Preview or apply a migration ZIP.")
    restore.add_argument("--input", "-i", required=True, help="Migration ZIP path.")
    restore.add_argument("--target-codex-home", default=str(default_codex_home()), help="Destination Codex home.")
    restore.add_argument("--target-workspace-root", help="Destination parent folder for workspace payloads.")
    restore.add_argument("--backup-dir", help="Where overwritten destination files should be backed up.")
    restore.add_argument("--apply", action="store_true", help="Actually write files. Without this flag, only preview.")
    restore.set_defaults(func=import_bundle)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
