# Skills Ant Design import control

Replace the native Skills editor file picker with Ant Design Upload and an
icon button, reusing the existing translated import label. Show the successfully
read filename with wrapping and a status announcement. The icon is decorative.

Import accepts a single Markdown file up to 64 KiB and validates UTF-8. Invalid
files preserve editor content. Reading disables editor actions. Upload always
returns LIST_IGNORE: selection only populates the local editor and never saves,
uploads, or enables a Skill automatically. Saving and version approval retain
their existing explicit actions.

Verification: SkillsSettings component tests passed (7), including local import,
oversize/extension/UTF-8 rejection, approval, failure handling, and Escape/focus.
Frontend typecheck and production build passed. Existing JSDOM pseudo-element
and build chunk-size warnings remain. No installed-runtime update or browser
visual verification was performed for this slice.
