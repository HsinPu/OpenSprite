import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownMessage } from "../src/features/chat/MarkdownMessage";


describe("MarkdownMessage", () => {
  it("renders common Markdown and GFM without changing the source string", () => {
    const content = [
      "**粗體**",
      "",
      "- 項目一",
      "- 項目二",
      "",
      "~~刪除~~",
      "",
      "`inline`",
      "",
      "```ts",
      "const answer = 42;",
      "```",
    ].join("\n");

    const { container } = render(<MarkdownMessage content={content} />);

    expect(screen.getByText("粗體").tagName).toBe("STRONG");
    expect(screen.getByText("項目一").closest("ul")).toBeTruthy();
    expect(screen.getByText("刪除").tagName).toBe("DEL");
    expect(screen.getByText("inline").tagName).toBe("CODE");
    expect(container.querySelector("pre code")?.textContent).toContain("const answer = 42;");
    expect(content).toContain("**粗體**");
  });

  it("keeps links safe and never loads Markdown images or raw HTML", () => {
    render(
      <MarkdownMessage
        content={'[官方網站](https://example.com) [危險連結](javascript:alert(1)) ![遠端圖片](https://example.com/tracker.png) <script>alert("xss")</script>'}
      />,
    );

    const safeLink = screen.getByRole("link", { name: "官方網站" });
    expect(safeLink.getAttribute("href")).toBe("https://example.com");
    expect(safeLink.getAttribute("target")).toBe("_blank");
    expect(safeLink.getAttribute("rel")).toBe("noreferrer noopener");
    expect(screen.queryByRole("link", { name: "危險連結" })).toBeNull();
    expect(screen.getByText("危險連結")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("遠端圖片")).toBeTruthy();
    expect(document.querySelector("script")).toBeNull();
  });
});
