"""Provider-neutral shell execution safety policy."""

import ast
import re

from opensprite.core.contracts.tool_results import tool_error_result


DEFAULT_EXEC_DENY_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fq]\b",
    r"\berase\s+/(?:[fq]|qf)\b",
    r"\brmdir\s+/s\b",
    r"\bremove-item\b.*(?:-recurse|-force)",
    r"\bgit\s+clean\b(?:[^\n]*\s)?-[^-\n]*f",
    r"\bgit\s+reset\s+--hard\b",
    r"(?:^|[;&|]\s*)format\b",
    r"\b(mkfs|diskpart)\b",
    r"\bdd\s+if=",
    r">\s*/dev/sd",
    r"\b(shutdown|reboot|poweroff)\b",
    r":\(\)\s*\{.*\};\s*:",
]


def _read_shell_token(command: str, start: int) -> tuple[str, int]:
    """Read one shell token, preserving quotes/escapes, starting at *start*."""
    i = start
    n = len(command)

    while i < n:
        ch = command[i]
        if ch.isspace() or ch in ";|&()":
            break
        if ch == "'":
            i += 1
            while i < n and command[i] != "'":
                i += 1
            if i < n:
                i += 1
            continue
        if ch == '"':
            i += 1
            while i < n:
                inner = command[i]
                if inner == "\\" and i + 1 < n:
                    i += 2
                    continue
                if inner == '"':
                    i += 1
                    break
                i += 1
            continue
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        i += 1

    return command[start:i], i


def has_shell_background_operator(command: str) -> bool:
    """Return True when the command uses shell backgrounding with `&`."""
    i = 0
    n = len(command)

    while i < n:
        ch = command[i]

        if ch.isspace():
            i += 1
            continue

        if ch == "#":
            nl = command.find("\n", i)
            if nl == -1:
                return False
            i = nl + 1
            continue

        if ch == "\\" and i + 1 < n:
            i += 2
            continue

        if ch in ("'", '"'):
            _, next_i = _read_shell_token(command, i)
            i = max(next_i, i + 1)
            continue

        if ch == "&":
            next_ch = command[i + 1] if i + 1 < n else ""
            if next_ch in {"&", ">"}:
                i += 2
                continue

            j = i - 1
            while j >= 0 and command[j].isspace():
                j -= 1
            if j >= 0 and command[j] in "<>":
                i += 1
                continue

            return True

        i += 1

    return False


_SHELL_LEVEL_BACKGROUND_RE = re.compile(r"\b(?:nohup|disown|setsid)\b", re.IGNORECASE)
_LONG_LIVED_FOREGROUND_PATTERNS = (
    re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:dev|start|serve|watch)\b", re.IGNORECASE),
    re.compile(r"\bdocker\s+compose\s+up\b", re.IGNORECASE),
    re.compile(r"\bnext\s+dev\b", re.IGNORECASE),
    re.compile(r"\bvite(?:\s|$)", re.IGNORECASE),
    re.compile(r"\bnodemon\b", re.IGNORECASE),
    re.compile(r"\buvicorn\b", re.IGNORECASE),
    re.compile(r"\bgunicorn\b", re.IGNORECASE),
    re.compile(r"\bpython(?:3)?\s+-m\s+http\.server\b", re.IGNORECASE),
)
_BACKGROUND_WRAPPER_GUIDANCE = (
    "exec cannot run commands that use nohup, disown, or setsid as shell-level "
    "background wrappers. Use exec with background=true or yield_ms instead so OpenSprite "
    "can keep the session managed and inspectable."
)
_BACKGROUND_OPERATOR_GUIDANCE = (
    "exec cannot mix shell background '&' with this tool's captured stdout/stderr "
    "(the subprocess would hang or lose output). Use exec with background=true or "
    "yield_ms instead of shell '&' so the session stays managed."
)
_LONG_LIVED_FOREGROUND_GUIDANCE = (
    "This command looks like it starts a long-lived dev server or watcher; "
    "exec is meant for short foreground commands. If you want OpenSprite to keep tracking "
    "it, run the command with background=true or yield_ms and then inspect it with process."
)


def _strip_shell_quotes(token: str) -> str:
    token = str(token or "").strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
        token = token[1:-1]
    return token.strip()


def _command_basename(token: str) -> str:
    token = _strip_shell_quotes(token).replace("\\", "/")
    return token.rsplit("/", 1)[-1].lower()


