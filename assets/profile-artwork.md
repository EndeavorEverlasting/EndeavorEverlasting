# Profile artwork

The banner introduces fragmented handoffs, the needle and a repeatable workflow.
Its lower-right output dissolves into the opener's violet field. The first GIF
carries a cyan-white signal down through clusters toward the introduction.
The second resumes the same field beneath the copy and leads into the
remaining sections. The final GIF collects light in a breathing cluster,
carrying the banner's theme of long-horizon durability to the bottom of the page.

The cosmic web is one deterministic density field sliced at the two text breaks.
Neighboring clouds connect through granular violet filaments, cool luminous
knots and sparse warmer points. Dark voids provide scale and separate the
layers. Keep individual paths buried in the density and let bright regions
emerge where clouds meet. Exposed wireframes, concentric rings, metallic tubes,
claws and repeated root silhouettes fail visual review. Fibonacci proportions
govern the density scales, phase period and the cadence of 21 frames at
130 milliseconds. The existing banner retains its Fibonacci spiral.

## Regenerate and review

The renderer uses NumPy, SciPy and Pillow. The current assets used NumPy 2.3.5,
SciPy 1.17.0 and Pillow 13.0.0. The visual checker uses Pillow to decode
shipped GIFs.

```sh
python scripts/render_profile_motion.py --output /path/to/preview
python scripts/verify_profile_banner.py
python scripts/verify_profile_visuals.py
python -m unittest discover -s scripts -v
```

Inspect each encoded GIF and its PNG still at desktop width and at 255 px.
Check that the banner output meets the projected opening field. Keep a visible
anchor at each text break and fade the surrounding light at the image edges.
The validator checks the sequence, detached or misplaced panels, repeat
metadata, downward signal, footer pulse and matching reduced-motion stills.
The pixel checks also look for broad midtone density, deep voids and luminous
cores, rejecting sparse line-art silhouettes and undifferentiated fog. Retain
the qualitative visual review for organic shape and a sense of depth.
Keep the three GIFs under 250 kB combined. Update
[profile-artwork-review.json](profile-artwork-review.json) after inspecting
the exact files.

## Keep changes scoped

GitHub Actions checks every pull request for out-of-scope file paths and
for README copy changes bundled with artwork. Put unrelated changes in their
own repository or the appropriate separate change. To run the same scope
check before local commits, configure a checkout with no existing hook path:

```sh
git config --local core.hooksPath .githooks
```

If a checkout already defines a hook path, add
`python scripts/verify_profile_scope.py --staged` to its existing pre-commit
hook. The CI check reports failures for direct pushes after they arrive.
Requiring that check before merge is a separate branch-protection setting.

After an authorized merge, run `python scripts/verify_profile_visuals.py --live`
and inspect the four images on the public GitHub profile.

## Browse and restore profile versions

The [profile release archive](profile-releases/) holds seven initial snapshots.
Each folder renders the README and artwork as they appeared in that version.
The catalog records the original commit and checksums for its archived files.

| Version | Expression |
| --- | --- |
| [v01](profile-releases/v01/) | Fibonacci workflow banner |
| [v02](profile-releases/v02/) | First Stitch |
| [v03](profile-releases/v03/) | Motion woven through the introduction |
| [v04](profile-releases/v04/) | Top-down threads |
| [v05](profile-releases/v05/) | Layered dendritic artwork |
| [v06](profile-releases/v06/) | Looping Fibonacci panels |
| [v07](profile-releases/v07/) | Continuous cosmic web |

Create a branch from current main. The first restore command prints a patch.
The second applies it to your checkout. It changes the media blocks and the
active version in the catalog while preserving the current README prose.
GitHub account settings, including the avatar and bio, live outside this archive.

```sh
git switch -c profile/restore-v06
python scripts/profile_release.py list
python scripts/profile_release.py restore v06
python scripts/profile_release.py restore v06 --apply
python scripts/verify_profile_visuals.py
git diff
```

Commit the two-file patch and merge through the normal PR workflow after the
checks are green. To return to the cosmic web, repeat the steps with `v07`.
If a rollback needs a text break whose anchor was edited out, restore the
supported section anchor in a separate editorial change. Saved working edits to
the README or catalog must be committed or stashed before applying rollback.

For a new design, produce and review the working artwork and README, then
capture them before the PR is merged. The command provides the next available
ID if you choose an existing or out-of-sequence one. Include the archive folder,
catalog and approved artwork in the PR.

```sh
python scripts/profile_release.py capture v08 --title "Your new expression"
python scripts/profile_release.py check
```

CI verifies the selected expression, the bytes of every archived file and
immutability against the PR base. Keep archived releases intact and capture
a new release for subsequent changes.
