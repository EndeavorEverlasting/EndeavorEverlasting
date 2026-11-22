# Profile artwork

The banner introduces fragmented handoffs, the needle and a repeatable workflow.
The first GIF brings teal and copper dendrites into the needle. Four
aligned strands cross the introduction into the continuation GIF, which
branches into distinct repeatable endpoints. The footer picks up those
endpoints and converges around an hourglass. Its pulse represents
long-horizon durability and closes the page.

Use Fibonacci proportions throughout profile artwork. The banner retains its
original 13, 21, 34, 55 and 89 quarter-circle arcs. The GIFs share successive
quarter-circle arcs, inset rings with radii 21, 34, 55, 89, 144 and 233, branch
spacing and reach from the same sequence, and a cadence of 21 frames at
130 milliseconds. The spiral and cut rings sit behind the needle and branches.
Keep the needle and strand junctions visible. Use tapered attached forks,
visible occlusion, curved material highlights and clean silhouettes.
Uniform paths, disconnected nodes and pencil or crayon textures fail review.

## Regenerate and review

The renderer uses NumPy and Pillow. The current assets used NumPy 2.3.5
and Pillow 13.0.0. The visual checker uses Pillow to decode shipped GIFs.

```sh
python scripts/render_profile_motion.py --output /path/to/preview
python scripts/verify_profile_banner.py
python scripts/verify_profile_visuals.py
python -m unittest discover -s scripts -v
```

Inspect each encoded GIF and its PNG still at desktop width and at 255 px
image width. Compare the previous release at the same widths. Confirm that
light descends across both moving panels and that the bottom hourglass
brightens and dims through each complete cycle. The checker measures decoded
movement, the wraparound frame, GIF repeat metadata, timing, placement and
matching PNG fallbacks. Keep the three animations under 250 kB combined.
Update the visual observations and SHA-256 values in
[profile-artwork-review.json](profile-artwork-review.json) after inspection
of those exact encodes. The visual judgment remains part of the review.

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
