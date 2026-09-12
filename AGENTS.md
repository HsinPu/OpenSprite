# OpenSprite repository instructions

## Current direction

- OpenSprite is being rebuilt from a clean repository foundation.
- The repository now contains a runnable React frontend and a minimal Python
  backend for local Provider connections and encrypted credential persistence.
- Continue to add backend capabilities only from an explicitly approved
  frontend workflow or contract; do not restore speculative archived behavior.
- Do not add an application CLI, command shim, Typer, Click, or argparse command suite.
- The archived implementation at `codex/archive-main-before-refactor-20260820` is read-only reference material. Never restore it wholesale.

## Repository boundaries

- `frontend/` owns browser UI source, frontend tests, and frontend build configuration.
- `backend/` owns the Python local service, encrypted persistence adapters and
  backend tests.
- `contracts/` owns authoritative frontend/backend HTTP and future WebSocket
  contracts.
- `installers/` will own separate Linux and Windows installation implementations with matching behavior.
- `docs/architecture/` records durable architecture decisions.
- `docs/changes/` records every implementation slice and its verification evidence.
- `scripts/` is reserved for repository verification and maintenance automation.

Keep business behavior out of shared configuration, installer, and documentation boundaries. Do not create generic dumping grounds such as broad `utils`, `helpers`, or `services` directories.

## Local user-data boundary

- `%USERPROFILE%\.opensprite` on Windows and `~/.opensprite` on Linux are the sole OpenSprite user-data roots.
- All future conversations, databases, uploaded attachments, generated outputs, memory, state, logs, and cache must remain below that root and use the mapping owned by `backend/src/opensprite_backend/app_paths.py`.
- Do not introduce a second product-data root, persist absolute user-profile paths in the database, or let individual features construct their own home-directory paths.
- Program installation remains separate. Provider API keys are stored only as
  AES-256-GCM ciphertext in `.opensprite/auth.json`, using the random
  per-install key in `.opensprite/config/credential.key`.
- Never add plaintext credential persistence, OS-keyring fallback, a fixed
  application-wide encryption key, secret logging, or API responses containing
  raw credentials. Treat the complete `.opensprite` root as sensitive because
  possession of both encrypted data and `credential.key` permits decryption.
- Backup, restore, move and delete `auth.json` and `credential.key` together.
- Only one desktop backend process may write a user-data root; do not enable
  multiple Uvicorn workers or a reloader against one `.opensprite`.
- Do not create reserved directories until an implemented feature performs its first real write.

## Change workflow

1. Keep each change focused on one approved objective.
2. Update or add a matching record under `docs/changes/` in the same commit.
3. Add abstractions only when current behavior requires them.
4. Run the narrowest real verification that exists, followed by broader checks when available.
5. Use English Conventional Commit subjects and create one independently reviewable commit per slice.

Do not add compatibility aliases, disabled legacy paths, keyword-based task routing, or speculative lifecycle layers unless a new approved requirement explicitly needs them.

## Current verification

The frontend now contains a runnable fake-data demo. Run these frontend checks:

```powershell
cd frontend
npm ci --ignore-scripts
npm test -- --run
npm run typecheck
npm run build
npm run dev
```

Backend checks:

```powershell
cd backend
uv sync --dev
uv run pytest -W error
uv run python -m compileall -q src tests
uv lock --check --offline
uv pip check
```

Repository checks:

```powershell
git diff --check
git status --short --branch
```

Windows installer checks:

```powershell
./installers/windows/test.ps1
```

Browser verification remains manual against the local Vite server or installed
single-origin runtime. Frontend, backend, API contract and Windows installer
isolation tests are committed; Linux installer execution tests do not exist yet
and must not be claimed.

## Generated and local files

- Commit `frontend/package-lock.json` whenever frontend dependencies change.
- Never commit `node_modules`, `dist`, Python virtual environments, caches,
  logs, `.opensprite`, `auth.json`, `credential.key`, raw credentials, `.codex`,
  or `.codegraph`.
- `.agents/` is intentionally not ignored so future repository skills can be reviewed and committed deliberately.
- Never delete user data, credentials, databases, or installation directories without explicit approval and verified absolute paths.

## Frontend engineering, UI/UX, and design standards

These rules apply to all AI coding agents (including Codex) and human developers
creating, modifying, refactoring, or reviewing frontend code unless explicitly
instructed otherwise.

### 1. Product philosophy

Use React, TypeScript, and Ant Design. Aim for a mature enterprise application,
operational tool, dashboard, admin interface, or professional SaaS product:
quiet, precise, modern, compact, information-dense, fast, clear, work-focused,
visually restrained, consistent, and suitable for daily use.

The formula is **Stripe data discipline + Linear visual restraint + Ant Design
implementation**.

