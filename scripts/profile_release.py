#!/usr/bin/env python3
"""List, verify, capture and restore profile expression snapshots."""
import argparse
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import NamedTemporaryFile

from verify_profile_scope import MEDIA_FILENAME, PROFILE_MEDIA, RELEASE_ID

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "assets/profile-releases.json"
ARCHIVES = "assets/profile-releases"
REPO = "https://github.com/EndeavorEverlasting/EndeavorEverlasting"
CONTENT_PATH = re.compile(rf"assets/{MEDIA_FILENAME}")
REF = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
MEDIA_ATTR = re.compile(r'\b(?:src|srcset)="([^"]+)"')
SLOTS = ("top", "after_intro", "before_work", "bottom")


class ReleaseError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ReleaseError(message)


def git(root, *args, input=None):
    process = subprocess.run(["git", *args], cwd=root, input=input, capture_output=True)
    if process.returncode:
        raise ReleaseError(process.stderr.decode("utf-8", "replace").strip() or "Git command failed.")
    return process.stdout


def encode(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def read_blob(root, path):
    target = root / path
    require(target.is_file() and target.resolve().is_relative_to(root.resolve())
            and target.resolve() == root.resolve() / path, f"Missing or relocated file: {path}")
    return target.read_bytes()


def catalog(root):
    data = json.loads(read_blob(root, CATALOG))
    require(isinstance(data, dict) and data.get("schema") == 1, "Unrecognized profile release catalog.")
    versions = data.get("versions")
    active = data.get("active")
    require(isinstance(versions, dict) and versions and isinstance(active, dict) and
            isinstance(active.get("id"), str) and active["id"] in versions and
            type(active.get("archive")) is bool, "Choose a known active profile release.")
    for name, entry in versions.items():
        require(re.fullmatch(RELEASE_ID, name) and isinstance(entry, dict), f"Invalid release: {name}")
        title = entry.get("title")
        source = entry.get("source_commit")
        files = entry.get("files")
        require(isinstance(title, str) and title.strip(), f"Missing title for {name}.")
        require(source is None or isinstance(source, str) and REF.fullmatch(source),
                f"Invalid source commit for {name}.")
        require(isinstance(files, dict) and "README.md" in files and len(files) > 1 and
                all((path == "README.md" or CONTENT_PATH.fullmatch(path)) and
                    isinstance(digest, str) and DIGEST.fullmatch(digest)
                    for path, digest in files.items()), f"Invalid archive file list for {name}.")
    return data


def layout(text):
    """Read the supported, visibly separate media blocks in presentation order."""
    from verify_profile_visuals import ProfileImages, require as check

    blocks = {slot: [] for slot in SLOTS}
    for match in PROFILE_MEDIA.finditer(text):
        before = PROFILE_MEDIA.sub("", text[:match.start()])
        after = PROFILE_MEDIA.sub("", text[match.end():]).lstrip()
        before = re.sub(r"\A(?:\s*<!--[^\n]*-->)*\s*", "", before)
        if not before:
            slot = "top"
        elif after.startswith("I care about what happens"):
            slot = "after_intro"
        elif after.startswith("### Selected work"):
            slot = "before_work"
        elif not after:
            slot = "bottom"
        else:
            raise ReleaseError("A profile image is outside the supported layout positions.")
        blocks[slot].append(match.group().rstrip())
    flat = [block for group in blocks.values() for block in group]
    media = ProfileImages(text, False)
    check(flat and len(media.images) == len(flat), "Use one image per visible profile media block.")
    require(all(len(MEDIA_ATTR.findall(block)) in (1, 2) for block in flat), "Invalid media URLs.")
    return blocks


def archive_prefix(name):
    return f"{ARCHIVES}/{name}"


def read_archive(root, name, entry):
    prefix = archive_prefix(name)
    files = {}
    for path, digest in entry["files"].items():
        content = read_blob(root, f"{prefix}/{path}")
        require(sha256(content).hexdigest() == digest, f"Archive checksum mismatch: {name}/{path}")
        files[path] = content
    blocks = layout(files["README.md"].decode("utf-8"))
    media_paths = {path for group in blocks.values() for block in group
                   for path in MEDIA_ATTR.findall(block)}
    require(media_paths == set(files) - {"README.md"}, f"Archive media mismatch: {name}")
    return blocks, files


def archive_layout(blocks, name):
    prefix = archive_prefix(name)
    return {slot: [re.sub(r'\b(src|srcset)="(assets/[^"]+)"',
                          lambda m: f'{m[1]}="{prefix}/{m[2]}"', block)
                   for block in group] for slot, group in blocks.items()}


def verify_inventory(root, versions):
    expected = {f"{archive_prefix(name)}/{path}" for name, entry in versions.items() for path in entry["files"]}
    observed = {path.relative_to(root).as_posix() for path in (root / ARCHIVES).rglob("*")
                if path.is_symlink() or not path.is_dir()}
    require(observed == expected, "Archive inventory differs from the release catalog.")


def current_version(root, base=None):
    data = catalog(root)
    verify_inventory(root, data["versions"])
    selected = data["active"]
    if base:
        require(REF.fullmatch(base), "Use a full base commit SHA.")
        git(root, "cat-file", "-e", f"{base}^{{commit}}")
        owner = git(root, "ls-tree", "--name-only", base, "--", CATALOG)
        if owner:
            baseline = json.loads(git(root, "show", f"{base}:{CATALOG}"))
            original = baseline["versions"]
            require(all(data["versions"].get(name) == entry for name, entry in original.items()),
                    "Existing profile versions are immutable. Capture a new version.")
            additions = set(data["versions"]) - set(original)
            require(not additions or (not selected["archive"] and additions == {selected["id"]}),
                    "Publish one newly captured working expression at a time.")
            if selected["archive"] and selected != baseline["active"]:
                paths = set(git(root, "diff", "--name-only", "--no-renames", "-z", base, "--")
                            .decode("utf-8").split("\0")) - {""}
                require(paths <= {"README.md", CATALOG},
                        "A rollback may only change README media and the active version.")
    # Verify every archive, including inactive versions, before trusting the catalog.
    for name, entry in data["versions"].items():
        blocks, files = read_archive(root, name, entry)
        if name == selected["id"]:
            expected = archive_layout(blocks, name) if selected["archive"] else blocks
            active_files = files
    readme = read_blob(root, "README.md").decode("utf-8")
    require(layout(readme) == expected, "Published media and layout must match the active version.")
    if not selected["archive"]:
        for path, content in active_files.items():
            if path != "README.md":
                require(read_blob(root, path) == content, f"Capture the changed artwork before publishing: {path}")
    return selected, expected, active_files


def insert_layout(current, blocks):
    # Remove only owned media blocks and one neighboring blank line per block.
    strip_media = re.compile(PROFILE_MEDIA.pattern.replace("(?m)", rf"(?m)(?:") + r")(?:\n[ \t]*\n)?")
    plain = strip_media.sub("", current)
    for slot in SLOTS:
        group = blocks[slot]
        if not group:
            continue
        rendered = "\n\n".join(group) + "\n\n"
        if slot == "top":
            start = re.match(r"\A(?:[ \t]*<!--[^\n]*-->[ \t]*\n)?\n*", plain).end()
        elif slot == "bottom":
            plain = plain.rstrip("\n") + "\n\n" + rendered.rstrip("\n") + "\n"
            continue
        else:
            anchor = {"after_intro": "I care about what happens", "before_work": "### Selected work"}[slot]
            candidates = list(re.finditer(rf"(?m)^{re.escape(anchor)}", plain))
            require(len(candidates) == 1, f"Restore needs exactly one section beginning with {anchor!r}.")
            start = candidates[0].start()
        plain = plain[:start] + rendered + plain[start:]
    from verify_profile_scope import readme_copy
    require(readme_copy(current) == readme_copy(plain), "Restore changed profile prose.")
    require(layout(plain) == blocks, "Could not place the selected version.")
    return plain


def restore(root, name, apply):
    if apply:
        require(not git(root, "status", "--porcelain", "--", "README.md", CATALOG),
                "Commit or stash pending README and catalog edits before restoring.")
    data = catalog(root)
    require(name in data["versions"], f"Unknown version {name!r}. Run the list command.")
    current_version(root)
    if data["active"]["id"] == name:
        return "This profile version is already selected."
    blocks, _ = read_archive(root, name, data["versions"][name])
    readme = read_blob(root, "README.md").decode("utf-8")
    recovered = insert_layout(readme, archive_layout(blocks, name))
    old_catalog = read_blob(root, CATALOG).decode("utf-8")
    data["active"] = {"id": name, "archive": True}
    new_catalog = encode(data).decode("utf-8")
    patch = "".join(line for path, old, new in (
        ("README.md", readme, recovered), (CATALOG, old_catalog, new_catalog))
        for line in unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                 f"a/{path}", f"b/{path}"))
    if apply:
        git(root, "apply", "--check", "-", input=patch.encode("utf-8"))
        git(root, "apply", "-", input=patch.encode("utf-8"))
        current_version(root)
        return f"Selected {name} in the checkout. Review the diff, then commit and use your normal PR."
    return patch


