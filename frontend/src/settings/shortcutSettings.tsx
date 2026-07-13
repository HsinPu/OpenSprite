import { SettingsCard, SettingsRow } from "./settingsPrimitives";

type ShortcutSettingsCopy = {
  settings: {
    shortcuts?: {
      openSettings?: string;
      openSettingsDescription?: string;
      sendMessage?: string;
      sendMessageDescription?: string;
    };
  };
};

export function ShortcutSettings({ copy }: { copy: ShortcutSettingsCopy }) {
  return (
    <section className="settings-page">
      <SettingsCard>
        <SettingsRow title={copy.settings.shortcuts?.openSettings || "Open settings"} description={copy.settings.shortcuts?.openSettingsDescription || ""}>
          <div className="shortcut-keys"><kbd>Ctrl</kbd><kbd>,</kbd></div>
        </SettingsRow>
        <SettingsRow title={copy.settings.shortcuts?.sendMessage || "Send message"} description={copy.settings.shortcuts?.sendMessageDescription || ""}>
          <div className="shortcut-keys"><kbd>Enter</kbd></div>
        </SettingsRow>
      </SettingsCard>
    </section>
  );
}
