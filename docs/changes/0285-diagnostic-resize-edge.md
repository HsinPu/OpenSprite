# Diagnostic resize edge

- Scope overrides to the diagnostic drawer: neutral 1px edge, transparent 8px
  hit area, no inherited right-panel transform or orange pseudo-element.
- Hover/drag use neutral gray. Keyboard focus gets a short central marker,
  not a full-height accent line. Dragging disables selection inside the drawer.
- Include app.css in the synthetic browser fixture so shared resize styles are
  present during visual regression checks.
- Main panel styles, sizing logic and event presentation remain unchanged.

Verification: 11 focused tests passed; TypeScript/build and diff checks passed.
Browser drag changed 560px to 760px. After release the handle was transparent,
not dragging, with neutral rgb(229, 227, 223) edge and no transform.
