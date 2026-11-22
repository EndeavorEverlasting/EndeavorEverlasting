# Profile artwork

The banner introduces fragmented handoffs, the needle and a repeatable workflow.
Its lower-right output dissolves into the opener's blue and orange field. The v11 opener carries cyan and ember signals down through fine filaments toward
the introduction. The second GIF resumes the same vertical field beneath the
copy, using the texture and glow of the v10 closing invitation. The v10 finale sets “Explore the projects.” and “Build with me.”
inside the GIF. The centered Instrument Sans setting gives the second line
more weight and makes it the first invitation the eye lands on. Distinct cores
and soft halos light up junctions down the cyan and ember routes in turn. Each
junction has a faint afterglow. The entire image opens the public repository list. Its alternative
text includes how to collaborate through an issue or pull request.

The v11 upper cosmic web uses neighboring slices of one deterministic field.
It remaps the type-free margins of the v10 Nexus poster into short, interlaced
filament sections over a recessed layer from the v09 field.
Neighboring clouds connect through granular blue and orange filaments.
Orange dust sits behind brighter ribbons and knots, threading between and
through the blue field. Both colors come from the banner and avatar. Dark voids provide scale and separate the
layers. Keep individual paths buried in the density and let bright regions
emerge where clouds meet. Exposed wireframes, concentric rings, metallic tubes,
claws and repeated root silhouettes fail visual review. Fibonacci proportions
govern the density scales, phase period and cadence. The first two scenes use
21 frames at 130 milliseconds. The Nexus footer has 34 frames at 80 milliseconds
and alternates the two paths in one 2.72-second loop. The banner retains its
Fibonacci spiral.

## Use the portable workflow

Use the [portable profile artwork capability](https://github.com/EndeavorEverlasting/Automation/blob/main/capabilities/profile-artwork/CAPABILITY.md)
to generate fresh artwork for a new GitHub profile or roll back artwork while
preserving the current README Markdown prose. For EndeavorEverlasting, import
the exact v11 GIFs and PNG stills from the [v11 assets](profile-releases/v11/assets/).

## Regenerate and review

The renderer uses NumPy, SciPy and Pillow. The current assets used NumPy 2.3.5,
SciPy 1.17.0 and Pillow 13.0.0. The visual checker uses Pillow to decode
shipped GIFs.

```sh
python scripts/render_profile_motion.py --output /path/to/legacy-preview
python scripts/render_profile_motion.py --nexus-footer
python scripts/render_profile_motion.py --nexus-upper
python scripts/verify_profile_banner.py
python scripts/verify_profile_visuals.py
python -m unittest discover -s scripts -v
```

The v10 PNG is the source poster for its GIF, with a generated cosmic-web plate
and [Instrument Sans](https://github.com/Instrument/instrument-sans) lettering
rasterized from the SIL Open Font License 1.1 typeface. The `--nexus-footer`
command uses that poster and regenerates
only the GIF. The v11 upper renderer reads the immutable v10 poster and updates
only the opening and continuation GIFs and PNGs. The unrestricted legacy renderer
produces the earlier three-panel
expression for comparison.

Inspect each encoded GIF and its PNG still at desktop width and at 255 px.
Check that the banner output meets the projected opening field. Keep a visible
anchor at each text break and fade the surrounding light at the image edges.
The validator checks the sequence, detached or misplaced panels, repeat
metadata, downward signal, two independently descending footer pulses and matching reduced-motion stills.
The first two panels retain the density and palette checks. The v10 footer checks
two lines of steady, legible text, the repository link, a continuous seam and
descending glints with a minimum visible core and halo on both sides at 255 px.
Retain the visual review for shape and depth.
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

The [profile release archive](profile-releases/) holds the published snapshots.
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
| [v08](profile-releases/v08/) | Teal and coral cosmic web with a handoff to Pinned |
| [v09](profile-releases/v09/) | Layered blue and orange cosmic web |
| [v10](profile-releases/v10/) | Linked Nexus invitation for users and collaborators |
| [v11](profile-releases/v11/) | Nexus filaments and halos carry through both upper transitions |

Create a branch from current main. The first restore command prints a patch.
The second applies it to your checkout. It changes the media blocks and the
active version in the catalog while preserving the current README prose.
The v10 invitation rolls back and returns with its GIF. A separately written
legacy invitation stays with the copy when restoring legacy artwork.
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
checks are green. To return to the latest expression, repeat the steps with `v11`.
If a rollback needs a text break whose anchor was edited out, restore the
supported section anchor in a separate editorial change. Saved working edits to
the README or catalog must be committed or stashed before applying rollback.

For a new design, produce and review the working artwork and README, then
capture them before the PR is merged. The command provides the next available
ID if you choose an existing or out-of-sequence one. Capture from working
media paths under `assets/`, then select the newly archived paths in the same
PR so each artwork release has fresh URLs.

```sh
python scripts/profile_release.py capture v11 --title "Your new expression"
git add -- README.md assets scripts
git commit -m "Capture profile artwork v10"
python scripts/profile_release.py restore v11 --apply
python scripts/profile_release.py check
```

CI verifies the selected expression, the bytes of every archived file and
immutability against the PR base. Keep archived releases intact and capture
a new release for subsequent changes.
