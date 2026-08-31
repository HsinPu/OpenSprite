# Code block copy button

## Objective

Make code returned in Markdown messages easy to copy without changing the
stored Markdown source or executing the content.

## Changes

- Add a localized Ant Design copy button to fenced code blocks.
- Keep inline code unchanged and copy only the code text, excluding the
  renderer's trailing newline.
- Report successful and failed clipboard writes through the button label and
  an `aria-live` status region.
- Preserve the existing safe Markdown behavior: raw HTML remains disabled and
  external links keep their existing safeguards.

## Verification

- MarkdownMessage tests cover rendering, exact copied text, success feedback,
  failure feedback, and unchanged inline Markdown behavior.
- TypeScript typecheck and production build.
