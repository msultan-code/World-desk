# WORLD DESK v0.6 — Fix Release

This release fixes the three failed v0.5 items:

1. **Links**
   - Pulse stories now open an internal coverage page.
   - Every individual headline opens the original publisher article.
   - `/open` resolves publisher redirects server-side before sending the user out.

2. **RTL**
   - Arabic story/headline elements use explicit `dir="rtl"`.
   - English elements use `dir="ltr"`.
   - Arabic typography has a separate font stack and spacing.

3. **Arabic sources**
   - Removed unproven generic HTML connectors.
   - Replaced them with verified RSS endpoints where available.
   - A source is marked healthy only if it actually returns usable headlines.

Also retained:
- Arabic-aware search in Headlines.
- Display refresh every 2 minutes.
- Source refresh every 5 minutes while the app is open.
