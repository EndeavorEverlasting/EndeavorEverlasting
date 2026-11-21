# GitHub profile release

The release target is the [public profile](https://github.com/EndeavorEverlasting).
Its source is this repository's default-branch README and assets.

- Run the profile workflow's checkout checks before landing README or artwork changes.
- When the operator has approved the visual and authorized landing, merge the verified change to the default branch in the same run. Carry that approval forward. A draft, branch preview, or green PR check is an intermediate result.
- After landing, run `python scripts/verify_profile_visuals.py --live` from the landed checkout. For visual changes, also open the public profile and verify the image's placement and visibility in the rendered page. Record the merged commit, public URL, and observed result. Investigate stale or missing artwork before claiming completion.
- Ask the operator only for a remaining visual decision or an actual authority boundary. Keep release verification and recoverable fixes with the executing agent.
