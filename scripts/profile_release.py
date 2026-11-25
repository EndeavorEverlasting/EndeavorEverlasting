#!/usr/bin/env python3
"""Inspect, verify, capture and restore profile expression snapshots."""
import argparse
from difflib import unified_diff
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile

if __name__ == "__main__":
    sys.dont_write_bytecode = True

from verify_profile_scope import FOOTER_INVITATION, MEDIA_FILENAME, NEXUS_MEDIA
from verify_profile_scope import PROFILE_MEDIA, RELEASE_ID, readme_copy

ROOT = Path(__file__).resolve().parents[1]
CATALOG = "assets/profile-releases.json"
ARCHIVES = "assets/profile-releases"
REPO = "https://github.com/EndeavorEverlasting/EndeavorEverlasting"
CONTENT_PATH = re.compile(rf"assets/{MEDIA_FILENAME}")
REF = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
MEDIA_ATTR = re.compile(r'\b(?:src|srcset)="([^"]+)"')
SLOTS = ("top", "after_intro", "before_work", "bottom")
VERIFICATION_SCRIPTS = ("scripts/profile_release.py", "scripts/verify_profile_scope.py",
                        "scripts/verify_profile_visuals.py")
CLEAN_LIVE_CHECKOUT = "Live status needs a clean profile checkout. Run status for local state."


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
        elif not after or (not NEXUS_MEDIA.fullmatch(match.group())
                           and FOOTER_INVITATION.fullmatch(after)):
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



def next_release_id(versions):
    return f"v{max(int(name[1:]) for name in versions) + 1:02d}"


def current_version(root, base=None):
    data = catalog(root)
    verify_inventory(root, data["versions"])
    selected = data["active"]
    additions = set()
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
            require(not additions or additions == {selected["id"]},
                    "Publish one newly captured working expression at a time.")
            if additions:
                expected_id = next_release_id(original)
                require(additions == {expected_id}, f"Use the next version ID: {expected_id}.")
            if selected["archive"] and not additions and selected != baseline["active"]:
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
    if not selected["archive"] or additions:
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
            invitation = FOOTER_INVITATION.search(plain)
            if not invitation:
                plain = plain.rstrip("\n") + "\n\n" + rendered.rstrip("\n") + "\n"
                continue
            start = invitation.start()
        else:
            anchor = {"after_intro": "I care about what happens", "before_work": "### Selected work"}[slot]
            candidates = list(re.finditer(rf"(?m)^{re.escape(anchor)}", plain))
            require(len(candidates) == 1, f"Restore needs exactly one section beginning with {anchor!r}.")
            start = candidates[0].start()
        plain = plain[:start] + rendered + plain[start:]
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
    if data["active"] == {"id": name, "archive": True}:
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
    from verify_profile_visuals import check_artwork, check_motion_pixels, check_quality_floor, check_review

    data = catalog(root)
    next_name = next_release_id(data["versions"])
    require(name == next_name, f"Use the next version ID: {next_name}.")
    verify_inventory(root, data["versions"])
    for existing, entry in data["versions"].items():
        read_archive(root, existing, entry)
    require(title.strip(), "Provide a release title.")
    raw_readme = read_blob(root, "README.md")
    markup = raw_readme.decode("utf-8")
    checked_images(markup)
    nexus = bool(NEXUS_MEDIA.search(markup))
    artwork = {path: read_blob(root, path) for path in ASSETS}
    check_artwork(artwork, nexus=nexus)
    measurements = check_motion_pixels(artwork, nexus=nexus)
    require(nexus, "New profile artwork must preserve the V11 Nexus layout.")
    evaluation = check_quality_floor(root, artwork, measurements, capturing=True)
    check_review(json.loads(read_blob(root, ARTWORK_REVIEW)),
                 {**artwork, RENDERER: read_blob(root, RENDERER)})
    require(not git(root, "status", "--porcelain", "--", CATALOG), "Commit pending catalog edits before capturing.")
    data["versions"][name] = archive_entry(root, name, title.strip(), None, {"README.md": raw_readme, **artwork})
    data["versions"][name]["quality_evaluation"] = evaluation
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


def committed_catalog(root, commit):
    paths = git(root, "ls-tree", "--name-only", commit, "--", CATALOG).decode("utf-8").splitlines()
    return json.loads(git(root, "show", f"{commit}:{CATALOG}")) if CATALOG in paths else None


