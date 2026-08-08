"""Shell command policy behavior."""

from opensprite.modules.tools.shell_policy import (
    classify_destructive_shell_command,
    foreground_exec_guidance,
    has_shell_background_operator,
)


class TestBackgroundOperatorDetection:
    def test_detects_shell_background_operator(self):
        assert has_shell_background_operator("sleep 1 &") is True
        assert has_shell_background_operator("sleep 1&") is True

    def test_ignores_redirect_and_logical_ampersands(self):
        assert has_shell_background_operator("cmd 2>&1") is False
        assert has_shell_background_operator("cmd &>/dev/null") is False
        assert has_shell_background_operator("A && B") is False

    def test_ignores_ampersand_inside_quotes(self):
        assert has_shell_background_operator('printf "&"') is False


class TestForegroundGuidance:
    def test_blocks_trailing_ampersand(self):
        assert foreground_exec_guidance("sleep 1&") is not None

    def test_blocks_inline_ampersand(self):
        assert foreground_exec_guidance("foo & bar") is not None

    def test_blocks_nohup(self):
        assert foreground_exec_guidance("nohup python server.py") is not None

    def test_blocks_uvicorn(self):
        assert foreground_exec_guidance("uvicorn app:app --host 0.0.0.0") is not None

    def test_allows_plain_echo(self):
        assert foreground_exec_guidance("echo hello") is None

    def test_allows_uvicorn_help(self):
        assert foreground_exec_guidance("uvicorn --help") is None


def test_destructive_classifier_blocks_common_bypass_variants():
    commands = [
        "Git Reset --Hard HEAD",
        '"git" reset --hard HEAD',
        "git clean -fdx",
        "git clean -d -f",
        "rm -rf build",
        "rm -Recurse build",
        "Remove-Item -LiteralPath build -Force",
        "cmd /c del /f important.txt",
        'powershell -Command "Remove-Item -Recurse ."',
        "rmdir /s build",
        "diskpart /s wipe.txt",
    ]

    for command in commands:
        assert classify_destructive_shell_command(command), command


def test_destructive_classifier_blocks_inline_wrapper_bypass_variants():
    commands = [
        'bash -c "git reset --hard HEAD"',
        "sh -lc 'rm -rf build'",
        'python -c "import os; os.system(\'git clean -fdx\')"',
        'python -c "import subprocess; subprocess.run(\'rm -rf build\', shell=True)"',
        'python -c "import subprocess; subprocess.run([\'rm\', \'-rf\', \'build\'])"',
        'node -e "require(\'child_process\').execSync(\'git reset --hard HEAD\')"',
        'node -e "const { exec } = require(\'child_process\'); exec(\'rm -rf build\')"',
    ]

    for command in commands:
        assert classify_destructive_shell_command(command), command


def test_destructive_classifier_allows_safe_commands():
    commands = [
        "git status",
        "git diff -- src/app.py",
        "Remove-Item --help",
        "npm run build",
        "echo git reset --hard",
        'python -c "print(\'git reset --hard\')"',
        'node -e "console.log(\'rm -rf build\')"',
    ]

    for command in commands:
        assert classify_destructive_shell_command(command) is None, command
