import React from "react";
import { createRoot } from "react-dom/client";
import { ContextUsageIndicator } from "../../src/features/chat/ContextUsageIndicator";
import "../../src/features/chat/ChatWorkspace.css";

createRoot(document.getElementById("root")!).render(
  <main style={{ padding: 24, maxWidth: 600, margin: "80px auto", fontFamily: "sans-serif" }}>
    <h1>Context usage verification</h1>
    {[null, 0, 25, 76, 100, 105].map((percent) => (
      <div key={String(percent)} style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 16 }}>
        <span style={{ width: 80 }}>{percent === null ? "Unknown" : `${percent}%`}</span>
        <ContextUsageIndicator fallbackLimitTokens={262144} usage={percent === null ? null : {
          providerId: "openrouter", modelId: "preview", contextTokens: 262144 * percent / 100,
          contextLimitTokens: 262144, inputBudgetTokens: 196608,
        }} />
      </div>
    ))}
  </main>,
);
