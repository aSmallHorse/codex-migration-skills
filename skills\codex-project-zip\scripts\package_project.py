#!/usr/bin/env python3
"""Package a project directory into a clean, shareable ZIP archive."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile


DEFAULT_EXCLUDES = [
    ".git/**",
    ".hg/**",
    ".svn/**",
    ".idea/**",
    ".vscode/**",
    "node_modules/**",
    ".venv/**",
    "venv/**",
    "env/**",
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
    "outputs/*.zip",
    "work/**",
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tmp",
    "*.temp",
    "*.bak",
    ".DS_Store",
    "Thumbs.db",
]

SENSITIVE_EXCLUDES = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*credential*",
    "*credentials*",
    "*secret*",
    "*secrets*",
    "*token*",
]

SAFE_SENSITIVE_EXCEPTIONS = [
    ".env.example",
    ".env.sample",
    ".env.template",
    "example.env",
]


def posix_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def match_any(rel: str, patterns: list[str]) -> bool:
    rel_path = PurePosixPath(rel)
    name = rel_path.name
    for pattern in patterns:
        pattern = pattern.replace("\\", "/").strip("/")
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
            return True
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if rel == prefix or rel.startswith(prefix + "/"):
                return True
    return False


def is_sensitive(rel: str) -> bool:
    if match_any(rel, SAFE_SENSITIVE_EXCEPTIONS):
        return False
    return match_any(rel, SENSITIVE_EXCLUDES)


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dir_names, file_names in os.walk(root):
        current = Path(current_root)
        rel_dir = "" if current == root else posix_rel(current, root)
        kept_dirs = []
        for dir_name in dir_names:
            rel = f"{rel_dir}/{dir_name}" if rel_dir else dir_name
            rel = rel.replace("\\", "/")
            if match_any(rel + "/", DEFAULT_EXCLUDES) or match_any(rel, DEFAULT_EXCLUDES):
                continue
            kept_dirs.append(dir_name)
        dir_names[:] = kept_dirs
        for file_name in file_names:
            files.append(current / file_name)
    return files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package a project into a clean shareable ZIP.")
    parser.add_argument("source", help="Project directory to package.")
    parser.add_argument("--output", "-o", required=True, help="Destination ZIP path.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional glob exclusion. Repeatable.")
    parser.add_argument("--include", action="append", default=[], help="Force-include glob for excluded files. Repeatable.")
    parser.add_argument("--name", help="Top-level folder name inside the ZIP. Defaults to source folder name.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = Path(args.source).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Source is not a directory: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)

    top_name = args.name or source.name or "project"
    top_name = top_name.replace("\\", "-").replace("/", "-").strip(". ") or "project"
    excludes = DEFAULT_EXCLUDES + [p.replace("\\", "/") for p in args.exclude]
    includes = [p.replace("\\", "/") for p in args.include]

    included: list[dict[str, object]] = []
    excluded: list[dict[str, str]] = []
    output_rel = None
    try:
        output_rel = posix_rel(output, source)
    except ValueError:
        pass

    for file_path in iter_files(source):
        rel = posix_rel(file_path, source)
        if output_rel and rel == output_rel:
            excluded.append({"path": rel, "reason": "output-zip"})
            continue

        forced = match_any(rel, includes)
        reason = ""
        if match_any(rel, excludes):
            reason = "default-or-custom-exclude"
        if is_sensitive(rel):
            reason = "sensitive"
        if reason and not forced:
            excluded.append({"path": rel, "reason": reason})
            continue

        included.append({"path": rel, "size": file_path.stat().st_size})

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "created_at": created_at,
        "source": str(source),
        "top_level_folder": top_name,
        "included_count": len(included),
        "excluded_count": len(excluded),
        "included_bytes": sum(int(item["size"]) for item in included),
        "excluded_sensitive": [item["path"] for item in excluded if item["reason"] == "sensitive"],
        "included": included,
        "excluded": excluded,
    }

    readme = "\n".join(
        [
            "Codex project package",
            f"Created at: {created_at}",
            f"Source: {source}",
            f"Included files: {len(included)}",
            f"Excluded files: {len(excluded)}",
            "",
            "Review note: sensitive files such as .env, keys, credentials, secrets, and tokens are excluded by default.",
            "",
        ]
    )

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for item in included:
            rel = str(item["path"])
            archive.write(source / rel, f"{top_name}/{rel}")
        archive.writestr(f"{top_name}/PACKAGE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr(f"{top_name}/PACKAGE_README.txt", readme)

    digest = sha256_file(output)
    with ZipFile(output, "r") as archive:
        bad_file = archive.testzip()
        entries = archive.namelist()
    if bad_file:
        raise SystemExit(f"ZIP verification failed at entry: {bad_file}")

    result = {
        "status": "ok",
        "zip": str(output),
        "sha256": digest,
        "size_bytes": output.stat().st_size,
        "entries": len(entries),
        "included_files": len(included),
        "excluded_files": len(excluded),
        "excluded_sensitive": manifest["excluded_sensitive"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
