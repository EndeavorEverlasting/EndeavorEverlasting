# GitHub profile release

The release target is the [public profile](https://github.com/EndeavorEverlasting).
Its source is this repository's default-branch README and assets.

- Start with `python scripts/profile_release.py status --history` for the checked-out artwork, populated scenes, independent editorial revision, and commit history. Use `--json` when another tool consumes the results. The last fetched default reference can be stale; use `status --live` from a clean checkout of GitHub's default HEAD to verify the public artwork and repository invitation.
- Run `python scripts/profile_release.py status --compare v09` to see which scenes and repository invitation would change, then use the printed `restore` preview. Artwork restores keep current README prose. The linked Nexus invitation travels with its artwork. Older original artwork commits and newer Git registration commits are recorded separately.

- From the clean candidate commit, install `Pillow>=11,<14` if needed and run `python scripts/profile_release.py verify --base <full-origin-main-sha>` before landing. Fetch the default branch first and use its commit as the base. This runs the same scope, banner, artwork, and regression checks as Actions on `main`.
- Pull requests run the base commit's scope guard. The full hosted suite runs on `main` pushes and manual dispatch. Entire CLI records agent sessions and checkpoints. Keep any session capture separate from this public repository.
- When the operator has approved the visual and authorized landing, merge the verified change to the default branch in the same run. Carry that approval forward. A draft, branch preview, or green PR check is an intermediate result.
- After landing, run `python scripts/verify_profile_visuals.py --live` from the landed checkout. For visual changes, also open the public profile and verify the image's placement and visibility in the rendered page. Record the merged commit, public URL, and observed result. Investigate stale or missing artwork before claiming completion.
- Ask the operator only for a remaining visual decision or an actual authority boundary. Keep release verification and recoverable fixes with the executing agent.
