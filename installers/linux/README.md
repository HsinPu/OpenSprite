# OpenSprite Linux installer

Run as the target user, never with `sudo`:

```bash
./installers/linux/install.sh --access-mode trusted_local
```

Use `trusted_local` for a directly operated Linux desktop. For remote Linux use
`password_required`; the installer writes a one-time setup URL only to the
interactive `/dev/tty`. Establish an SSH tunnel on the client before opening it:

```bash
ssh -N -L 8765:127.0.0.1:8765 user@server
```

The backend always binds `127.0.0.1`. Existing policy is preserved when the
flag is omitted. Reset password setup with `--access-mode password_required
--reset-local-access`. Uninstall preserves `~/.opensprite` unless the explicit
interactive `--remove-user-data` flow is confirmed.

The installer checks user lingering before registering the user service. It
never enables lingering or invokes `sudo`. When lingering is not enabled or
cannot be confirmed, the installer prints the administrator command
`sudo loginctl enable-linger $USER`; until an administrator enables it,
OpenSprite and its schedules may stop after logout.