def _shell_tokens(command: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if ch.isspace() or ch in ";|&()":
            i += 1
            continue
        token, next_i = _read_shell_token(command, i)
        if token:
            tokens.append(_strip_shell_quotes(token))
        i = max(next_i, i + 1)
    return tokens


def _shell_segments(command: str) -> list[str]:
    segments: list[str] = []
    start = 0
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if ch in {"'", '"'}:
            _, i = _read_shell_token(command, i)
            continue
        if ch in ";|&":
            segment = command[start:i].strip()
            if segment:
                segments.append(segment)
            if ch == "&" and i + 1 < n and command[i + 1] == "&":
                i += 2
            else:
                i += 1
            start = i
            continue
        i += 1
    tail = command[start:].strip()
    if tail:
        segments.append(tail)
    return segments


def _is_rm_recursive_or_forced(tokens: list[str], index: int) -> bool:
    flags = [token.lower() for token in tokens[index + 1 :]]
    for flag in flags:
        if flag in {"-recurse", "-recursive", "--recursive", "-force", "--force"}:
            return True
        if flag.startswith("-") and "r" in flag[1:]:
            return True
    return False


def _has_windows_delete_flags(tokens: list[str], index: int) -> bool:
    flags = {token.lower() for token in tokens[index + 1 :]}
    return bool(flags & {"/f", "/q", "/s"})


def dangerous_command_error(reason: str | None = None) -> str:
    """Build the stable tool result for a destructive shell command."""
    detail = str(reason or "").strip() or "dangerous pattern detected"
    return tool_error_result(
        f"Command blocked by safety guard: {detail}",
        error_type="ToolGuardrailError",
        category="blocked_by_policy",
        repeated_error_key=f"exec:safety_guard:{detail}",
        metadata={"tool_name": "exec", "command_policy": "destructive_command"},
    )


def _reason_from_nested_command(prefix: str, nested: str) -> str | None:
    reason = classify_destructive_shell_command(nested)
    if reason is None:
        return None
    return f"{prefix} -> {reason}"


def _first_inline_arg_after_flag(tokens: list[str], lowered: list[str], index: int, flags: set[str]) -> str | None:
    for flag_index in range(index + 1, len(lowered)):
        flag = lowered[flag_index]
        if flag in flags and flag_index + 1 < len(tokens):
            return tokens[flag_index + 1]
    return None


def _shell_wrapper_inline_command(tokens: list[str], lowered: list[str], index: int) -> str | None:
    for flag_index in range(index + 1, len(lowered)):
        flag = lowered[flag_index]
        if flag.startswith("-") and "c" in flag.lstrip("-") and flag_index + 1 < len(tokens):
            return tokens[flag_index + 1]
    return None


def _python_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _python_call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _python_constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _python_string_sequence(node: ast.AST) -> list[str] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    values: list[str] = []
    for item in node.elts:
        value = _python_constant_string(item)
        if value is None:
            return None
        values.append(value)
    return values


def _python_keyword_is_true(call: ast.Call, name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value is True
    return False


def _classify_python_inline_code(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    subprocess_calls = {
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "Popen",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _python_call_name(node.func)
        if call_name == "os.system" and node.args:
            command = _python_constant_string(node.args[0])
            if command and (reason := _reason_from_nested_command("python -c os.system", command)):
                return reason
            continue
        if call_name not in subprocess_calls or not node.args:
            continue
        command = _python_constant_string(node.args[0])
        if command and _python_keyword_is_true(node, "shell"):
            if reason := _reason_from_nested_command("python -c subprocess shell", command):
                return reason
        sequence = _python_string_sequence(node.args[0])
        if sequence:
            command = " ".join(sequence)
            if reason := _reason_from_nested_command("python -c subprocess argv", command):
                return reason
    return None


def _read_quoted_js_string(code: str, start: int) -> tuple[str | None, int]:
    quote = code[start]
    if quote not in {"'", '"'}:
        return None, start
    chars: list[str] = []
    i = start + 1
    while i < len(code):
        ch = code[i]
        if ch == "\\" and i + 1 < len(code):
            chars.append(code[i + 1])
            i += 2
            continue
        if ch == quote:
            return "".join(chars), i + 1
        chars.append(ch)
        i += 1
    return None, i


def _skip_js_string_or_comment(code: str, index: int) -> int | None:
    ch = code[index]
    if ch in {"'", '"'}:
        _, next_index = _read_quoted_js_string(code, index)
        return max(next_index, index + 1)
    if ch == "`":
        i = index + 1
        while i < len(code):
            if code[i] == "\\" and i + 1 < len(code):
                i += 2
                continue
            if code[i] == "`":
                return i + 1
            i += 1
        return i
    if code.startswith("//", index):
        newline = code.find("\n", index + 2)
        return len(code) if newline == -1 else newline + 1
    if code.startswith("/*", index):
        end = code.find("*/", index + 2)
        return len(code) if end == -1 else end + 2
    return None


def _classify_node_inline_code(code: str) -> str | None:
    i = 0
    while i < len(code):
        skipped = _skip_js_string_or_comment(code, i)
        if skipped is not None:
            i = skipped
            continue
        for function_name in ("execSync", "exec"):
            if not code.startswith(function_name, i):
                continue
            before = code[i - 1] if i > 0 else ""
            after_index = i + len(function_name)
            after = code[after_index] if after_index < len(code) else ""
            if before and (before.isalnum() or before in {"_", "$"}):
                continue
            if after and (after.isalnum() or after in {"_", "$"}):
                continue
            j = after_index
            while j < len(code) and code[j].isspace():
                j += 1
            if j >= len(code) or code[j] != "(":
                continue
            j += 1
            while j < len(code) and code[j].isspace():
                j += 1
            if j >= len(code) or code[j] not in {"'", '"'}:
                continue
            command, _ = _read_quoted_js_string(code, j)
            if command and (reason := _reason_from_nested_command(f"node -e {function_name}", command)):
                return reason
        i += 1
    return None


def classify_destructive_shell_command(command: str) -> str | None:
    """Return a stable reason when a shell command is unambiguously destructive."""
    segments = _shell_segments(command)
    if len(segments) > 1:
        for segment in segments:
            if reason := classify_destructive_shell_command(segment):
                return reason
        return None

    tokens = _shell_tokens(command)
    lowered = [token.lower() for token in tokens]
    if not lowered:
        return None
    if lowered[0] in {"echo", "printf"}:
        return None

    basenames = [_command_basename(token) for token in tokens]

    for index, token in enumerate(basenames):
        if token in {"cmd", "cmd.exe"} and index + 2 < len(lowered) and lowered[index + 1] in {"/c", "/k"}:
            nested = " ".join(tokens[index + 2 :])
            if reason := _reason_from_nested_command("cmd /c", nested):
                return reason
        if token in {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}:
            for flag_index in range(index + 1, len(lowered)):
                if lowered[flag_index] in {"-command", "-c", "/command", "/c"} and flag_index + 1 < len(tokens):
                    nested = " ".join(tokens[flag_index + 1 :])
                    if reason := _reason_from_nested_command("powershell -Command", nested):
                        return reason
        if token in {"bash", "bash.exe", "sh", "sh.exe", "zsh", "zsh.exe", "dash", "dash.exe"}:
            nested = _shell_wrapper_inline_command(tokens, lowered, index)
            if nested and (reason := _reason_from_nested_command(f"{token} -c", nested)):
                return reason
        if token in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}:
            code = _first_inline_arg_after_flag(tokens, lowered, index, {"-c"})
            if code and (reason := _classify_python_inline_code(code)):
                return reason
        if token in {"node", "node.exe"}:
            code = _first_inline_arg_after_flag(tokens, lowered, index, {"-e", "--eval"})
            if code and (reason := _classify_node_inline_code(code)):
                return reason

    for index, token in enumerate(lowered):
        if token == "git" and index + 2 < len(lowered):
            subcommand = lowered[index + 1]
            args = lowered[index + 2 :]
            if subcommand == "reset" and "--hard" in args:
                return "git reset --hard"
            if subcommand == "clean":
                clean_flags = [arg for arg in args if arg.startswith("-")]
                if any("f" in flag.lstrip("-") for flag in clean_flags):
                    return "git clean force"

        if token in {"rm", "remove-item"} and _is_rm_recursive_or_forced(lowered, index):
            return f"{token} recursive/forced delete"
        if token in {"del", "erase", "rmdir"} and _has_windows_delete_flags(lowered, index):
            return f"{token} forced delete"
        if token in {"format", "format.com", "diskpart", "mkfs", "shutdown", "reboot", "poweroff"}:
            return token
        if token == "dd" and any(arg.startswith("if=") for arg in lowered[index + 1 :]):
            return "dd raw disk copy"

    return None


def is_help_or_version_command(command: str) -> bool:
    """Return True for informational invocations that should never be blocked."""
    normalized = " ".join(command.lower().split())
    return (
        " --help" in normalized
        or normalized.endswith(" -h")
        or " --version" in normalized
        or normalized.endswith(" -v")
    )


def _foreground_exec_violation(command: str, *, allow_long_lived: bool) -> str | None:
    """Return the foreground-exec policy violation for a command, if any."""
    if _SHELL_LEVEL_BACKGROUND_RE.search(command):
        return _BACKGROUND_WRAPPER_GUIDANCE

    if has_shell_background_operator(command):
        return _BACKGROUND_OPERATOR_GUIDANCE

    if not allow_long_lived and any(pattern.search(command) for pattern in _LONG_LIVED_FOREGROUND_PATTERNS):
        return _LONG_LIVED_FOREGROUND_GUIDANCE

    return None


def foreground_exec_guidance(command: str, *, allow_long_lived: bool = False) -> str | None:
    """Return a human-readable reason to refuse exec, or None if allowed."""
    if is_help_or_version_command(command):
        return None

    return _foreground_exec_violation(command, allow_long_lived=allow_long_lived)