- Reference Stripe for tables, forms, settings, billing-like layouts, data,
  statuses, details, KPI, and structured workflows.
- Reference Linear for sidebar, navigation, toolbar, lists, typography, spacing,
  interaction density, keyboard efficiency, and low-noise layouts.
- Use only interaction, hierarchy, layout, and information-design principles.
  Do not copy proprietary logos, branding, illustrations, trademarks, or copy.
- Prefer productivity over decoration. Do not turn the product into a marketing
  landing page, AI startup homepage, Dribbble concept, neon/gaming UI, or
  glassmorphism demo.

### 2. Ant Design and component reuse

Use Ant Design whenever an appropriate component exists:

- Controls: Button, Input, Input.Search, InputNumber, Select, AutoComplete,
  Checkbox, Radio, Switch, Slider, DatePicker, TimePicker, Upload.
- Data/forms: Form, Table, Pagination.
- Overlays: Modal, Drawer, Popconfirm, Popover, Tooltip, Dropdown.
- Navigation: Menu, Tabs, Steps, Breadcrumb.
- Feedback/presentation: Alert, Tag, Badge, Avatar, Empty, Result, Skeleton,
  Spin, Progress, notification, message.

Do not recreate buttons, inputs, selects, modals, tables, forms, dropdowns, or
date pickers unless a clear requirement cannot be satisfied by Ant Design.

Do not introduce another major UI library without an explicit request, including
Material UI, shadcn/ui, Chakra UI, Mantine, Bootstrap UI, PrimeReact, or Semantic UI.
Avoid duplicated controls, inconsistent appearance/UX/theming, bundle growth,
and unnecessary maintenance.

Before creating components, search for existing page headers, table/form wrappers,
toolbars, status tags, modal/drawer patterns, empty states, and layouts. Reuse
reasonable patterns. Keep one-off implementations simple; extract repeated
patterns when useful, not prematurely. Avoid universal, overly flexible components.

### 3. Theme and styling authority

Inspect and reuse the existing theme first. Preserve intentional brand decisions
and equivalent tokens. Do not duplicate theme configurations or blindly overwrite
them. The blue example below is a fallback, not an instruction to recolor OpenSprite.

Prefer styling in this order:

1. Ant Design ConfigProvider.
2. Global design tokens.
3. Component tokens.
4. Ant Design component props.
5. Existing shared style system.
6. Component-level CSS when necessary.

If no equivalent theme exists, use this default direction:

```tsx
import type { ThemeConfig } from 'antd';

export const appTheme: ThemeConfig = {
  token: {
    colorPrimary: '#2563eb',
    colorBgBase: '#ffffff',
    colorBgLayout: '#f8f9fb',
    colorText: '#1f2328',
    colorTextSecondary: '#667085',
    colorBorder: '#dfe3e8',
    colorBorderSecondary: '#eceff3',
    borderRadius: 6,
    fontSize: 14,
  },
  components: {
    Button: { borderRadius: 6, controlHeight: 32 },
    Input: { borderRadius: 6, controlHeight: 32 },
    Select: { borderRadius: 6, controlHeight: 32 },
    Table: {
      headerBg: '#f8f9fb',
      headerColor: '#475467',
      borderColor: '#eceff3',
    },
    Card: { borderRadiusLG: 8 },
    Modal: { borderRadiusLG: 8 },
  },
};
```

Avoid repeated hardcoded token equivalents, excessive inline styles, and broad
or deep Ant Design internal `.ant-*` overrides. Small one-off layout adjustments
may be acceptable; reusable styling belongs in the existing style system.

Avoid `!important` unless no cleaner option exists. Repeated need for it requires
investigating selectors, theme configuration, component misuse, or style
architecture and fixing the underlying cause.

### 4. Visual foundations

- Prefer white surfaces, light neutral backgrounds, neutral gray borders, dark
  primary text, muted secondary text, and one controlled accent.
- Approximate balance: 80% neutral, 15% structural hierarchy, 5% accent.
- Use color for primary actions, selection, success, warning, error, information,
  status, or meaningful highlights, not decoration. Status colors must be
  consistent and restrained: subtle backgrounds, soft borders, muted text.
- Create hierarchy in this order: typography, spacing, alignment, border,
  background, color, shadow.
- Prefer thin, subtle neutral borders/separators for tables, panels, toolbars,
  input boundaries, and section hierarchy.
- Reserve shadows for Modal, Dropdown, Popover, floating overlays, and context
  menus. Normal content uses spacing, borders, background contrast, and type.
  Avoid unnecessary border + heavy shadow + glow + gradient combinations.
- Recommended radii: Button/Input/Select 6px; Dropdown/Card 6–8px; Modal about
  8px. Avoid 16/20/24/32px as defaults and excessive pill shapes.
