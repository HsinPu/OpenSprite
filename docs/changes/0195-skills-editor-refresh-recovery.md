# Skills editor refresh recovery

## Changes

- Reset committed state when opening a newly validated folder import preview.
- Lock Markdown editing and file import after a successful write whose list refresh failed, so refresh retry cannot discard subsequent edits.
- Preserve retryable editing when the write itself fails.

## Verification

- SkillsSettings regression suite: 13 passed, including a failed refresh followed by closing and importing another folder.
- Reviewed save, approval, folder import, close, reopen, and refresh retry transitions.
- No installed runtime update or browser verification performed for this slice.
