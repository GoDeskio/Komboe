mod app_data;
mod type_input;

pub mod mvp; // MVP, delete with PM-41067

use anyhow::Result;
pub use app_data::{
    path::{build_normalizer, PathNormalizer, PlatformPolicy},
    running_apps::{get_active_app, get_running_apps},
    AppData, AppMetadata, VerifiableAppData,
};

/// Verifies the active application and types into it (Windows path verification).
#[cfg(windows)]
pub fn execute_autotype(
    expected: VerifiableAppData,
    input: &[u16],
    keyboard_shortcut: &[String],
) -> Result<()> {
    let current = get_active_app()?;

    if current != expected {
        tracing::error!(
            %expected,
            %current,
            "active application changed since verification; cancelling."
        );
        return Err(anyhow::anyhow!(
            "active application changed since verification; cancelling."
        ));
    }

    type_input::type_input(input, keyboard_shortcut)
}

/// Linux MVP: types via wtype/xdotool/ydotool (or dry-run). App path verification is Windows-only for now.
#[cfg(target_os = "linux")]
pub fn execute_autotype(
    _expected: VerifiableAppData,
    input: &[u16],
    keyboard_shortcut: &[String],
) -> Result<()> {
    mvp::type_input(input, keyboard_shortcut)
}

/// Autotype is not supported on this platform yet.
#[cfg(not(any(windows, target_os = "linux")))]
pub fn execute_autotype(
    _expected: VerifiableAppData,
    _input: &[u16],
    _keyboard_shortcut: &[String],
) -> Result<()> {
    Err(anyhow::anyhow!("Autotype is not supported on this platform"))
}
