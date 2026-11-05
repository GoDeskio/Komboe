# Apple Watch + Safari extension

**Blocked on hardware:** both require macOS with Xcode.

| Deliverable | Requirement | Status |
|---|---|---|
| Safari Web Extension | Mac + Xcode + Apple Developer account for notarization | Not built on Linux CI |
| Apple Watch app | Xcode + watchOS SDK; pairs with iOS app | Not built on Linux CI |

When a Mac builder is available: convert the existing Chromium/Firefox extension with `xcrun safari-web-extension-converter`, then archive Watch + iOS targets. Store submit still needs Dustin's own words.
