export type SettingsSection = "general" | "models";

export type DemoSettings = {
  language: string;
  timezone: string;
  newConversation: boolean;
  restoreConversation: boolean;
  sendMode: string;
  taskNotifications: boolean;
  confirmNotifications: boolean;
  sound: boolean;
};

export const defaultDemoSettings: DemoSettings = {
  language: "繁體中文",
  timezone: "依照系統設定",
  newConversation: true,
  restoreConversation: false,
  sendMode: "Enter 送出，Shift + Enter 換行",
  taskNotifications: true,
  confirmNotifications: true,
  sound: false,
};
