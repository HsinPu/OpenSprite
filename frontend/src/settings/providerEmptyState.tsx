export function ProviderEmptyState({ title, description = "" }: { title: string; description?: string }) {
  return (
    <div className="provider-row provider-row--empty">
      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
    </div>
  );
}
