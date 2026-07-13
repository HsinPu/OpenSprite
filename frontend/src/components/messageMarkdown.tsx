import React from "react";

export type MessageCopy = {
  message: {
    assistantAvatar?: string;
    artifactTypes?: Record<string, string>;
    jsonArray: (count: number) => string;
    jsonObject: (keys: string, count: number) => string;
    jsonTitle: string;
    jsonValue: string;
    userAvatar?: string;
    viewTrace?: string;
  };
  run?: {
    statusLabels?: Record<string, string>;
  };
};

type MessageSegment =
  | { id: string; type: "text" | "code" | "strong"; text: string }
  | { id: string; type: "link"; text: string; href: string };

type MessageListItem = {
  id: string;
  text: string;
  segments: MessageSegment[];
};

type MessageTableCell = {
  id: string;
  text: string;
};

type MessageTableRow = {
  id: string;
  cells: MessageTableCell[];
};

export type MessageBlock =
  | { id: string; type: "heading"; level: number; text: string; segments: MessageSegment[] }
  | { id: string; type: "list"; ordered: boolean; items: MessageListItem[] }
  | { id: string; type: "quote"; segments: MessageSegment[] }
  | { id: string; type: "code"; language: string; code: string }
  | { id: string; type: "json"; summary: string; code: string }
  | { id: string; type: "table"; headers: MessageTableCell[]; rows: MessageTableRow[] }
  | { id: string; type: "rule" }
  | { id: string; type: "paragraph"; text: string; segments: MessageSegment[] };

