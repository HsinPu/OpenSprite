"""Bounded UTF-8 Markdown with a safe, duplicate-free YAML header."""
import hashlib
import unicodedata
import yaml
from .models import SkillError


class HeaderLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise SkillError("invalid_format")
        return super().compose_node(parent, index)


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if type(key) is not str or key in result:
            raise SkillError("invalid_format")
        result[key] = loader.construct_object(value_node)
    return result


HeaderLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def parse(content: str) -> tuple[str, str, str, str]:
    try:
        data = content.encode("utf-8")
        if len(data) > 65536:
            raise SkillError("content_too_large")
        # Accept the UTF-8 signature without altering stored bytes or their hash.
        lines = content.removeprefix("\ufeff").splitlines()
        if not lines or lines[0] != "---":
            raise SkillError("invalid_format")
        end = lines.index("---", 1)
        header = yaml.load("\n".join(lines[1:end]), Loader=HeaderLoader)
        if type(header) is not dict or not {"name", "description"}.issubset(header):
            raise SkillError("invalid_format")
        name, description = header["name"], header["description"]
        if type(name) is not str or type(description) is not str:
            raise SkillError("invalid_format")
        name = unicodedata.normalize("NFC", name).strip()
        description = description.strip()
        body = "\n".join(lines[end + 1:]).strip()
        if not 1 <= len(name) <= 80 or not description or not body:
            raise SkillError("invalid_format")
        if any(unicodedata.category(c) in {"Cc", "Cs"} for c in name):
            raise SkillError("invalid_format")
        return name, description, body, hashlib.sha256(data).hexdigest()
    except (ValueError, UnicodeError, yaml.YAMLError, RecursionError):
        raise SkillError("invalid_format") from None
