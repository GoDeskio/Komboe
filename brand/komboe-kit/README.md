# Komboe — Brand Sheet (v2)
Generated 2026-11-04 (MST). Mark = vector trace of the official padlock-K (`Brand-IP/logos/komboe/komboe-official-master.png`); shape unchanged. v1 is archived in `_archive/v1/`.

## Palette (WCAG contrast)
| Role | Name | Hex | Key pairings |
|---|---|---|---|
| Core | Ink (sampled) | `#070702` | Ink on Off-White 17.17:1 |
| Core | Off-White (sampled) | `#F0ECE7` | Off-White on Navy 14.65:1 |
| Base / secondary | Komboe Navy | `#0B1B33` | Teal on Navy 9.16:1 |
| Gradient | Navy 2 | `#16335E` | Off-White on Navy 2 10.70:1 |
| Accent | Signal Teal | `#19D3C5` | Ink on Teal 10.73:1, Navy on Teal 9.16:1 |
| Gradient | Teal 2 | `#0E9FB5` | accent gradient end |
| Alert only | Amber | `#FFB020` | Amber on Navy 9.42:1 |
| Dark UI bg | Night | `#111110` | |
All listed pairs pass WCAG AA (4.5:1) and AAA (7:1). **Don't** use Teal on Off-White (1.60:1).

## App icon styles
- **Primary:** Off-White mark on Navy gradient (#16335E top-left to #0B1B33).
- Alternates: Teal gradient (Navy mark), Classic (Ink on Off-White), Ink + Teal mark, Teal flat. See `00-palette/icon-styles/`.
- iOS 18: dark = Teal mark on transparent; tinted = white mark on black (grayscale).

## Clear space & minimum size
Clear space ≥ ½ mark width. Min mark 16 px / 6 mm; min horizontal lockup 96 px / 24 mm. Wordmark: Poppins SemiBold (OFL), outlined.

## Do / Don't
Do: Off-White or Teal on Navy; Ink on Off-White or Teal. Don't: recolour outside the palette, stretch, rotate, add effects, or redraw the K/padlock.

## File map
- `favicons/` (and identical `04-web/`): favicon.ico (16/32/48), favicon.svg, favicon-16/32/48/96 PNG, apple-touch-icon.png (180), android-chrome-192/512, maskable-icon-512, mstile-150, safari-pinned-tab.svg, site.webmanifest, browserconfig.xml, head-snippet.html
- `00-palette/icon-styles/` 5 icon styles (SVG + 1024 PNG)
- `01-master/` mark in light, dark, navy, navy-gradient, teal, mono-black, mono-white (SVG + 4096 PNG) + trace SVG
- `02-ios/AppIcon.appiconset/` Contents.json, all iPhone/iPad sizes (20–83.5 @1–3x, incl. 38/64/68), 1024 any + dark + tinted; `alternate-icons/`
- `03-android/res/` mipmap-{mdpi..xxxhdpi}: ic_launcher, _round, _foreground, _background, _monochrome; mipmap-anydpi-v26 adaptive XML; drawable vectors (foreground, monochrome, gradient background, ic_stat_komboe); drawable-{dpi}/ic_stat_komboe.png (notification); values/colors.xml; `play-store/` icon 512 + feature-graphic 1024x500
- `09-desktop/` macos/Komboe.iconset + Komboe.icns; windows/komboe.ico (16–256), tiles/ (UWP + mstile), browserconfig.xml; electron/icon-1024.png, icon.icns, icon.ico, icons/16–512
- `05-wordmark-lockups/` wordmark, horizontal, stacked × light/dark/navy/teal/mono-black/mono-white
- `06-social/` avatars 400/1024 + X, LinkedIn, Facebook, YouTube banners × navy/light/dark
- `07-splash/` 2732 navy/light/dark
- `previews/` per-platform actual-size sheets + phone and browser-tab mockups
