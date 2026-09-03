# Linux installation

OpenSprite installs per user without `sudo`. Program files live below
`${XDG_DATA_HOME:-$HOME/.local/share}/opensprite/app`; durable product data
remains exclusively in `~/.opensprite`. A systemd user unit owns one Uvicorn
process bound to `127.0.0.1` with no reload or additional workers.

## Access modes

`trusted_local` is intended for a directly operated graphical Linux desktop.
It opens the base localhost URL through `xdg-open` when available and does not
create bootstrap state. `password_required` is intended for SSH and shared
hosts. The installer writes its one-time setup URL directly to `/dev/tty`; the
raw token never enters stdout, stderr, the journal, a file, or process
arguments.

Remote clients establish their own tunnel before opening the printed URL:

```bash
ssh -N -L 8765:127.0.0.1:8765 user@server
```

The backend cannot distinguish a direct localhost connection from one arriving
through an SSH tunnel. Access mode is therefore installation-wide and never
selected from request metadata.

## Lifecycle and recovery

The installer builds in a same-filesystem staging directory, stops an existing
user service, atomically moves the application root, installs the Python
environment at its final path, writes the strict access policy, renders the
systemd unit, and verifies `/healthz`. Failure restores the previous app,
policy, bootstrap record, and service unit. Normal uninstall removes program
and lifecycle files but preserves `~/.opensprite`.

The explicit `--reset-local-access` flow is valid only with
`password_required`. It preserves conversations, credentials, settings, logs,
and the database while replacing password/bootstrap state. Permanent user-data
removal requires an interactive `DELETE` confirmation.

The installer rejects root execution, non-Linux systems, unsafe test roots,
symlink roots, invalid ports and unavailable prerequisites. It does not expose
a public listener, configure a reverse proxy, enable system linger, or alter a
firewall.
