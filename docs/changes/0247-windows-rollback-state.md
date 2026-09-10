# Windows rollback port and partial-write recovery

- Preserve the previous startup port before cutover; rollback launches the restored application on that port instead of the attempted installation port. Registry command text is never executed.
- Mark policy, bootstrap and access state as requiring recovery before calling writers, including failures after replacement during cleanup.
- Add isolated regression checks for default/custom previous ports, rollback argument forwarding and writer failures with recovery flags already set.
- Scope: no version bump, deployment, credential changes or commit. Full live-service failure injection remains unverified.
