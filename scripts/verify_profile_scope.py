#!/usr/bin/env python3
"""Reject out-of-scope files and mixed artwork/editorial changes."""
import argparse
import json
import re
import subprocess

ARTWORK_REVIEW = "assets/profile-artwork-review.json"
QUALITY_EVALUATORS = {"scripts/verify_profile_visuals.py", "scripts/profile_release.py",
                      "scripts/verify_profile_scope.py", ".github/workflows/profile-banner.yml"}

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
REPOSITORIES_URL = "https://github.com/EndeavorEverlasting?tab=repositories"
NEXUS_ALT = ("Explore the projects. Build with me. Browse the public repositories, "
             "or open an issue or pull request in a project to collaborate.")
NEXUS_BLOCK = (
    rf'^<a href="{re.escape(REPOSITORIES_URL)}">\n<picture>\n'
    rf'  <source media="\(prefers-reduced-motion: reduce\)" srcset="{MEDIA_PREFIX}stitch-pulse\.png" />\n'
    rf'  <img src="{MEDIA_PREFIX}stitch-pulse\.gif" width="100%" alt="{re.escape(NEXUS_ALT)}" />\n'
    r'</picture>\n</a>[ \t]*$'
)
NEXUS_MEDIA = re.compile(NEXUS_BLOCK, re.MULTILINE)
PROFILE_MEDIA = re.compile(
    rf'(?m){NEXUS_BLOCK}|^<picture>[ \t]*\n[ \t]*<source\b[^>\n]*>\n[ \t]*'
    rf'<img\s+src="{MEDIA_PREFIX}{MEDIA_FILENAME}"[^>\n]*>\n</picture>[ \t]*$'
    rf'|^<p align="center">[ \t]*\n[ \t]*'
    rf'<img\s+src="{MEDIA_PREFIX}hero\.svg"[^>\n]*>\n</p>[ \t]*$'
    rf'|^<img\s+src="{MEDIA_PREFIX}first-stitch\.gif"[^>\n]*>[ \t]*$'
)


FOOTER_INVITATION = re.compile(
    rf'(?m)^<p><strong>[^<\n]+</strong>[^<\n]+'
    rf'<a href="{re.escape(REPOSITORIES_URL)}">[^<\n]+</a></p>[ \t]*\s*\Z'
)
LEGACY_NEXUS = ('<p><strong>Explore the project nexus.</strong> Your next tool may be among '
                'the pinned projects below. '
                f'<a href="{REPOSITORIES_URL}">Browse all repositories →</a></p>')


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
    release_paths = {path for path in paths if path.startswith("assets/")
                     and re.fullmatch(MEDIA_PREFIX + MEDIA_FILENAME, path)}
    if paths & QUALITY_EVALUATORS and (archive_files or release_paths
                                      or paths & {"README.md", "assets/profile-releases.json",
                                                  "scripts/render_profile_motion.py"}):
        raise ProfileScopeError("Land quality evaluator changes separately from artwork and README changes.")
    if artwork and "AGENTS.md" in paths:
        raise ProfileScopeError("Put agent governance and artwork in separate changes.")
    if "README.md" in paths and prior_readme is None:
        raise ProfileScopeError("The base README is required for scope comparison.")
    if "README.md" in paths and not candidate_readme:
        raise ProfileScopeError("The public README must remain present.")
    if artwork and "README.md" in paths:
        footer = NEXUS_MEDIA.search(candidate_readme)
        if (footer and not candidate_readme[footer.end():].strip()
                and not NEXUS_MEDIA.search(prior_readme)
                and prior_readme.rstrip().endswith(LEGACY_NEXUS)):
            prior_readme = prior_readme.rstrip().removesuffix(LEGACY_NEXUS)
        if readme_copy(prior_readme) != readme_copy(candidate_readme):
            raise ProfileScopeError("An artwork change may only edit the README's approved media markup.")


def verify_quality_floor(prior, candidate):
    floor = json.loads(prior).get("quality_floor")
    if floor is not None and (not candidate or json.loads(candidate).get("quality_floor") != floor):
        raise ProfileScopeError("The approved V11 quality floor is immutable.")


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
        if ARTWORK_REVIEW in paths:
            prior_review = git("show", f"{base}:{ARTWORK_REVIEW}")
            exists = subprocess.run(
                ["git", "cat-file", "-e", f"{target}:{ARTWORK_REVIEW}"], capture_output=True
            ).returncode == 0
            candidate_review = git("show", f"{target}:{ARTWORK_REVIEW}") if exists else None
            verify_quality_floor(prior_review, candidate_review)
        print(f"PASS: profile scope ({len(paths)} changed paths)")
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"FAIL: {error}\n")


if __name__ == "__main__":
    main()
