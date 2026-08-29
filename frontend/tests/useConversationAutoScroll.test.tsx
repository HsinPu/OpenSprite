import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useConversationAutoScroll } from "../src/features/chat/useConversationAutoScroll";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

type HarnessProps = {
  enabled: boolean;
  loading: boolean;
  messageCount: number;
  streamedText: string;
  showLiveAssistant?: boolean;
  loadOlder?: () => Promise<void>;
};

function Harness({ enabled, loading, messageCount, streamedText, showLiveAssistant = false, loadOlder = async () => undefined }: HarnessProps) {
  const scrolling = useConversationAutoScroll({
    enabled,
    conversationId: "49d6c5e3-1724-44a7-9e69-0c0103176461",
    loading,
    messageCount,
    streamedText,
    showLiveAssistant,
  });
  return <div>
    <div data-testid="scroll-owner" ref={scrolling.containerRef} onScroll={scrolling.onScroll} />
    <button type="button" onClick={scrolling.followLatest}>send</button>
    <button type="button" onClick={() => void scrolling.preservePositionWhilePrepending(loadOlder)}>older</button>
  </div>;
}

function setMetrics(element: HTMLElement, { scrollHeight, clientHeight, scrollTop }: { scrollHeight: number; clientHeight: number; scrollTop: number }) {
  Object.defineProperty(element, "scrollHeight", { configurable: true, value: scrollHeight });
  Object.defineProperty(element, "clientHeight", { configurable: true, value: clientHeight });
  element.scrollTop = scrollTop;
}

beforeEach(() => {
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => { callback(0); return 1; });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
});

afterEach(() => vi.unstubAllGlobals());

describe("useConversationAutoScroll", () => {
  it("positions an opened conversation at the latest message and follows an explicit send", () => {
    const { rerender } = render(<Harness enabled loading messageCount={10} streamedText="" />);
    const owner = screen.getByTestId("scroll-owner");
    setMetrics(owner, { scrollHeight: 1000, clientHeight: 300, scrollTop: 0 });

    rerender(<Harness enabled loading={false} messageCount={10} streamedText="" />);
    expect(owner.scrollTop).toBe(1000);

    owner.scrollTop = 100;
    fireEvent.scroll(owner);
    fireEvent.click(screen.getByRole("button", { name: "send" }));
    expect(owner.scrollTop).toBe(1000);
  });

  it("follows streaming output near the bottom but pauses and resumes around manual scrolling", () => {
    const { rerender } = render(<Harness enabled loading messageCount={10} streamedText="" />);
    const owner = screen.getByTestId("scroll-owner");
    setMetrics(owner, { scrollHeight: 1000, clientHeight: 300, scrollTop: 0 });
    rerender(<Harness enabled loading={false} messageCount={10} streamedText="" />);

    setMetrics(owner, { scrollHeight: 1100, clientHeight: 300, scrollTop: 800 });
    fireEvent.scroll(owner);
    rerender(<Harness enabled loading={false} messageCount={10} streamedText="a" showLiveAssistant />);
    expect(owner.scrollTop).toBe(1100);

    owner.scrollTop = 100;
    fireEvent.scroll(owner);
    Object.defineProperty(owner, "scrollHeight", { configurable: true, value: 1200 });
    rerender(<Harness enabled loading={false} messageCount={10} streamedText="ab" showLiveAssistant />);
    expect(owner.scrollTop).toBe(100);

    owner.scrollTop = 900;
    fireEvent.scroll(owner);
    Object.defineProperty(owner, "scrollHeight", { configurable: true, value: 1300 });
    rerender(<Harness enabled loading={false} messageCount={10} streamedText="abc" showLiveAssistant />);
    expect(owner.scrollTop).toBe(1300);
  });

  it("does not follow sends or streaming output when disabled", () => {
    const { rerender } = render(<Harness enabled={false} loading messageCount={10} streamedText="" />);
    const owner = screen.getByTestId("scroll-owner");
    setMetrics(owner, { scrollHeight: 1000, clientHeight: 300, scrollTop: 0 });
    rerender(<Harness enabled={false} loading={false} messageCount={10} streamedText="" />);
    expect(owner.scrollTop).toBe(1000);

    owner.scrollTop = 100;
    fireEvent.click(screen.getByRole("button", { name: "send" }));
    Object.defineProperty(owner, "scrollHeight", { configurable: true, value: 1200 });
    rerender(<Harness enabled={false} loading={false} messageCount={11} streamedText="reply" showLiveAssistant />);
    expect(owner.scrollTop).toBe(100);
  });

  it("preserves the visible position while older messages are prepended", async () => {
    const load = deferred();
    const { rerender } = render(<Harness enabled loading messageCount={10} streamedText="" loadOlder={() => load.promise} />);
    const owner = screen.getByTestId("scroll-owner");
    setMetrics(owner, { scrollHeight: 1000, clientHeight: 300, scrollTop: 0 });
    rerender(<Harness enabled loading={false} messageCount={10} streamedText="" loadOlder={() => load.promise} />);

    owner.scrollTop = 120;
    fireEvent.scroll(owner);
    fireEvent.click(screen.getByRole("button", { name: "older" }));
    Object.defineProperty(owner, "scrollHeight", { configurable: true, value: 1400 });
    await act(async () => load.resolve());

    expect(owner.scrollTop).toBe(520);
  });
});