- Reuse existing spacing; prefer 4, 8, 12, 16, 20, 24, 32, 40, 48 over arbitrary
  values such as 13, 17, 19, 23, 29.
- Typography: body 14–16px, secondary 12–14px, page titles 20–28px. Avoid
  unnecessary 48/64/72px headings in enterprise tools.
- Use page title, section, subsection, body, secondary, caption levels; combine
  size, weight, color, and spacing instead of making every level bold.
- Default to medium-to-high density without crowding. Avoid tall rows, oversized
  controls/buttons, loose forms, large empty areas, and oversized headers.

Unless explicitly requested, avoid purple-blue/rainbow gradients, neon, glow,
glassmorphism, large blur, decorative blobs/light orbs, oversized heroes,
marketing banners, decorative illustrations, huge headings, excessive whitespace,
card walls/nested cards, huge radii, excessive pills, heavy shadows, decorative
animation, and emoji as primary UI icons.

### 5. Layout and navigation

- Reuse page layouts rather than reinventing them. Typical management structure:
  global navigation → page header → toolbar/actions → filters → main content →
  pagination/footer. This pattern does not require an unnecessary top bar.
- Keep sidebar navigation compact, quiet, hierarchical, and scannable; use
  consistent icons/labels and muted group labels. Avoid colorful icons, per-item
  cards, and heavy separators.
- Prefer subtle neutral selection with stronger text, not saturated blocks with
  white text/shadow unless branding requires it.
- Keep top bars simple: breadcrumbs, search, global actions, user menu, and
  notifications when useful.
- Headers contain title, optional functional description, primary action, and
  secondary actions; avoid promotional welcome messages.
- Keep navigation predictable: users should know where they are, where they can
  go, and what to do next. Do not change patterns for visual novelty.
- Use compact, quiet toolbars and row-based lists with muted metadata, subtle
  hover, fast scanning, and keyboard support when appropriate.
- Prefer simple Ant Design Tabs; avoid huge, colorful, card, or pill tabs as
  defaults.

### 6. Actions, copy, and feedback

- Usually provide one obvious primary action. Use default/text/link/dropdown
  styles for secondary actions; prefer small/middle over large default controls.
- Use Ant Design Icons or the existing icon library for refresh, settings,
  close, more, filter, and other familiar actions. Add Tooltip when meaning is
  unclear; do not use emoji as operational icons.
- Make destructive actions (delete, disable, remove, reset, clear) explicit.
  Use Popconfirm or confirmation Modal when appropriate; name the target and
  consequences instead of only “Are you sure?”.
- Async UI must handle loading, success, empty, and error states. Use button/table
  loading, Skeleton, or Spin when necessary, not avoidable full-screen spinners.
- Keep empty states simple and useful, with a relevant action when appropriate.
- API errors should be specific and provide recovery when useful. Do not show
  stack traces or vague errors when useful details are available.
- Copy must be concise, direct, functional, non-marketing, and human-readable:
  “Create API Key” and “No data”, not promotional slogans.

### 7. Tables, filters, and data presentation

- Prefer Ant Design Table with compact, readable, structured, data-first rows;
  neutral headers, subtle dividers, and restrained typography.
- Avoid cards inside rows, large per-row buttons, excessive colored tags, and
  meaningless decorative icons.
- Align text left, numbers/currency right, actions right, and status left/center
  according to context.
- Keep visible row actions limited (for example Edit and More); put secondary
  duplicate/disable/history/delete actions in a dropdown.
- Set reasonable widths for long text; use ellipsis and Tooltip when helpful.
  Prevent uncontrolled horizontal expansion.
- Keep date formats consistent within an interface (for example
  `2026-09-11 14:30`); relative time must be intentional.
- Use consistent restrained Tag, Badge, or text for statuses.
- Keep search/filters compact, preferably in one row; use Input.Search or Input
  with a search icon. Put advanced filters in Drawer, Popover, or Collapse.
  Do not give each filter a card or let filters dominate the page.
- Present KPI with label, value, and relevant change. Avoid giant icons,
  gradients, glow, oversized type, and illustrations.
- Add a chart only if it answers a clear user question. Keep charts neutral,
  minimal, readable, and purpose-driven; avoid 3D charts, rainbow palettes,
  unnecessary gauges, and decorative animation.

### 8. Forms, settings, details, and overlays

- Use Ant Design Form with explicit labels, helpful descriptions/tooltips,
  logical groups, and specific validation. Placeholders never replace labels.
- Prefer one column for simple forms; two for complex forms when useful.
  Do not force three or more columns merely to fill width.
- Ordinary forms typically use 480–720px width; complex settings may be wider.
- Explain validation failures (for example “Email address is not valid”), not
  merely “Invalid value” or “Error”.
