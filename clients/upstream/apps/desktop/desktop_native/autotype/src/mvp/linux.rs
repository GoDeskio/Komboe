//! Linux auto-type MVP for Komboe.
//! Prefers `wtype` (Wayland), then `xdotool` (X11), then `ydotool`.
//! Set `KOMBOE_AUTOTYPE_DRY_RUN=1` to validate without injecting keystrokes
//! (used by feature tests on headless boxes).

use anyhow::{anyhow, bail, Result};
use std::process::Command;

fn dry_run() -> bool {
    matches!(std::env::var("KOMBOE_AUTOTYPE_DRY_RUN").as_deref(), Ok("1") | Ok("true"))
}

fn utf16_to_string(input: &[u16]) -> Result<String> {
    String::from_utf16(input).map_err(|_| anyhow!("auto-type input is not valid UTF-16"))
}

fn which(bin: &str) -> bool {
    Command::new("sh")
        .arg("-c")
        .arg(format!("command -v {bin} >/dev/null 2>&1"))
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

pub fn get_foreground_window_title() -> Result<String> {
    if dry_run() {
        return Ok("komboe-dry-run".into());
    }
    if which("xdotool") {
        let out = Command::new("xdotool")
            .args(["getactivewindow", "getwindowname"])
            .output()?;
        if out.status.success() {
            return Ok(String::from_utf8_lossy(&out.stdout).trim().to_string());
        }
    }
    if which("wtype") {
        // wtype has no window-title API; return a stable placeholder so callers can proceed.
        return Ok("wayland-unknown".into());
    }
    bail!("No window-title helper found (install xdotool for X11).")
}

pub fn type_input(input: &[u16], keyboard_shortcut: &[String]) -> Result<()> {
    let text = utf16_to_string(input)?;
    if text.chars().count() > 4096 {
        bail!("auto-type input too long");
    }
    // Reject control chars other than tab/newline to avoid shell metachar injection via helpers.
    if text.chars().any(|c| c.is_control() && c != '\t' && c != '\n') {
        bail!("auto-type input contains unsupported control characters");
    }
    if dry_run() {
        // Feature tests assert this path works without a display server.
        let _ = keyboard_shortcut;
        return Ok(());
    }
    let mods: Vec<&str> = keyboard_shortcut
        .iter()
        .map(|s| s.as_str())
        .filter(|s| matches!(*s, "Control" | "Alt" | "Super" | "Shift" | "Meta"))
        .collect();

    if which("wtype") {
        let mut cmd = Command::new("wtype");
        for m in &mods {
            let key = match *m {
                "Control" => "ctrl",
                "Alt" => "alt",
                "Super" | "Meta" => "logo",
                "Shift" => "shift",
                _ => continue,
            };
            cmd.args(["-M", key]);
        }
        cmd.arg("--").arg(&text);
        let status = cmd.status()?;
        if status.success() {
            return Ok(());
        }
        bail!("wtype failed: {status}");
    }
    if which("xdotool") {
        let mut args = vec!["type".to_string(), "--clearmodifiers".into(), "--".into(), text.clone()];
        if !mods.is_empty() {
            // Hold modifiers via keydown/keyup around type.
            let mut seq = Vec::new();
            for m in &mods {
                seq.push("keydown".into());
                seq.push((*m).to_lowercase());
            }
            seq.push("type".into());
            seq.push("--".into());
            seq.push(text.clone());
            for m in mods.iter().rev() {
                seq.push("keyup".into());
                seq.push((*m).to_lowercase());
            }
            args = seq;
        }
        let status = Command::new("xdotool").args(&args).status()?;
        if status.success() {
            return Ok(());
        }
        bail!("xdotool failed: {status}");
    }
    if which("ydotool") {
        let status = Command::new("ydotool").args(["type", &text]).status()?;
        if status.success() {
            return Ok(());
        }
        bail!("ydotool failed: {status}");
    }
    bail!("No auto-type helper found (install wtype, xdotool, or ydotool).")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dry_run_types_utf16() {
        std::env::set_var("KOMBOE_AUTOTYPE_DRY_RUN", "1");
        let input: Vec<u16> = "hello@example.com".encode_utf16().collect();
        type_input(&input, &[]).unwrap();
        assert_eq!(get_foreground_window_title().unwrap(), "komboe-dry-run");
    }
}
