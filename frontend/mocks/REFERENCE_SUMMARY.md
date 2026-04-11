# Rex Procore → Rex OS: Reference Summary

## Top 10 Visual/Interaction Characteristics of Rex Procore

| # | Characteristic | Specific values |
|---|---------------|-----------------|
| 1 | **Purple brand accent** | Primary `#6b45a1`, hover `#5A3889`, light `#F3EEFA`, page bg `#F8F5FC` |
| 2 | **Dark sidebar nav** | `#2D1B4E` bg, collapsible, active item has left purple border + tinted bg |
| 3 | **Sticky top bar** | 62px, project selector centered, health dot + user right-aligned |
| 4 | **Stat cards with left color border** | 3px left border (red/amber/green), large 36px numbers, uppercase 12px labels |
| 5 | **Purple table headers** | `#6b45a1` bg, white uppercase text, striped rows `#FBF9FE`, hover `#F3EEFA` |
| 6 | **Solid status badges** | 11px uppercase bold, solid colored backgrounds (red/amber/green/purple) |
| 7 | **Display typography** | Syne 800wt for headings, DM Sans/Mono 500wt for body, high contrast `#0F172A` |
| 8 | **Generous spacing** | Card padding 16-20px, page gutters 24-32px, 8px border radius |
| 9 | **Two button variants** | Primary solid purple, outline with purple border, 6px radius, 13px 600wt |
| 10 | **Tabs for section switching** | Bottom-border tabs, purple active state, 13px 600wt text |

## Essential to Preserve in Rex OS

1. **Purple accent system** — this IS the Rex brand. Non-negotiable.
2. **Left-border stat cards** — signature data pattern. Immediately recognizable.
3. **Purple table headers** — strong, opinionated. Defines the product.
4. **Solid status badges** — clear, decisive status communication.
5. **High-contrast typography** — bold headings, readable body text.
6. **Card-based layout** — professional, structured data presentation.

## Where Current Rex OS Diverges Most Obviously

| Rex OS current | Rex Procore reference | Gap severity |
|---------------|----------------------|-------------|
| Dark navy top nav `#1a1a2e` | Dark purple sidebar `#2D1B4E` | **High** — wrong color family entirely |
| Gray/blue inline badges | Solid colored uppercase badges | **High** — status feels weak |
| Light gray table headers | Purple `#6b45a1` table headers | **High** — tables look generic |
| system-ui font, thin weights | Syne headings, DM Sans body, bold | **High** — typography feels default |
| Inline styles, no theme | CSS custom properties, unified theme | **Medium** — maintenance issue |
| No sidebar | Collapsible sidebar with groups | **Medium** — different nav model |
| No stat card pattern | Left-border colored stat cards | **Medium** — data feels flat |
| `#f8f8fa` page background | `#F8F5FC` purple-tinted background | **Low** — subtle but contributes to brand |
