# Skills storage and approval policy

- Added bounded SafeLoader front matter parsing with duplicate/alias rejection.
- Added global and Workspace-local files, strict catalog, revision checks,
  content-hash approval, overrides, immutable snapshots and archive deletion.
- File/catalog writes recover through a private roll-forward transaction record.
- Verification: 9 focused storage, policy, parser and recovery tests passed.