def profile_history(root):
    """Classify first-parent events since the immutable catalog was introduced."""
    commits = git(root, "log", "--first-parent", "--reverse", "--format=%H%x09%s",
                  "--", "README.md", CATALOG).decode("utf-8").splitlines()
    shallow = git(root, "rev-parse", "--is-shallow-repository").strip() == b"true"
    events = []
    previous_prose = previous_selection = editorial = baseline = None
    known_versions = set()
    registrations = {}
    for index, row in enumerate(commits):
        commit, subject = row.split("\t", 1)
        registry = committed_catalog(root, commit)
        if registry is None:
            continue
        prose = readme_copy(git(root, "show", f"{commit}:README.md").decode("utf-8"))
        selection = registry["active"]
        versions = set(registry["versions"])
        additions = versions - known_versions
        copy_changed = previous_prose is not None and prose != previous_prose
        selection_changed = selection != previous_selection
        previous_prose, previous_selection, known_versions = prose, selection, versions
        if shallow and index == 0:
            continue
        if baseline is None:
            baseline = commit
        if copy_changed:
            editorial = commit
        registrations.update(dict.fromkeys(additions, commit))
        if additions or copy_changed or selection_changed:
            events.append({"commit": commit, "subject": subject, "active": selection,
                           "registered": sorted(additions, key=lambda name: int(name[1:])),
                           "artwork_selection_changed": selection_changed, "editorial_changed": copy_changed})
    return events, editorial, baseline, registrations, shallow


def scene_files(blocks, files):
    return {slot: {path: sha256(files[path]).hexdigest()
                   for block in blocks[slot] for path in MEDIA_ATTR.findall(block)}
            for slot in SLOTS}


def invitation_medium(readme):
    if NEXUS_MEDIA.search(readme):
        return "artwork"
    return "text" if FOOTER_INVITATION.search(readme) else None


def compare_artwork(root, data, current, target, readme, checkout_layout):
    require(target in data["versions"], f"Unknown release {target!r}. Run the list command.")
    current_blocks, current_files = read_archive(root, current, data["versions"][current])
    target_blocks, target_files = read_archive(root, target, data["versions"][target])
    before, after = scene_files(current_blocks, current_files), scene_files(target_blocks, target_files)
    scenes = {}
    for slot in SLOTS:
        original, replacement = before[slot], after[slot]
        placement_changed = current_blocks[slot] != target_blocks[slot]
        if original != replacement or placement_changed:
            scenes[slot] = {
                "added": sorted(replacement.keys() - original.keys()),
                "removed": sorted(original.keys() - replacement.keys()),
                "changed": sorted(path for path in original.keys() & replacement.keys()
                                  if original[path] != replacement[path]),
                "markup_changed": placement_changed,
            }
    target_layout = archive_layout(target_blocks, target)
    url_changes = [slot for slot in SLOTS
                   if MEDIA_ATTR.findall("\n".join(checkout_layout[slot])) !=
                      MEDIA_ATTR.findall("\n".join(target_layout[slot]))]
    blocker = None
    invitation_change = None
    try:
        restored = insert_layout(readme, target_layout)
    except ValueError as error:
        blocker = str(error)
    else:
        current_invitation = invitation_medium(readme)
        restored_invitation = invitation_medium(restored)
        if current_invitation != restored_invitation:
            invitation_change = {"from": current_invitation, "to": restored_invitation}
    return {"from": current, "to": target, "changed_scenes": scenes,
            "media_url_scenes": url_changes, "invitation_change": invitation_change,
            "restore_blocker": blocker,
            "preview_command": f"python scripts/profile_release.py restore {target}"}


def github_default_head(root):
    provider = subprocess.run(["git", "ls-remote", "--symref", f"{REPO}.git", "HEAD"],
                              cwd=root, capture_output=True, text=True, timeout=20)
    require(provider.returncode == 0, f"Cannot read GitHub default HEAD: {provider.stderr.strip()}")
    return next((line.split()[0] for line in provider.stdout.splitlines()
                 if re.fullmatch(r"[0-9a-f]{40}\tHEAD", line)), None)


