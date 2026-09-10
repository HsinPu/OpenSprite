# Chat corner controls (0.21.2)

## Scope

Remove the full-width toolbar treatment while preserving the existing panel,
conversation and draft state. The desktop sidebar spans the full shell height;
its toggle remains in the chat breadcrumb row, to the left of the workspace,
in both expanded and collapsed states. No toggle sits beside the new-chat button.
The execution expand/collapse control stays at the far right of the breadcrumb
row in both states, aligned with the left control. The panel heading has no
duplicate toggle. Neither control jumps to another row when toggled.
The desktop execution panel spans the full shell height, matching the left
sidebar. Only the chat column reserves space for the breadcrumb controls; the
execution heading starts at the top. The breadcrumb row ends at the chat/panel
boundary, so its right toggle remains outside the panel on the chat side. A
shared responsive panel-width token keeps that boundary aligned at both desktop
widths. Collapsing the panel extends the breadcrumb row to the window edge.
Narrow-screen drawer layout is unchanged.
The compact workspace/conversation breadcrumb
stays within the chat column without a divider or separate background. The
header new-chat action appears only when desktop navigation is collapsed or on
mobile. Existing colors and provider behavior are unchanged.

## Verification

- Focused App and ChatWorkspace tests: 53 passed.
- Production build includes TypeScript checking.
- Browser checks cover expanded/collapsed desktop and narrow layout.
- Local installation is requested separately as part of this delivery; no Git
  commit or push is requested.
