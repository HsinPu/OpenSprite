# One-command Windows source installation

The bootstrap accepts explicit FromSource mode. It requests Git as well as the
existing Node.js/npm and uv prerequisites, shallow-clones the fixed official
HsinPu/OpenSprite main branch into its guarded temporary root, and invokes the
existing installer. Release mode remains unchanged and never silently falls back
to source. Numbered Version and FromSource are rejected together.

README documents a raw.githubusercontent.com script invocation with FromSource
and InstallPrerequisites. This becomes usable only after these changes reach
GitHub main. Existing installation/data preservation remains owned by install.ps1.

Verification: bootstrap isolation tests cover source orchestration, required Git,
no Release requests, success cleanup, incompatible arguments and clone failure
reporting/cleanup. Prerequisite and packaging regression tests pass; diff check
passes. Tests mock downloads, Git and installation; no real system packages or
application deployment were performed, and no public one-command success is claimed.