def verify_live_checkout(root, head, pending):
    require(not pending, CLEAN_LIVE_CHECKOUT)
    from verify_profile_visuals import PROFILE

    require(github_default_head(root) == head,
            "Checkout does not match GitHub's current default HEAD. Fetch and check out that commit.")
    check = subprocess.run([sys.executable, "-B", str(root / "scripts/verify_profile_visuals.py"), "--live"],
                           cwd=root, capture_output=True, text=True, timeout=90)
    require(check.returncode == 0, (check.stderr or check.stdout).strip())
    require(github_default_head(root) == head, "GitHub default HEAD changed during verification. Fetch and retry.")
    return {"url": PROFILE, "default_commit": head, "artwork_and_invitation_verified": True}


def canonical_origin(root):
    """Use only a recognized GitHub origin when linking fetched archive bytes."""
    urls = {line.split()[1].lower().removesuffix(".git")
            for line in git(root, "remote", "-v").decode("utf-8").splitlines()
            if line.startswith("origin\t") and line.endswith("(fetch)")}
    slug = REPO.removeprefix("https://github.com/").lower()
    return bool(urls) and urls <= {REPO.lower(), f"git@github.com:{slug}",
                                  f"ssh://git@github.com/{slug}"}


def profile_status(root, *, compare=None, live=False):
    """Report checkout artwork and copy, with optional comparison or live proof."""
    scripts_pending = bool(git(root, "status", "--porcelain", "--", *VERIFICATION_SCRIPTS))
    if live:
        require(not scripts_pending, CLEAN_LIVE_CHECKOUT)
    selected, checkout_layout, _ = current_version(root)
    data = catalog(root)
    events, editorial, baseline, registrations, shallow = profile_history(root)
    head = git(root, "rev-parse", "HEAD").decode("utf-8").strip()
    branch = git(root, "branch", "--show-current").decode("utf-8").strip()
    tracking = git(root, "for-each-ref", "--format=%(symref)", "refs/remotes/origin/HEAD").decode("utf-8").strip()
    tracked_head = git(root, "rev-parse", tracking).decode("utf-8").strip() if tracking else None
    pending = scripts_pending or bool(git(
        root, "status", "--porcelain", "--", "README.md", CATALOG, ARCHIVES,
        *[path for path in data["versions"][selected["id"]]["files"] if path != "README.md"]))
    remote = committed_catalog(root, tracked_head) if tracked_head else None
    canonical = canonical_origin(root)
    registered_remote = remote["versions"] if remote and canonical else {}
    versions = {}
    for name, entry in data["versions"].items():
        path = archive_prefix(name)
        published_path = f"{REPO}/tree/{tracked_head}/{path}" if registered_remote.get(name) == entry else None
        versions[name] = {"title": entry["title"], "original_commit": entry["source_commit"],
                          "registered_commit": registrations.get(name),
                          "archive_path": path, "archive_url": published_path}
    blocks, files = read_archive(root, selected["id"], data["versions"][selected["id"]])
    readme = read_blob(root, "README.md").decode("utf-8")
    invitation = invitation_medium(readme)
    result = {
        "schema": 1,
        "checkout": {"commit": head, "branch": branch or None, "profile_changes_pending": pending},
        "last_fetched_default": {"ref": tracking or None, "commit": tracked_head,
                                 "artwork": remote["active"] if remote else None, "canonical_origin": canonical},
        "artwork": {**selected, **versions[selected["id"]], "scenes": scene_files(blocks, files)},
        "editorial": {"last_commit": editorial, "registry_baseline": baseline,
                      "invitation_present": invitation is not None,
                      "invitation_medium": invitation},
        "versions": versions, "next_artwork_version": next_release_id(versions),
        "history": events, "history_is_shallow": shallow,
    }
    if compare:
        result["comparison"] = compare_artwork(root, data, selected["id"], compare, readme, checkout_layout)
    if live:
        result["live"] = verify_live_checkout(root, head, pending)
    return result


