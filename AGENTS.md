# Publication and authorship

Use GitHub noreply identity for every commit in this public repository:

- Name: `EgorKo25`
- Email: `77259232+EgorKo25@users.noreply.github.com`

Check both author and committer before pushing. Do not use an email inherited
from a work repository, system configuration or environment variables. Keep this
configuration local to this repository; do not change the user's work identity
globally. The user explicitly requested this privacy rule.

Write original teaching text and examples. The paid course is a topic reference;
do not copy its lessons, exercises or images into this public handbook.

Build maintained volumes with `python3 scripts/build_library.py`. Export only
through `scripts/prepare_site.py`; private deployment instructions and untracked
files must not enter Pages or the portable reading copy.

`published-volumes.json` is the explicit publication allowlist used by the
build, shared dictionary, export, and reader checks. Register a new volume only
after its sources and labs have been reviewed. A working directory or a
`volume_config.py` alone must not grant publication permission. Add new learning
directions to `scripts/library_structure.py` without presenting them as ready.
