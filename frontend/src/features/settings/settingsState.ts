export type SettingsSection = "general" | "models";

export type DemoSettings = {
  timezone: "system" | "asia-taipei" | "utc";
  newConversation: boolean;
  restoreConversation: boolean;
  sendMode: "enter" | "ctrl-enter";
  taskNotifications: boolean;
  confirmNotifications: boolean;
  sound: boolean;
};

export const defaultDemoSettings: DemoSettings = {
  timezone: "system",
  newConversation: true,
  restoreConversation: false,
  sendMode: "enter",
  taskNotifications: true,
  confirmNotifications: true,
  sound: false,
};
