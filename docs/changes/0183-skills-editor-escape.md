# Skills editor keyboard boundary

Live in-app browser verification used an isolated temporary data root and port
8766, not the installed user database or credentials. Creating a global Skill
showed pending confirmation; reopening and approving showed effective state.
The composer listed the effective Skill. At 390px, the page scroll width was
390px and the editor rendered as a Drawer.

Escape initially dismissed the native outer settings dialog along with the
editor. The editor now consumes Escape in a document capture handler while open,
blocks dismissal while saving, and restores the opener after closing. A regression
test verifies propagation and focus; live retest confirmed the settings page
remains visible and focus returns to Edit. The browser viewport was reset and
the test tab closed. No installed application was updated.

Verification: three SkillsSettings tests and production build pass. This is
actual UI evidence, separate from the blocked Provider-routing probe.
