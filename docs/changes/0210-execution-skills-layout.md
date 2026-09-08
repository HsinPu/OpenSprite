# Execution Skills layout — 0.18.1

Moves Skills below tools and above execution information. Uses shared capability
cards and the existing empty-tool card, with wrapping names, selection source and
an error indicator. Skills are shown only with loaded run details, not above the
history loading/error state. Agent selection and backend events are unchanged.

Component regression coverage verifies section order and shared empty/loaded
cards, alongside existing failure and historical-run tests. No installed runtime
update or push is performed. Actual browser geometry is not claimed verified.
