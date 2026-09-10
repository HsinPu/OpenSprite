# Remove duplicate header new-chat action (0.21.4)

- Remove the header new-chat shortcut in desktop collapsed and mobile layouts.
- Preserve sidebar new-chat, navigation toggle, breadcrumb and execution toggle.
- Remove the obsolete icon import and CSS selector; update collapsed-header regression expectation.
- Bump product version to 0.21.4. No data migration, commit or local deployment.
- Verification: App suite 30 tests passed; TypeScript/production build, offline lockfile check and diff check passed. Existing bundle-size warning remains. No new live-browser verification in this slice.
