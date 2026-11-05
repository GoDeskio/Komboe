# Linux auto-type (desktop global)

Komboe desktop on Linux can type vault credentials into the focused window
using `wtype`, `xdotool`, or `ydotool` (picked at runtime).

## Dry-run unit test (no desktop session required)

```bash
cd clients/upstream/apps/desktop/desktop_native
KOMBOE_AUTOTYPE_DRY_RUN=1 cargo test -p autotype dry_run_types_utf16 -- --nocapture
```

`KOMBOE_AUTOTYPE_DRY_RUN=1` skips talking to a real compositor and asserts the
UTF-16 typing path builds the correct key events.

## Runtime helpers

| Tool | Session |
|---|---|
| wtype | Wayland |
| xdotool | X11 |
| ydotool | uinput (needs permissions) |

Source: `clients/upstream/apps/desktop/desktop_native/autotype/src/mvp/linux.rs`.
