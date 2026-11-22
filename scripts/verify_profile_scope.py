#!/usr/bin/env python3
"""Reject out-of-scope files and mixed artwork/editorial changes."""
import argparse
import re
import subprocess

PROFILE_ART = {
    "assets/hero.svg", "assets/profile-artwork.md", "assets/profile-artwork-review.json",
    "assets/stitch-descent.gif", "assets/stitch-descent.png",
    "assets/stitch-resume.gif", "assets/stitch-resume.png",
    "assets/stitch-pulse.gif", "assets/stitch-pulse.png",
    "scripts/render_profile_motion.py", "scripts/verify_profile_banner.py",
    "scripts/verify_profile_visuals.py", "scripts/test_profile_visuals.py",
}
RELEASE_TOOLS = {
    ".githooks/pre-commit", ".github/workflows/profile-banner.yml",
    "scripts/verify_profile_scope.py", "scripts/test_profile_scope.py",
}
PROFILE_ART.add("assets/profile-releases.json")
RELEASE_TOOLS.update({"scripts/profile_release.py", "scripts/test_profile_releases.py"})
PROFILE_FILES = PROFILE_ART | RELEASE_TOOLS | {"README.md", "AGENTS.md"}
MEDIA_FILENAME = r"(?:hero\.svg|first-stitch\.gif|stitch-(?:opening|continuation|descent|resume|pulse)\.(?:gif|png))"
RELEASE_ID = r"v[0-9]{2,}"
ARCHIVE_PATH = re.compile(rf"assets/profile-releases/{RELEASE_ID}/(?:README\.md|assets/{MEDIA_FILENAME})")
MEDIA_PREFIX = rf"assets/(?:profile-releases/{RELEASE_ID}/assets/)?"
PROFILE_MEDIA = re.compile(
    rf'(?m)^<picture>[ \t]*\n[ \t]*<source\b[^>\n]*>\n[ \t]*'
    rf'<img\s+src="{MEDIA_PREFIX}{MEDIA_FILENAME}"[^>\n]*>\n</picture>[ \t]*$'
    rf'|^<p align="center">[ \t]*\n[ \t]*'
    rf'<img\s+src="{MEDIA_PREFIX}hero\.svg"[^>\n]*>\n</p>[ \t]*$'
    rf'|^<img\s+src="{MEDIA_PREFIX}first-stitch\.gif"[^>\n]*>[ \t]*$'
)



class ProfileScopeError(ValueError):
    pass


def readme_copy(markup):
    return [line for line in PROFILE_MEDIA.sub("", markup).splitlines() if line.strip()]


def verify_changes(paths, prior_readme=None, candidate_readme=None):
    paths = set(paths)
    archive_files = {path for path in paths if ARCHIVE_PATH.fullmatch(path)}
    artwork = (paths & PROFILE_ART) | archive_files
    if unknown := sorted(paths - PROFILE_FILES - archive_files):
        raise ProfileScopeError("Unrelated paths in this profile change: " + ", ".join(unknown))
    if artwork and "AGENTS.md" in paths:
        raise ProfileScopeError("Put agent governance and artwork in separate changes.")
    if "README.md" in paths and prior_readme is None:
        raise ProfileScopeError("The base README is required for scope comparison.")
    if "README.md" in paths and not candidate_readme:
        raise ProfileScopeError("The public README must remain present.")
    if (artwork and "README.md" in paths and
            readme_copy(prior_readme) != readme_copy(candidate_readme)):
        raise ProfileScopeError("An artwork change may only edit the README's approved media markup.")


def git(*args):
    return subprocess.check_output(["git", *args]).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="Review the index against HEAD.")
    mode.add_argument("--range", nargs=2, metavar=("BASE", "HEAD"), help="Review two exact commits.")
    args = parser.parse_args()
    try:
        base, target = ("HEAD", "") if args.staged else args.range
        if not args.staged:
            for ref in (base, target):
                if not re.fullmatch(r"[a-f0-9]{40}", ref):
                    raise ProfileScopeError("The scope check requires full commit SHAs.")
        diff = ["--cached", base] if args.staged else [base, target]
        paths = git("diff", "--name-only", "--no-renames", "-z", *diff, "--").split("\0")[:-1]
        prior = candidate = None
        if "README.md" in paths:
            prior = git("show", f"{base}:README.md")
            candidate = git("show", f"{target}:README.md")
        verify_changes(paths, prior, candidate)
        print(f"PASS: profile scope ({len(paths)} changed paths)")
    except (ProfileScopeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
