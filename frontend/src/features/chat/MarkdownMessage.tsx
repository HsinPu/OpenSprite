import { isValidElement, useState, type ReactNode } from "react";
import { Button } from "antd";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { useI18n } from "../../i18n/I18nProvider";
import "./MarkdownMessage.css";


type MarkdownMessageProps = {
  content: string;
};

type CodeBlockProps = {
  children: ReactNode;
};

function textContent(value: ReactNode): string {
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(textContent).join("");
  if (isValidElement<{ children?: ReactNode }>(value)) return textContent(value.props.children);
  return "";
}

function CodeBlock({ children }: CodeBlockProps) {
  const { t } = useI18n();
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");
  const label = status === "copied" ? t("chat.copiedCode") : status === "failed" ? t("chat.copyCodeFailed") : t("chat.copyCode");
  const code = textContent(children).replace(/\n$/, "");

  const copy = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(code);
      setStatus("copied");
    } catch {
      setStatus("failed");
    }
  };

  return (
    <div className="markdown-message__code-block">
      <Button
        type="text"
        size="small"
        className="markdown-message__copy-button"
        aria-label={label}
        title={label}
        onClick={() => void copy()}
      >
        {label}
      </Button>
      <pre>{children}</pre>
      <span className="markdown-message__copy-status" role="status" aria-live="polite">
        {status === "copied" ? t("chat.copiedCode") : status === "failed" ? t("chat.copyCodeFailed") : ""}
      </span>
    </div>
  );
}

const externalUrl = /^https?:\/\//i;

const components: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  a: ({ children, href, title }) => {
    if (!href) return <span>{children}</span>;
    const external = externalUrl.test(href);
    return (
      <a
        href={href}
        title={title}
        target={external ? "_blank" : undefined}
        rel={external ? "noreferrer noopener" : undefined}
      >
        {children}
      </a>
    );
  },
  img: ({ alt, title }) => (
    alt ? <span className="markdown-message__image-alt" title={title}>{alt}</span> : null
  ),
};

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <div className="markdown-message">
      <ReactMarkdown components={components} remarkPlugins={[remarkGfm]} skipHtml>
        {content}
      </ReactMarkdown>
    </div>
  );
}