def archive_entry(root, name, title, source_commit, files):
    """Write the exact expression once and return its immutable catalog entry."""
    destination = root / archive_prefix(name)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for path, data in files.items():
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    except OSError:
        shutil.rmtree(destination)
        raise
    return {"title": title, "source_commit": source_commit,
            "files": {path: sha256(content).hexdigest() for path, content in sorted(files.items())}}


def capture(root, name, title):
    from verify_profile_visuals import ASSETS, ARTWORK_REVIEW, RENDERER, checked_images
    from verify_profile_visuals import check_artwork, check_motion_pixels, check_review

    data = catalog(root)
    next_name = f"v{max(int(key[1:]) for key in data['versions']) + 1:02d}"
    require(name == next_name, f"Use the next version ID: {next_name}.")
    verify_inventory(root, data["versions"])
    for existing, entry in data["versions"].items():
        read_archive(root, existing, entry)
    require(title.strip(), "Provide a release title.")
    raw_readme = read_blob(root, "README.md")
    checked_images(raw_readme.decode("utf-8"))
    artwork = {path: read_blob(root, path) for path in ASSETS}
    check_artwork(artwork)
    check_motion_pixels(artwork)
    check_review(json.loads(read_blob(root, ARTWORK_REVIEW)),
                 {**artwork, RENDERER: read_blob(root, RENDERER)})
    require(not git(root, "status", "--porcelain", "--", CATALOG), "Commit pending catalog edits before capturing.")
    data["versions"][name] = archive_entry(root, name, title.strip(), None, {"README.md": raw_readme, **artwork})
    data["active"] = {"id": name, "archive": False}
    temp = None
    try:
        with NamedTemporaryFile(dir=root / "assets", prefix=".profile-releases-", delete=False) as handle:
            temp = Path(handle.name)
            handle.write(encode(data))
        temp.chmod(0o644)
        temp.replace(root / CATALOG)
    except OSError:
        shutil.rmtree(root / archive_prefix(name))
        raise
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return f"Captured and selected {name}. Commit the catalog, snapshot and approved artwork together."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("list")
    check = sub.add_parser("check")
    check.add_argument("--base")
    recover = sub.add_parser("restore")
    recover.add_argument("version")
    recover.add_argument("--apply", action="store_true")
    record = sub.add_parser("capture")
    record.add_argument("version")
    record.add_argument("--title", required=True)
    args = parser.parse_args()
    try:
        if args.operation == "list":
            data = catalog(ROOT)
            for name, entry in data["versions"].items():
                state = " (active)" if name == data["active"]["id"] else ""
                print(f"{name}{state}  {entry['title']}  {REPO}/tree/main/{archive_prefix(name)}")
        elif args.operation == "check":
            selected, _, _ = current_version(ROOT, args.base)
            print(f"PASS: verified profile versions and active expression {selected['id']}")
        elif args.operation == "restore":
            print(restore(ROOT, args.version, args.apply))
        else:
            print(capture(ROOT, args.version, args.title))
    except (ValueError, OSError) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
