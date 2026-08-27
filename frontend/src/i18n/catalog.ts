import { enMessages } from "./locales/en";
import { jaMessages } from "./locales/ja";
import { zhTWMessages, type MessageKey } from "./locales/zh-TW";

export const supportedLocales = ["zh-TW", "en", "ja"] as const;

export type Locale = typeof supportedLocales[number];
export type TranslationVariables = Readonly<Record<string, string | number>>;
export type Translator = (key: MessageKey, variables?: TranslationVariables) => string;

export const localeLabels: Record<Locale, string> = {
  "zh-TW": "繁體中文",
  en: "English",
  ja: "日本語",
};

export function isLocale(value: string): value is Locale {
  return supportedLocales.some((locale) => locale === value);
}

const catalogs: Record<Locale, Record<MessageKey, string>> = {
  "zh-TW": zhTWMessages,
  en: enMessages,
  ja: jaMessages,
};

function interpolate(message: string, variables: TranslationVariables = {}): string {
  return message.replace(/\{([A-Za-z][A-Za-z0-9]*)\}/g, (placeholder, name: string) => (
    Object.hasOwn(variables, name) ? String(variables[name]) : placeholder
  ));
}

export function createTranslator(locale: Locale): Translator {
  return (key, variables) => interpolate(catalogs[locale][key] ?? zhTWMessages[key], variables);
}

export const defaultTranslator = createTranslator("zh-TW");

export type { MessageKey };
