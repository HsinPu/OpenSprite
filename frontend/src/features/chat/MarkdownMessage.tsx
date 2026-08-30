import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import "./MarkdownMessage.css";


type MarkdownMessageProps = {
  content: string;
};

const externalUrl = /^https?:\/\//i;

const components: Components = {
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