export function MessageTextRenderer({ blocks, copy }: { blocks: MessageBlock[]; copy: MessageCopy }) {
  return (
    <div className="message__rendered">
      {blocks.map((block) => {
        if (block.type === "heading") {
          if (block.level <= 1) {
            return <h3 key={block.id}>{renderSegments(block.segments)}</h3>;
          }
          if (block.level === 2) {
            return <h4 key={block.id}>{renderSegments(block.segments)}</h4>;
          }
          return <h5 key={block.id}>{renderSegments(block.segments)}</h5>;
        }
        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          return (
            <ListTag key={block.id}>
              {block.items.map((item) => (
                <li key={item.id}>{renderSegments(item.segments)}</li>
              ))}
            </ListTag>
          );
        }
        if (block.type === "quote") {
          return <blockquote key={block.id}>{renderSegments(block.segments)}</blockquote>;
        }
        if (block.type === "code") {
          return (
            <pre key={block.id} className="message__code-block">
              <code>{block.code}</code>
            </pre>
          );
        }
        if (block.type === "json") {
          return (
            <details key={block.id} className="message__json-card">
              <summary>
                <strong>{copy.message.jsonTitle}</strong>
                <span>{block.summary}</span>
              </summary>
              <pre>{block.code}</pre>
            </details>
          );
        }
        if (block.type === "table") {
          return (
            <div key={block.id} className="message__table-wrap">
              <table className="message__table">
                <thead>
                  <tr>
                    {block.headers.map((header) => (
                      <th key={header.id}>{header.text}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row) => (
                    <tr key={row.id}>
                      {row.cells.map((cell) => (
                        <td key={cell.id}>{cell.text}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (block.type === "rule") {
          return <hr key={block.id} className="message__rule" />;
        }
        return <p key={block.id}>{renderSegments(block.segments)}</p>;
      })}
    </div>
  );
}

export function buildMessageBlocks(copy: MessageCopy, value: unknown, keyPrefix: string): MessageBlock[] {
  const text = String(value || "").replace(/\r\n/g, "\n").trim();
  if (!text) {
    return [];
  }
  const jsonBlock = maybeJsonBlock(copy, text, `${keyPrefix}:json`);
  if (jsonBlock) {
    return [jsonBlock];
  }
  return parseMarkdownBlocks(copy, text, keyPrefix);
}

function maybeJsonBlock(copy: MessageCopy, text: string, id: string): MessageBlock | null {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
    return null;
  }
  try {
    const parsed = JSON.parse(trimmed);
    return {
      id,
      type: "json",
      summary: jsonSummary(copy, parsed),
      code: JSON.stringify(parsed, null, 2),
    };
  } catch {
    return null;
  }
}

function jsonSummary(copy: MessageCopy, value: unknown) {
  if (Array.isArray(value)) {
    return copy.message.jsonArray(value.length);
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    return copy.message.jsonObject(keys.slice(0, 4).join(", "), keys.length);
  }
  return copy.message.jsonValue;
}

function parseMarkdownBlocks(copy: MessageCopy, text: string, keyPrefix: string): MessageBlock[] {
  const lines = text.split("\n");
  const blocks: MessageBlock[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();
    if (!trimmed) {
      index += 1;
      continue;
    }
    if (isMarkdownRule(trimmed)) {
      blocks.push({ id: `${keyPrefix}:rule-${blocks.length}`, type: "rule" });
      index += 1;
      continue;
    }
    const fence = trimmed.match(/^```([A-Za-z0-9_-]*)\s*$/);
    if (fence) {
      const language = fence[1] || "";
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push(codeBlock(copy, codeLines.join("\n"), language, `${keyPrefix}:code-${blocks.length}`));
      continue;
    }
    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      blocks.push({
        id: `${keyPrefix}:heading-${blocks.length}`,
        type: "heading",
        level: heading[1].length,
        text: heading[2].trim(),
        segments: inlineSegments(heading[2].trim(), `${keyPrefix}:heading-${blocks.length}`),
      });
      index += 1;
      continue;
    }
    if (isMarkdownTable(lines, index)) {
      const tableLines = [lines[index]];
      index += 2;
      while (index < lines.length && lines[index].includes("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      blocks.push(tableBlock(tableLines, `${keyPrefix}:table-${blocks.length}`));
      continue;
    }
    const unordered = trimmed.match(/^[-*]\s+(.+)$/);
    const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      const orderedList = Boolean(ordered);
      const items: MessageListItem[] = [];
      while (index < lines.length) {
        const itemMatch = lines[index].trim().match(orderedList ? /^\d+[.)]\s+(.+)$/ : /^[-*]\s+(.+)$/);
        if (!itemMatch) {
          break;
        }
        const itemText = itemMatch[1].trim();
        items.push({
          id: `${keyPrefix}:list-${blocks.length}-${items.length}`,
          text: itemText,
          segments: inlineSegments(itemText, `${keyPrefix}:list-${blocks.length}-${items.length}`),
        });
        index += 1;
      }
      blocks.push({ id: `${keyPrefix}:list-${blocks.length}`, type: "list", ordered: orderedList, items });
      continue;
    }
    const paragraphLines: string[] = [];
    while (index < lines.length && !isBlockStart(lines, index)) {
      if (!lines[index].trim()) {
        break;
      }
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    const paragraph = paragraphLines.join(" ").trim();
    if (paragraph) {
      blocks.push({
        id: `${keyPrefix}:paragraph-${blocks.length}`,
        type: "paragraph",
        text: paragraph,
        segments: inlineSegments(paragraph, `${keyPrefix}:paragraph-${blocks.length}`),
      });
    }
  }
  return blocks;
}

function codeBlock(copy: MessageCopy, code: string, language: string, id: string): MessageBlock {
  const jsonBlock = language.toLowerCase() === "json" ? maybeJsonBlock(copy, code, id) : null;
  if (jsonBlock) {
    return jsonBlock;
  }
  return { id, type: "code", language, code };
}

function isBlockStart(lines: string[], index: number) {
  const trimmed = lines[index]?.trim() || "";
  if (!trimmed) {
    return false;
  }
  return (
    isMarkdownRule(trimmed) ||
    /^```/.test(trimmed) ||
    /^(#{1,3})\s+/.test(trimmed) ||
    /^[-*]\s+/.test(trimmed) ||
    /^\d+[.)]\s+/.test(trimmed) ||
    /^>\s?/.test(trimmed) ||
    isMarkdownTable(lines, index)
  );
}

function isMarkdownRule(trimmed: string) {
  return /^(?:-{3,}|\*{3,}|_{3,})$/.test(String(trimmed || "").replace(/\s+/g, ""));
}

function isMarkdownTable(lines: string[], index: number) {
  const current = lines[index]?.trim() || "";
  const next = lines[index + 1]?.trim() || "";
  return current.includes("|") && /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(next);
}

function tableBlock(tableLines: string[], id: string): MessageBlock {
  const headers = splitTableRow(tableLines[0]).map((text, index) => ({ id: `${id}:h-${index}`, text }));
  const rows = tableLines.slice(1).map((line, rowIndex) => {
    const cells = splitTableRow(line).map((text, cellIndex) => ({ id: `${id}:r-${rowIndex}-${cellIndex}`, text }));
    return { id: `${id}:r-${rowIndex}`, cells };
  });
  return { id, type: "table", headers, rows };
}

function splitTableRow(line: string) {
  return String(line || "")
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function inlineSegments(text: string, idPrefix: string): MessageSegment[] {
  const segments: MessageSegment[] = [];
  const pattern = /(`[^`]+`)|(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))|(\*\*([^*\n][\s\S]*?[^*\n])\*\*)/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      segments.push({ id: `${idPrefix}:t-${segments.length}`, type: "text", text: text.slice(cursor, match.index) });
    }
    if (match[1]) {
      segments.push({ id: `${idPrefix}:c-${segments.length}`, type: "code", text: match[1].slice(1, -1) });
    } else if (match[2]) {
      segments.push({ id: `${idPrefix}:l-${segments.length}`, type: "link", text: match[3], href: match[4] });
    } else {
      segments.push({ id: `${idPrefix}:s-${segments.length}`, type: "strong", text: match[6] });
    }
    cursor = pattern.lastIndex;
  }
  if (cursor < text.length) {
    segments.push({ id: `${idPrefix}:t-${segments.length}`, type: "text", text: text.slice(cursor) });
  }
  return segments.length ? segments : [{ id: `${idPrefix}:t-0`, type: "text", text }];
}

function renderSegments(segments: MessageSegment[] = []) {
  return segments.map((segment) => {
    if (segment.type === "code") {
      return <code key={segment.id}>{segment.text}</code>;
    }
    if (segment.type === "link") {
      return (
        <a key={segment.id} href={segment.href} target="_blank" rel="noreferrer">
          {segment.text}
        </a>
      );
    }
    if (segment.type === "strong") {
      return <strong key={segment.id}>{segment.text}</strong>;
    }
    return <React.Fragment key={segment.id}>{segment.text}</React.Fragment>;
  });
}
