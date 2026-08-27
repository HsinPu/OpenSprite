export type SettingsSection = "general" | "models";

export type DemoSettings = {
  newConversation: boolean;
  restoreConversation: boolean;
  sendMode: "enter" | "ctrl-enter";
  taskNotifications: boolean;
  confirmNotifications: boolean;
  sound: boolean;
};

export const defaultDemoSettings: DemoSettings = {
  newConversation: true,
  restoreConversation: false,
  sendMode: "enter",
  taskNotifications: true,
  confirmNotifications: true,
  sound: false,
};
