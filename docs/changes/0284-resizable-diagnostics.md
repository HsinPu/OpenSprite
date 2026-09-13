# Resizable diagnostic drawer

- Reuse PanelResizeHandle with an optional minimum (existing panels unchanged).
- Diagnostics defaults to 560px, clamps desktop width to 360px–viewport minus
  48px, and uses full viewport width below 768px.
- Drag the left edge, use arrow keys, or reset with Home/double-click.
- Width remains local to the mounted diagnostic component; no data/backend
  changes or persistence of a second global panel setting.
- Browser fixture verified actual drag from 560 to 760px, ArrowRight to 750px,
  and Home reset to 560px.
- No installation, commit or additional version bump included.
