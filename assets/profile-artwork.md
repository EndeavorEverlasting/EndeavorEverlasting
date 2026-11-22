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