def format_status(data, history):
    artwork, checkout, editorial = (data[key] for key in ("artwork", "checkout", "editorial"))
    dirty = " (pending profile edits)" if checkout["profile_changes_pending"] else ""
    origin = data["last_fetched_default"]
    copy_revision = editorial["last_commit"] or (
        f"{editorial['registry_baseline']} (registry baseline)" if editorial["registry_baseline"] else "unknown")
    remote_art = f" (artwork {origin['artwork']['id']})" if origin["artwork"] else ""
    lines = [
        f"Checkout {checkout['branch'] or 'detached HEAD'} at {checkout['commit']}{dirty}",
        (f"Last fetched origin default {origin['ref'] or 'unknown'} {origin['commit'] or ''}" + remote_art).rstrip(),
        f"Artwork {artwork['id']} — {artwork['title']} ({'archive URLs' if artwork['archive'] else 'working URLs'})",
        f"Original artwork commit {artwork['original_commit'] or 'unknown'}",
        f"Archive registered in {artwork['registered_commit'] or 'unknown'} | "
        f"{artwork['archive_url'] or artwork['archive_path']}",
        f"Editorial revision {copy_revision} | "
        f"repository invitation {editorial['invitation_medium'] or 'absent'}",
    ]
    for slot, paths in artwork["scenes"].items():
        lines.append(f"  {slot}: {', '.join(Path(path).name for path in paths) or 'none'}")
    lines.append(f"{len(data['versions'])} snapshots | next artwork ID {data['next_artwork_version']}.")
    lines.append("Run list to browse all versions.")
    if data["history_is_shallow"]:
        lines.append("Shallow history. Older provenance may be unavailable.")
    if "live" in data:
        lines.append(f"Live artwork and invitation verified against GitHub default HEAD. {data['live']['url']}")
    if comparison := data.get("comparison"):
        lines.append(f"Compare {comparison['from']} → {comparison['to']}")
        for slot, changes in comparison["changed_scenes"].items():
            parts = [f"{operation} {', '.join(Path(path).name for path in changes[operation])}"
                     for operation in ("added", "removed", "changed") if changes[operation]]
            if changes["markup_changed"]:
                parts.append("scene markup changes")
            lines.append(f"  {slot}: {' | '.join(parts)}")
        if not comparison["changed_scenes"]:
            lines.append("  Artwork bytes and scene markup match.")
        if comparison["media_url_scenes"]:
            lines.append("  Media URLs would change in " + ", ".join(comparison["media_url_scenes"]))
        if comparison["restore_blocker"]:
            lines.append(f"Restore blocked: {comparison['restore_blocker']}")
        else:
            if change := comparison["invitation_change"]:
                before, after = change["from"] or "none", change["to"] or "none"
                lines.append(f"  Repository invitation would change from {before} to {after}.")
            lines.append("Artwork restore preserves current editorial copy.")
            lines.append(comparison["preview_command"])
    if history:
        lines.append("Committed profile history (newest first)")
        for event in reversed(data["history"]):
            changes = []
            if event["registered"]:
                changes.append("registered " + ", ".join(event["registered"]))
            if event["artwork_selection_changed"] and event["active"]:
                selection = event["active"]
                changes.append(f"selected {selection['id']} ({'archive' if selection['archive'] else 'working'})")
            if event["editorial_changed"]:
                changes.append("editorial")
            lines.append(f"  {event['commit'][:7]} | {', '.join(changes)} | {event['subject']}")
    return "\n".join(lines)


def validate_revision_geometry(g):
    import math
    PHI = (1 + math.sqrt(5)) / 2
    TOL = 1e-6
    if not isinstance(g, dict):
        return ["Missing geometry evidence"]
    errors = []
    radii = g.get("quarter_turn_radii", [])
    if not isinstance(radii, list) or len(radii) < 4 or any(type(r) not in (float, int) or not math.isfinite(r) or r <= 0 for r in radii):
        errors.append("Need at least four finite positive measured quarter-turn radii")
    elif any(abs(b/a - 1/PHI) > TOL for a, b in zip(radii, radii[1:])):
        errors.append("Inward quarter-turn ratio is not 1/phi")
    def vec(key):
        v = g.get(key, [])
        if not isinstance(v, list) or len(v) != 2 or any(type(x) not in (float, int) or not math.isfinite(x) for x in v):
            raise ValueError(key)
        return v
    try:
        a, b = vec("rim_end"), vec("spiral_start")
        if math.dist(a, b) > TOL:
            errors.append("Rim-to-spiral join is disconnected")
        a, b = vec("rim_end_tangent"), vec("spiral_start_tangent")
        if min(math.hypot(*a), math.hypot(*b)) <= TOL:
            errors.append("Join tangents must be nonzero")
        elif math.dist(a, b) > TOL * max(1, math.hypot(*a), math.hypot(*b)):
            errors.append("Join derivatives differ: not C1 in declared parameterization")
    except (ValueError, TypeError):
        errors.append("Missing or malformed join evidence")
    return errors


