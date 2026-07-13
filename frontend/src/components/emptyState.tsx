import { Button } from "antd";

export interface EmptyStateCopy {
  empty: {
    ariaLabel: string;
    title: string;
    description: string;
  };
}

export interface PromptOption {
  title: string;
  description: string;
  text: string;
}

export function EmptyState({
  copy,
  prompts,
  applyPrompt,
}: {
  copy: EmptyStateCopy;
  prompts: PromptOption[];
  applyPrompt: (text: string) => void;
}) {
  return (
    <section className="empty-state" aria-label={copy.empty.ariaLabel}>
      <div className="empty-state__mark" aria-hidden="true">OS</div>
      <h1>{copy.empty.title}</h1>
      <p>{copy.empty.description}</p>
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <Button key={prompt.title} className="prompt-card" type="text" onClick={() => applyPrompt(prompt.text)}>
            <strong>{prompt.title}</strong>
            <span>{prompt.description}</span>
          </Button>
        ))}
      </div>
    </section>
  );
}
