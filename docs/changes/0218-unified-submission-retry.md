# Unified submission retry

The retry entry point prioritizes pending immutable submissions through the same
send routine. Without a pending request it reloads the accepted Run. A new chat
can retry without a conversation ID or composer text. Shared synchronous busy
guards prevent overlapping retry/send operations, and ordinary recovery refuses
to hydrate an older Run while a submission remains pending.

Add three-language explanation that retry uses the original message, not the
draft. Extend the lost-response test to invoke retry twice without passing text
and assert identical original payloads.

Verification: all 360 frontend tests passed. After updating typed component
fixtures, the 40 chat/retry tests passed again; production build (including
TypeScript checking) passed. Existing bundle-size and jsdom pseudo-element
warnings remain. No live browser verification was performed for this slice.
No version bump, installation, commit or push.