def verify_revision(packet_path, *, authority_path, review=False):
    """Validate a private revision packet; never infer visual approval from a receipt."""
    from PIL import Image, ImageChops

    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    require(isinstance(packet, dict) and packet.get("schema_version") == 1,
            "Unsupported profile revision packet.")

    require(authority_path.resolve() != packet_path.resolve(),
            "Revision authority must be a separate private source.")
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    require(isinstance(authority, dict) and authority.get("schema_version") == 1,
            "Unsupported revision authority.")
    # The authority is recovered independently of the candidate from the private
    # operator-approved source; this checks equality, not the approval itself.
    fields = ("baseline", "requested_delta", "rejected_variants", "required_outputs",
              "preservation_mode", "geometry_required", "native_output")
    require(all(key in authority and key in packet and authority[key] == packet[key]
                for key in fields), "Revision packet contradicts private authority.")
    require(type(authority["geometry_required"]) is bool,
            "Geometry requirement must be explicit.")
    require(isinstance(packet.get("source"), dict)
            and packet["source"].get("sha256") == authority.get("source_sha256"),
            "Source differs from private authority.")

    def asset(record):
        require(isinstance(record, dict) and isinstance(record.get("path"), str)
                and isinstance(record.get("sha256"), str) and DIGEST.fullmatch(record["sha256"]),
                "Every asset needs a path and SHA-256.")
        path = (packet_path.parent / record["path"]).resolve(strict=True)
        require(path.is_file() and sha256(path.read_bytes()).hexdigest() == record["sha256"],
                "Asset is missing or its hash differs.")
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            require(getattr(image, "n_frames", 1) == 1, "Expected a static image.")
            image.load()
        return path

    source = asset(packet.get("source"))
    require(packet.get("source_inspected") is True, "Inspect the actual source first.")
    baseline, delta, proposed = (packet.get(k) for k in ("baseline", "requested_delta", "proposed"))
    require(all(isinstance(x, dict) and x for x in (baseline, delta, proposed)),
            "Provide the complete baseline, explicit delta and resolved proposed attributes.")
    require(delta.keys() <= baseline.keys() and proposed == baseline | delta,
            "Requested delta is unmapped, or protected attributes have drifted.")
    rejected = packet.get("rejected_variants")
    require(isinstance(rejected, list) and all(isinstance(x, str) and x.strip() for x in rejected),
            "Record rejected variants or an explicit empty list.")
    targets = packet.get("required_outputs")
    require(isinstance(targets, dict) and targets and all(
        isinstance(k, str) and k and isinstance(v, list) and len(v) == 2
        and all(type(n) is int and n > 0 for n in v) for k, v in targets.items()),
        "Declare independent output names and exact dimensions.")
    mode = packet.get("preservation_mode")
    require(mode in ("semantic", "pixel_lock"), "Declare the preservation mode explicitly.")
    if mode == "pixel_lock":
        require(isinstance(packet.get("approved_mask"), dict)
                and isinstance(authority.get("mask_sha256"), str)
                and packet["approved_mask"].get("sha256") == authority["mask_sha256"],
                "Protected mask is not independently pinned.")
        require(packet["native_output"] in targets, "Declare the protected native export name.")
        mask = asset(packet.get("approved_mask"))
        require(packet.get("mask_approved") is True, "Pixel lock requires an independently approved mask.")
        with Image.open(source) as original, Image.open(mask) as protected:
            require(protected.mode == "L" and protected.size == original.size
                    and protected.getbbox() and not (set(protected.getdata()) - {0, 255}),
                    "Protected mask must be nonempty binary grayscale in native coordinates.")
    else:
        require(packet["native_output"] is None, "Semantic mode cannot claim pixel-locked exports.")
    if not review:
        return
    if packet.get("geometry_required") is True:
        errors = validate_revision_geometry(packet.get("geometry_receipt"))
        require(not errors, "; ".join(errors))
    checks = packet.get("attribute_review")
    require(isinstance(checks, dict) and checks.keys() == baseline.keys() and all(
        isinstance(v, dict) and v.get("status") == "PASS" and isinstance(v.get("evidence"), str)
        and v["evidence"].strip() for v in checks.values()),
        "Review every retained and changed attribute with evidence.")
    outputs = packet.get("outputs")
    require(isinstance(outputs, dict) and outputs.keys() == targets.keys(),
            "Missing or unexpected output files.")
    seen = {source}
    for name, record in outputs.items():
        path = asset(record)
        require(path not in seen, "Output paths must be distinct from each other and the source.")
        seen.add(path)
        with Image.open(path) as image:
            require(list(image.size) == targets[name], f"Incorrect dimensions: {name}.")
    if mode == "pixel_lock":
        native = asset(packet.get("native_candidate"))
        with Image.open(source) as original, Image.open(mask) as protected, Image.open(native) as candidate:
            require(candidate.size == original.size, "Native candidate dimensions changed.")
            diff = ImageChops.difference(original.convert("RGBA"), candidate.convert("RGBA"))
            require(not any(ImageChops.multiply(channel, protected).getbbox() for channel in diff.split()),
                    "Protected native pixels changed.")
            output = asset(outputs[packet["native_output"]])
            with Image.open(output) as exported:
                expected = candidate.convert("RGBA").resize(exported.size, Image.Resampling.LANCZOS)
                difference = ImageChops.difference(expected, exported.convert("RGBA"))
                require(not any(channel.getbbox() for channel in difference.split()),
                        "Protected export is not derived from the validated native candidate.")


