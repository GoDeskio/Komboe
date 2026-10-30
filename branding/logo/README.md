# Komboe brand: padlock-K logo (official, chosen by Dustin 2026-10-29)

## SHAPE LOCK RULE
The padlock-K **shape must never change**: no redrawing, stretching, re-proportioning, cropping into the glyph, outlining or adding strokes.
Only **colors and backgrounds** may change. Every file here uses the same alpha mask (`master/komboe-mask.png`), scaled uniformly.

## Files
| Path | What |
|---|---|
| source/komboe-padlock-k-original.png | Original artwork (do not edit) |
| master/komboe-mask.png | Canonical shape mask extracted from the original (anti-aliasing preserved) |
| master/komboe-logo-master-transparent.png | Master logo, original ink #070702, transparent |
| master/komboe-logo.svg | Vector trace (vtracer); 99.87% pixel match to the mask. For exact reproduction, the PNG mask is canonical |
| variants/komboe-{original,light,dark}-transparent.png / -on-bg.png | Original (ink on cream #F0ECE7), Light (#6D4AFF on white), Dark (#C4B7FF on #191724) |
| favicon/favicon.ico (16/32/48), favicon-16/32/48.png, apple-touch-icon-180.png, pwa-192.png, pwa-512.png | Web |
| extension/icon-16/32/48/128.png | Browser extensions |
| desktop/komboe.ico (16–256), komboe.icns, komboe-256.png, komboe-512.png | Desktop (Windows/macOS/Linux) |
| mobile/ios/AppIcon-1024.png | iOS App Store icon, opaque (no alpha) |
| mobile/android/ic_launcher_foreground.png / ic_launcher_background.png (432 px), play-store-512.png | Android adaptive icon + Play icon |
| preview.png | Contact sheet |

App tiles use a Proton Pass-like violet gradient (#7C5CFF → #3E24B4) with a white glyph.
| build.py | Regenerates all assets from source (python3 + Pillow + numpy + vtracer) |
