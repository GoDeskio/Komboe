# Build the Komboe Electron desktop app for Windows x64 (NSIS installer + portable zip).
# Resumable: each step is skipped when its output already exists. No admin rights needed:
# MSVC + Windows SDK come from a portable, non-installed copy (portable-msvc.py).
# Prereqs: rustup (msvc toolchain), Node >= 24.17, git, Python 3.
param([string]$Root = "D:\komboe-build")
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Root | Out-Null; Set-Location $Root
if (-not (Test-Path "$Root\msvc\setup_x64.bat")) {
  Invoke-WebRequest https://gist.githubusercontent.com/mmozeiko/7f3162ec2988e81e56d5c4e22cde9977/raw/portable-msvc.py -OutFile portable-msvc.py
  python portable-msvc.py --accept-license --vs 2022 --target x64
}
if (-not (Test-Path "$Root\src\.git")) { git -c core.longpaths=true clone --depth 1 https://github.com/GoDeskio/Komboe.git src }
# clients/upstream in the repo is already the pinned (91214c3) tree with scripts/rebrand_apply.py applied.
$app = "$Root\src\clients\upstream\apps\desktop"
New-Item -ItemType Directory -Force "$Root\cargo-target" | Out-Null
if (-not (Test-Path "$app\desktop_native\target")) { cmd /c mklink /J "$app\desktop_native\target" "$Root\cargo-target" | Out-Null }
# electron-builder's winCodeSign archive has macOS symlinks that fail without the symlink privilege; pre-extract without them.
$wcs = "$env:LOCALAPPDATA\electron-builder\Cache\winCodeSign\winCodeSign-2.6.0"
if (-not (Test-Path "$wcs\rcedit-x64.exe")) {
  $a = "$env:TEMP\winCodeSign-2.6.0.7z"
  Invoke-WebRequest https://github.com/electron-userland/electron-builder-binaries/releases/download/winCodeSign-2.6.0/winCodeSign-2.6.0.7z -OutFile $a
  $script:z = $a
}
$cmd = @"
@echo off
call "$Root\msvc\setup_x64.bat"
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
set ELECTRON_BUILDER_SIGN=0
set CSC_IDENTITY_AUTO_DISCOVERY=false
cd /d "$Root\src\clients\upstream"
if not exist node_modules\.package-lock.json (call npm ci --no-audit --no-fund || exit /b 11)
if "$($script:z)" neq "" node_modules\7zip-bin\win\x64\7za.exe x -bd -y "$($script:z)" -o"$wcs" -xr!darwin >nul
cd apps\desktop
if not exist desktop_native\dist\desktop_proxy.win32-x64.exe (cd desktop_native && node build.js --release && cd .. || exit /b 12)
if not exist build\main.js (call npm run build || exit /b 13)
call npx electron-builder --win nsis zip --x64 -p never || exit /b 14
"@
Set-Content -Encoding ascii "$Root\build-win.cmd" $cmd
cmd /c "$Root\build-win.cmd"; if ($LASTEXITCODE) { throw "build failed: $LASTEXITCODE" }
Get-ChildItem "$app\dist\*.exe", "$app\dist\*.zip" | Format-Table Name, Length
