# Automatic Skills selection in chat — 0.14.3

- Remove the composer Skill picker, selection state, and catalog requests.
- Browser chat no longer sends skillIds; backend manual API compatibility and historical events remain supported.
- Enabled Skills remain selected automatically through load_skill, subject to model tool-call support.
