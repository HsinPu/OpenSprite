import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useConversations } from "../src/features/chat/useConversations";

const conversationId = "49d6c5e3-1724-44a7-9e69-0c0103176461";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function Harness() {
  const conversations = useConversations();
  return (
    <div>
      <div data-testid="ids">{conversations.conversations.map((item) => item.id).join(",")}</div>
      <button type="button" onClick={() => conversations.recordAcceptedConversation(conversationId, "new conversation")}>accept</button>
    </div>
  );
}

describe("useConversations", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("ignores an older refresh result after a newer accepted-conversation refresh", async () => {
    const first = deferred<Response>();
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn(() => {
      calls += 1;
      if (calls === 1) return first.promise;
      return Promise.resolve(new Response(JSON.stringify({
        conversations: [{
          id: conversationId,
          workspaceId: "00000000-0000-4000-8000-000000000000",
          revision: 1,
          workspaceManagedBySchedule: false,
          title: "new conversation",
          latestMessagePreview: "new conversation",
          createdAt: "2026-08-28T08:00:00Z",
          updatedAt: "2026-08-28T08:00:00Z",
        }],
        nextCursor: null,
      })));
    }));
    render(<Harness />);

    fireEvent.click(screen.getByRole("button", { name: "accept" }));
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toContain(conversationId));
    await act(async () => {
      first.resolve(new Response(JSON.stringify({ conversations: [], nextCursor: null })));
      await first.promise;
    });

    expect(screen.getByTestId("ids").textContent).toContain(conversationId);
  });
});
