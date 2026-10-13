#!/usr/bin/env python3
"""Build an auditable source ZIP from a Git commit, never from working files.

This verification package contains exactly the tracked files in the selected
commit. The release_download URL names this exact ZIP; canonical_download is
GitHub's alternate commit archive, whose container bytes can differ while the
repository paths and file bytes remain identical.
"""

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def forbidden(path):
    parts = PurePosixPath(path).parts
    if path == "webapp/projects/.gitkeep":
        return False
    return (path.startswith(("webapp/projects/", "webapp/library/", "out/"))
            or any(p in {".git", "node_modules", "__pycache__", ".venv", "venv",
                         ".pytest_cache", ".ruff_cache", ".report-gen-browser-id",
                         ".report-gen-backup-routine.json", ".report-gen-owner"}
                   or p.startswith(".write-") or p.endswith(".egg-info") for p in parts))


def build_release(repo, ref, output):
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()
    tree = git(repo, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    version_source = git(repo, "show", f"{commit}:version.py").decode("utf-8")
    version = None
    for node in ast.parse(version_source).body:
        if isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and n.id == "__version__" for n in node.targets):
            version = ast.literal_eval(node.value)
    if not isinstance(version, str) or not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]*", version):
        raise ValueError("version.py has no safe literal __version__")
    files = []
    for entry in git(repo, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        header, path_raw = entry.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        path = path_raw.decode("utf-8")
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError(f"Unsupported source entry (symlink/submodule): {path}")
        if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or "\\" in path:
            raise ValueError(f"Unsafe repository path: {path}")
        if forbidden(path):
            raise ValueError(f"User data or generated files are tracked; remove them before packaging: {path}")
        files.append((path, mode, oid))
    output.mkdir(parents=True, exist_ok=True)
    stem = f"report-gen-{version}-{commit[:12]}"
    archive = output / f"{stem}.zip"
    manifest = []
    # ZIP_STORED deliberately avoids compressor/library differences. All ZIP
    # timestamps, platform attributes, permissions and ordering are explicit.
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as package:
        for path, mode, oid in sorted(files):
            data = git(repo, "cat-file", "blob", oid)
            item = zipfile.ZipInfo(f"{stem}/{path}", date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (int(mode, 8) << 16)
            item.compress_type = zipfile.ZIP_STORED
            package.writestr(item, data)
            manifest.append({"path": path, "mode": mode, "size": len(data),
                             "sha256": hashlib.sha256(data).hexdigest()})
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    metadata = {"schema": 1, "version": version, "commit": commit, "tree": tree,
                "canonical_download": f"https://github.com/IphobiusS/report-gen/archive/{commit}.zip",
                "release_download": f"https://github.com/IphobiusS/report-gen/releases/download/v{version}/{archive.name}",
                "archive": archive.name, "sha256": digest, "files": manifest}
    checksums = f"{digest}  {archive.name}\n"
    if any(path.startswith('integrations/libreoffice/extension/') for path, _, _ in files):
        # Packaging code is local and trusted; payload bytes come exclusively
        # from the selected Git tree. Never execute a script from the ref or
        # include an untracked/modified extension payload from the workspace.
        builder_path = Path(__file__).resolve().parents[1] / 'integrations/libreoffice/build_oxt.py'
        spec = importlib.util.spec_from_file_location('release_oxt_builder', builder_path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        objects = {path: oid for path, _, oid in files}
        missing = set(builder.PAYLOAD_PATHS.values()) - objects.keys()
        if missing:
            raise ValueError('Incomplete LibreOffice extension payload: ' + ', '.join(sorted(missing)))
        payload = {name: git(repo, 'cat-file', 'blob', objects[path])
                   for name, path in builder.PAYLOAD_PATHS.items()}
        extension = builder.build_oxt(output / f'report-gen-libreoffice-{version}.oxt', payload)
        extension_digest = hashlib.sha256(extension.read_bytes()).hexdigest()
        metadata['libreoffice_extension'] = {
            'archive': extension.name, 'sha256': extension_digest,
            'release_download': f'https://github.com/IphobiusS/report-gen/releases/download/v{version}/{extension.name}',
            'source_paths': builder.PAYLOAD_PATHS,
            'installation': 'optional_explicit_libreoffice_extension',
        }
        checksums += f'{extension_digest}  {extension.name}\n'
    (output / f"{stem}.sha256").write_text(checksums, encoding="utf-8")
    (output / f"{stem}.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="Existing commit or tag (default: HEAD)")
    parser.add_argument("--output", type=Path, default=Path("out/release"))
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    try:
        metadata = build_release(repo, args.ref, args.output)
    except (subprocess.CalledProcessError, ValueError, OSError) as exc:
        parser.exit(1, f"Source package failed: {exc}\n")
    print(json.dumps({k: v for k, v in metadata.items() if k != "files"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
