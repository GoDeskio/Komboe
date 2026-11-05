# Komboe — Brand Sheet
Generated 2026-11-04 (MST) from `komboe-official-master.png` (Brand-IP/logos/komboe). Mark shape unchanged: vector trace (potrace) of the official black padlock-K; only colour, background and size vary.

## Colours (sampled from master, median)
| Name | Hex | Use |
|---|---|---|
| Komboe Ink | `#070702` | Mark, wordmark, text on light |
| Komboe Off-White | `#F0ECE7` | Light background; mark on dark |
| Night | `#111110` | Dark-mode background |
| Mono | `#000000` / `#FFFFFF` | Single-colour / pinned-tab / themed icon |

## Typography
Wordmark "Komboe" set in Poppins SemiBold (SIL OFL), converted to outlines in all SVGs.

## Clear space & minimum size
- Clear space: at least ½ mark width on every side.
- Minimum: mark 16 px (6 mm print); horizontal lockup 96 px wide (24 mm).
- App icons: mark ≈56% of tile height; Android adaptive foreground within the 66 dp safe zone (40% of 108 dp).

## Do / Don't
- Do: Ink on Off-White, or Off-White on Night. Use supplied files.
- Don't: recolour, stretch, rotate, outline, add effects, re-draw the K or padlock, or place on busy photos without a solid plate.

## File map
- `01-master/` mark SVG + 4096 PNG: light, dark, mono-black, mono-white; `komboe-mark-trace.svg` (tight crop)
- `02-ios/AppIcon.appiconset/` Contents.json + all sizes (20–1024, opaque); `komboe-ios-1024-dark.png`
- `03-android/res/` mipmap-{mdpi…xxxhdpi} ic_launcher, ic_launcher_round, foreground, monochrome PNGs; `mipmap-anydpi-v26/ic_launcher(.xml|_round.xml)`; `drawable/ic_launcher_foreground.xml`, `ic_launcher_monochrome.xml`; `values/ic_launcher_background.xml`; `play-store-icon-512.png`
- `04-web/` favicon.ico (16/32/48), favicon.svg (auto dark), favicon-16/32/48.png, apple-touch-icon.png (180), android-chrome-192/512, maskable-512, safari-pinned-tab.svg, site.webmanifest, head-snippet.html
- `05-wordmark-lockups/` wordmark, lockup-horizontal, lockup-stacked × light/dark/mono-black/mono-white (SVG + PNG @3x)
- `06-social/` avatar-400/1024, X 1500×500, LinkedIn 1584×396, Facebook 820×312, YouTube 2560×1440 (logo inside 1546×423 safe area) × light/dark
- `07-splash/` splash-2732-light/dark.png
- `08-brand-sheet/` this file + komboe-brand-sheet.png
- `previews/` contact sheets; `MANIFEST.sha256`
