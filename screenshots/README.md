# Screenshots

These get embedded in the project README and on bitaxeballer.com. Replace placeholders here with real screenshots and they show up everywhere automatically.

## Expected files

| Filename | Used in | What to capture |
|---|---|---|
| `home.jpg` | README hero, README screenshots section, site `/index.html` | Home view of the dashboard with multiple device cards visible. Ideally show different border colors (one good/green, one warn/yellow if you can engineer that). Window content only — no desktop chrome around it. |
| `detail.jpg` | README screenshots section, site `/index.html` | Device detail page scrolled so the live charts (hashrate + temps) are visible alongside the metrics grid. Pick a device that's been running long enough for the charts to have data. |
| `scan.jpg` | README screenshots section, site `/index.html` | Network scanner mid-run. Click "⚡ scan network" and screenshot while the cycling-IP animation is going (the sweep bar + flicker are striking against the accent green). |

## Capture tips

- ⌘+Shift+4 on macOS, then press <kbd>space</kbd> and click the Bitaxe Baller window — captures just the window with no desktop background.
- Save as `.jpg` (or `.png` — both work, .jpg is smaller for screenshots)
- Resolution: 2x retina is fine — the README scales them down to 900px wide automatically; site does the same.
- Dark theme reads better in the README hero (matches the project's terminal aesthetic).

## Why these names

The README and the site's `index.html` both reference these exact filenames. Naming them anything else means another commit to wire them up.
