import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  createTranslator,
  defaultTranslator,
  type Locale,
  type Translator,
} from "./catalog";

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Translator;
};

const defaultContext: I18nContextValue = {
  locale: "zh-TW",
  setLocale: () => undefined,
  t: defaultTranslator,
};

const I18nContext = createContext<I18nContextValue>(defaultContext);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>("zh-TW");
  const value = useMemo<I18nContextValue>(() => ({
    locale,
    setLocale,
    t: createTranslator(locale),
  }), [locale]);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  return useContext(I18nContext);
}