def verify_checkout(root, base):
    """Run release checks against one committed checkout."""
    head = git(root, "rev-parse", "HEAD").decode().strip()
    require(not git(root, "status", "--porcelain"), "Release verification needs a clean checkout.")
    env = os.environ.copy()
    if base is not None:
        require(REF.fullmatch(base), "Use a full base commit SHA.")
        scope = git(root, "show", f"{base}:scripts/verify_profile_scope.py")
        subprocess.run([sys.executable, "-B", "-", "--range", base, head],
                       cwd=root, input=scope, check=True)
        env["PROFILE_RELEASE_BASE"] = base
    else:
        env.pop("PROFILE_RELEASE_BASE", None)
    for command in (["scripts/verify_profile_banner.py"], ["scripts/verify_profile_visuals.py"],
                    ["-m", "unittest", "discover", "-s", "scripts", "-v"]):
        subprocess.run([sys.executable, "-B", *command], cwd=root, env=env, check=True)
    require(git(root, "rev-parse", "HEAD").decode().strip() == head and
            not git(root, "status", "--porcelain"), "Checkout changed during release verification.")
    print(f"PASS profile release checks for {head}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("list")
    status = sub.add_parser("status", help="Show profile state and provenance without changing files.")
    status.add_argument("--compare", metavar="VERSION", help="Show scene changes from a possible restore.")
    status.add_argument("--history", action="store_true", help="Show committed profile history.")
    status.add_argument("--json", action="store_true", help="Emit machine-readable status and history.")
    status.add_argument("--live", action="store_true", help="Check GitHub default HEAD and rendered artwork/invitation.")
    check = sub.add_parser("check")
    check.add_argument("--base")
    verify = sub.add_parser("verify", help="Run the full checkout verification used by Actions on main.")
    verify.add_argument("--base", help="Full SHA for the prior scope and release rules.")
    recover = sub.add_parser("restore")
    recover.add_argument("version")
    recover.add_argument("--apply", action="store_true")
    revision = sub.add_parser("revision", help="Validate a private profile revision packet.")
    revision.add_argument("packet", type=Path)
    revision.add_argument("--authority", type=Path, required=True)
    revision.add_argument("--review", action="store_true")
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
        elif args.operation == "status":
            result = profile_status(ROOT, compare=args.compare, live=args.live)
            print(encode(result).decode("utf-8").rstrip() if args.json else format_status(result, args.history))
        elif args.operation == "check":
            selected, _, _ = current_version(ROOT, args.base)
            print(f"PASS: verified profile versions and active expression {selected['id']}")
        elif args.operation == "verify":
            verify_checkout(ROOT, args.base)
        elif args.operation == "revision":
            verify_revision(args.packet, authority_path=args.authority, review=args.review)
            print("PASS: revision packet checks; visual approval remains independent.")
        elif args.operation == "restore":
            print(restore(ROOT, args.version, args.apply))
        else:
            print(capture(ROOT, args.version, args.title))
    except subprocess.CalledProcessError as error:
        parser.exit(error.returncode if error.returncode > 0 else 1, "FAIL: Profile release checks stopped.\n")
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
