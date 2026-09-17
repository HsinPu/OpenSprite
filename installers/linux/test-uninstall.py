"""Exercise uninstall summaries in disposable homes without touching real services."""

from pathlib import Path
import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest


@unittest.skipUnless(sys.platform == "linux", "Requires Linux")
class UninstallSummaryTests(unittest.TestCase):
    def setUp(self):
        self.assertNotEqual(os.geteuid(), 0, "Run as a non-root test user")
        self.temporary = tempfile.TemporaryDirectory(prefix="opensprite-uninstall-summary ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.user_home = self.root / "home"
        self.data = self.user_home / ".opensprite"
        self.app = self.root / "custom data" / "opensprite" / "app"
        self.unit = self.root / "custom config" / "systemd" / "user" / "opensprite.service"
        self.data.mkdir(parents=True)
        self.app.mkdir(parents=True)
        self.unit.parent.mkdir(parents=True)
        (self.data / "keep.txt").write_text("test user data")
        self.unit.write_text("test unit")
        self.source = Path(__file__).with_name("uninstall.sh").read_text()
        self.script = self.app / "uninstall.sh"
        self.script.write_text(self.source)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        systemctl = self.bin / "systemctl"
        systemctl.write_text(
            '#!/bin/sh\n'
            'printf "%s\\n" "$*" >> "$TEST_SERVICE_LOG"\n'
            'if [ "${TEST_FAIL_RELOAD:-0}" = 1 ] && [ "$2" = daemon-reload ]; then exit 1; fi\n'
        )
        systemctl.chmod(0o700)
        remove = self.bin / "rm"
        remove.write_text(
            '#!/bin/sh\n'
            'if [ "${TEST_FAIL_DATA:-0}" = 1 ] && [ "$3" = "$HOME/.opensprite" ]; then\n'
            '  /bin/rm -f -- "$3/keep.txt"\n'
            '  echo "Injected partial data removal failure" >&2; exit 1\n'
            'fi\n'
            'exec /bin/rm "$@"\n'
        )
        remove.chmod(0o700)
        self.env = dict(os.environ, HOME=str(self.user_home),
                        XDG_DATA_HOME=str(self.root / "custom data"),
                        XDG_CONFIG_HOME=str(self.root / "custom config"),
                        PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        TEST_SERVICE_LOG=str(self.root / "services.log"))

    def run_uninstall(self, *args):
        return subprocess.run(["bash", str(self.script), *args], env=self.env,
                              capture_output=True, text=True, start_new_session=True, timeout=15)

    def run_interactive(self, answer, expected_exit=0):
        import pty

        pid, terminal = pty.fork()
        if pid == 0:
            os.execvpe("bash", ["bash", str(self.script), "--remove-user-data"], self.env)
        output = b""
        sent = False
        deadline = time.monotonic() + 15
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([terminal], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(terminal, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                    if not sent and b"Type DELETE: " in output:
                        os.write(terminal, answer.encode() + b"\n")
                        sent = True
            else:
                self.fail("Interactive uninstaller timed out")
            _, status = os.waitpid(pid, 0)
            pid = None
            self.assertTrue(sent, output.decode())
            self.assertEqual(os.waitstatus_to_exitcode(status), expected_exit, output.decode())
            return output.decode()
        finally:
            os.close(terminal)
            if pid is not None:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)

    def assert_summary(self, output, application="Removed", unit="Removed", data="Retained"):
        self.assertIn(f"Application: {application} -- {self.app}", output)
        self.assertIn(f"User service file: {unit} -- {self.unit}", output)
        self.assertIn(f"User data: {data} -- {self.data}", output)

    def test_default_preserves_data_and_runs_from_installed_directory(self):
        result = self.run_uninstall()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_summary(result.stdout)
        self.assertFalse(self.app.exists())
        self.assertFalse(self.unit.exists())
        self.assertEqual((self.data / "keep.txt").read_text(), "test user data")
        self.assertEqual((self.root / "services.log").read_text().splitlines(),
                         ["--user disable --now opensprite.service", "--user daemon-reload"])

    def test_purge_requires_and_honors_confirmation(self):
        output = self.run_interactive("DELETE")
        self.assert_summary(output, data="Removed")
        self.assertFalse(self.data.exists())

    def test_declined_purge_reports_retained_data(self):
        output = self.run_interactive("NO")
        self.assert_summary(output)
        self.assertEqual((self.data / "keep.txt").read_text(), "test user data")

    def test_missing_paths_are_not_reported_as_deleted(self):
        self.assertEqual(self.run_uninstall("--remove-user-data").returncode, 1)
        # The first run removed the app/unit but kept data without an interactive TTY.
        self.script = self.root / "uninstall.sh"
        self.script.write_text(self.source)
        result = self.run_uninstall()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_summary(result.stdout, application="Already absent", unit="Already absent")

    def test_partial_failure_reports_actual_state_and_preserves_error(self):
        self.env["TEST_FAIL_RELOAD"] = "1"
        result = self.run_uninstall()
        self.assertNotEqual(result.returncode, 0)
        self.assert_summary(result.stdout, application="Retained")
        self.assertIn("Uninstall stopped before completion.", result.stdout)
        self.assertTrue(self.app.exists())
        self.assertFalse(self.unit.exists())
        self.assertEqual((self.data / "keep.txt").read_text(), "test user data")

    def test_data_removal_failure_is_not_reported_as_cancellation_or_success(self):
        self.env["TEST_FAIL_DATA"] = "1"
        output = self.run_interactive("DELETE", expected_exit=1)
        self.assert_summary(output)
        self.assertIn("Uninstall stopped before completion.", output)
        self.assertNotIn("User data preserved.", output)
        self.assertNotIn("Retained user data can be reused", output)
        self.assertTrue(self.data.is_dir())
        self.assertFalse((self.data / "keep.txt").exists())


if __name__ == "__main__":
    unittest.main()
