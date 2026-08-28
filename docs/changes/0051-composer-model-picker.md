# 0051 Composer model picker

## Objective

Move the existing chat model selector next to the send control so model choice belongs to message composition instead of the conversation header.

## Changes

- Moved the single existing model selector from the header into the composer's primary action group.
- Kept the current model value, provider grouping, disabled states, persistence callback and accessibility label unchanged.
- Left only the conversation title, local Agent status and future actions in the header.
- Added bounded desktop and mobile widths so long model names do not displace the send control.

## Public impact

Users now choose the model beside the send button. Model persistence, Provider state, Agent execution and HTTP contracts are unchanged.

## Verification

- Component tests verify that the model selector and send button share the composer action group.
- All 92 frontend tests, TypeScript checks and the production build passed.
- Desktop and 390px browser checks confirmed one composer picker, no header picker and no horizontal overflow.

## Remaining work

- Attachment and message-option controls remain intentionally unavailable.
