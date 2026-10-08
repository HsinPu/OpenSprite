# OpenSprite architecture

OpenSprite 0.21.31 is a text Agent workbench with a replaceable Loop and recovery policy.
See [clean-agent-core](clean-agent-core.md) for the removed surfaces and upgrade boundary.

## Ownership

`frontend/` owns React/TypeScript/Ant Design presentation and strict API consumers.
`backend/` owns the Python local service, encrypted credentials, text execution and persistence.
`contracts/` is the HTTP/SSE authority; installers only manage installation, and scripts only verify/maintain the repository.
There is no application CLI or command shim.

The API validates input and delegates accepted requests to `application/chat_service.py`.
The service snapshots AI settings, Workspace, Provider endpoint and execution plugins under the mutation gate.
`RunManager` owns task cancellation and single-owner execution. `AgentLoop` and `LoopExecutionHost` own context, inference, events, partial output and terminal transactions.
An installed API v2 Driver coordinates the Host; a policy may veto otherwise eligible retry/continuation.
`NativeModelGateway` owns encrypted-credential lookup and routes approved protocols to native adapters.
`SqliteConversationRepository` owns conversations, messages, Runs, events and compactions.

## Runtime and security

One backend writer uses one `.opensprite` root. Provider keys are AES-256-GCM ciphertext with a per-installation random key.
Browser operations use same-origin HTTP/SSE and retain Host/Origin/session protections.
Password mode uses Argon2id and process-memory sessions; trusted-local mode remains an explicit installation policy.
Plugins execute trusted Python in the backend process; neither Host validation nor wheel inspection is a sandbox.
Workspace paths are metadata; the text core cannot read files or execute commands.
Every future extension needs an approved workflow and a reviewed contract before adding runtime behavior.
