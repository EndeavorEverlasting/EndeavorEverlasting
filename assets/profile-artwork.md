# Profile artwork

The README opens on four cyan and copper trunks that converge around an inset
hourglass. The second image picks up the same trunk positions, widths and color
order below the copy, then opens into a wider set of branches. Light moves down
the visible trunk surfaces. The stills show the resting composition.

A dendrite is a tapered offshoot attached to a parent branch. Use continuous
junctions and smaller secondary forks. Build depth behind the trunks with
recessed filaments, overlapping surfaces, occlusion and a quiet background.
Keep material highlights on the curved surfaces and keep the silhouette
clean at reading size. Uniform-width paths, hollow node markers, stippling,
dry-brush edges, pencil strokes and crayon textures fail visual review.

## Regenerate and review

Use Python with NumPy and Pillow. The current assets were rendered with
NumPy 2.3.5 and Pillow 13.0.0.

```sh
python scripts/render_profile_motion.py --output /path/to/preview
python scripts/verify_profile_banner.py
python scripts/verify_profile_visuals.py
python -m unittest discover -s scripts -v
```

Before updating the assets, look at both actual GIFs and the reduced-motion
stills at desktop width and in a 340 px viewport. Compare with the previous
release at the same sizes. Inspect thumbnail-scale branch separation, taper,
junctions and depth, then inspect the full-size edges for texture and
quantization. Confirm the light goes down each panel and that the handoff
aligns across the copy. Preserve the one-shot playback and 250 kB combined GIF
budget. Use a fresh render and inspect the encodes before refreshing the
observations and SHA-256 values in [profile-artwork-review.json](profile-artwork-review.json).
That file records the inspection, and the validator ties it to the reviewed
renderer and assets. The validator cannot judge a changed artwork's style.

After an authorized merge, run `python scripts/verify_profile_visuals.py --live`
and inspect both images on the public GitHub profile.