- Settings follow navigation, title/description, configuration, divider, next
  section. Avoid decorative cards around every section.
- Details organize header, status, metadata, actions, then tabs/details/activity/
  history rather than KPI card walls.
- Use Modal for confirmation, quick edits, short forms, and simple actions.
  Use Drawer or dedicated pages for large forms, full details, and complex flows.
- Keep Drawers focused on contextual details, quick edits, or secondary workflows,
  not an entire application.
- Cards suit isolated summaries, KPI, independent widgets, and distinct modules.
  Avoid nested cards or cards used only because whitespace feels uncomfortable.

### 9. Responsive and accessible interaction

- Desktop is primary, but tablet/mobile must work. Do not simply shrink desktop.
- When needed: Sidebar → Drawer; filters → Collapse/Drawer; table → horizontal
  scroll/priority columns; buttons → stacked layout.
- Check text/buttons/tables, modal/drawer width, forms, headers, sidebar, filters,
  and pagination for overflow, overlap, inaccessible controls, and viewport escape.
- Support relevant default, hover, focus, active, disabled, and loading states.
- Check keyboard navigation, visible focus, labels, appropriate ARIA, contrast,
  and disabled/loading/error states. Do not convey state using color alone.
- Support Enter, Escape, arrows, shortcuts, and command actions when appropriate,
  without introducing an unnecessary complex shortcut system.
- Keep interaction fast, subtle, functional. Use motion only to explain overlays,
  Collapse, feedback, or state transitions; avoid long transitions, bounce,
  parallax, floating movement, and decorative animation.

### 10. Engineering boundaries

- Keep component responsibilities understandable. Split when API calls, forms,
  large tables, modals, business rules, navigation, and unrelated UI become hard
  to reason about together; do not split trivial markup pointlessly.
- Prefer explicit TypeScript interfaces, types, unions, and generics; avoid
  unnecessary `any` and use enums only when appropriate.
- Keep props and configuration APIs simple and readable.
- Keep local UI state local (modal/drawer visibility, selected tab, temporary
  form state). Use global state only when genuinely shared.
- Modify only task-relevant code. Do not replace frameworks, directories, state
  management, unrelated dependencies/components, or unrelated screens.
- Inspect nearby/similar pages, layout, table/form patterns, theme, CSS, and
  conventions before changes. Extend the existing product language.

### 11. Required frontend workflow

1. **Inspect:** existing/similar pages, components, theme, and shared patterns.
2. **Understand:** page type, user goal, main information, navigation, primary and
   secondary actions. Ask whether a card/modal is necessary and whether Ant Design
   or the project already provides the component/page pattern.
3. **Reuse:** existing components, layouts, tokens, and Ant Design.
4. **Implement:** the smallest coherent solution, without unrelated redesign.
5. **Run:** the application; compilation alone does not prove correct UI.
6. **Visually inspect:** actual alignment, spacing, typography, borders, density,
   hierarchy, overflow, and interaction states.
7. **Responsive review:** desktop, tablet, and mobile.
8. **Fix:** visual and interaction problems before declaring completion.

### 12. Review and definition of done

All applicable conditions must be satisfied:

- Functionality works; relevant tests, TypeScript, and build pass; no obvious
  console errors.
- Ant Design/existing patterns are reused appropriately; no unnecessary
  dependency or second UI library was added.
- Product language, spacing, typography, and density remain consistent.
- Data/tables are readable, structured, comparable; forms/settings clear;
  statuses restrained.
- Sidebar/toolbar/navigation are compact, quiet, predictable, and scannable;
  primary actions obvious.
- Loading, empty, error, destructive-action, keyboard, and focus states work.
- Responsive layouts do not break.
- The actual rendered interface was visually reviewed, not just compiled.

Review Stripe qualities (readable data, structured tables, clear forms/settings,
restrained status, comparable numbers), Linear qualities (compact sidebar,
quiet toolbar, predictable navigation, restrained type, systematic spacing,
fast scanning), and Ant Design usage (reuse, tokens, minimal internal overrides).

Ask whether the result is a mature production product or a generic AI dashboard.
Warning signs include gradients, giant cards/headings, decorative icons, glow,
oversized radii, excessive whitespace, random colors, cards everywhere, and
marketing language. Simplify when these appear.

Final decision rule: choose **simpler, quieter, more compact, clearer, more
consistent, and easier to work with**. Prefer fewer visual elements, existing
components/patterns, Ant Design, clarity over decoration, and function over novelty.

Before finishing significant frontend work, ask: “Does this interface feel like
a mature working product inspired by Stripe and Linear, implemented consistently
with Ant Design?” If not, continue improving it.
