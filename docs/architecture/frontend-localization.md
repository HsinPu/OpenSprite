# Frontend localization

## Boundary

OpenSprite frontend owns one typed localization boundary under `src/i18n/`.
The supported locale identifiers are `zh-TW`, `en` and `ja`; Traditional
Chinese is the default and fallback catalog.

Locale catalogs contain only presentation text. Components request stable keys
through `useI18n()` and never use translated copy as application state, a DOM id,
an API value or a persistence key. Interpolation accepts only explicit bounded
variables. TypeScript requires the English and Japanese catalogs to implement
every key present in the Traditional Chinese source catalog.

## Runtime behavior

- The General settings language selector changes the locale for the current
  browser session.
- The document `lang`, React copy, Ant Design locale, API error text and
  `Intl.DateTimeFormat` locale change together.
- Locale state is not written to localStorage, the URL, `.opensprite` or the
  backend AI settings contract.
- General timezone and send-mode preferences use stable identifiers rather than
  translated option labels.
- Provider names, model identifiers, user messages and model responses are
  content and are not translated.

No supported locale currently requires right-to-left layout. A future RTL
locale must add an explicit document direction and responsive visual checks in
the same implementation slice.
