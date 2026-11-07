# Dyeroom for Windows. In PowerShell:
#   powershell -ExecutionPolicy ByPass -c "irm https://dyeroom.app/install.ps1 | iex"
#
# Installs uv (Astral's Python installer, which brings its own Python) if it is not there, then
# Dyeroom from PyPI with uv, and adds Dyeroom to the Start menu. Run it again to update. Nothing
# needs administrator rights. Source: https://github.com/djordjejanjic/dyeroom

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv, which installs Dyeroom and its Python..."
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"  # where uv's installer puts it
}

# One of Dyeroom's parts has no build for Windows on Arm: there, Python for Intel, which Windows runs.
$python = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "cpython-3.12-windows-x86_64-none" } else { "3.12" }
$package = if ($env:DYEROOM_PACKAGE) { $env:DYEROOM_PACKAGE } else { "dyeroom" }

Write-Host "Installing Dyeroom..."
uv tool install --upgrade --compile-bytecode --python $python $package
if ($LASTEXITCODE -ne 0) { Write-Host "Dyeroom could not be installed."; exit 1 }
uv tool update-shell 2>&1 | Out-Null  # so the dyeroom command is found in new terminals

$dyeroom = Join-Path (uv tool dir --bin) "dyeroom.exe"
if (-not $env:DYEROOM_NO_SHORTCUT) { & $dyeroom shortcut }

Write-Host ""
Write-Host "Dyeroom is installed. Open it from the Start menu, or type dyeroom in a new terminal window."
if (-not (Get-Command exiftool -ErrorAction SilentlyContinue)) {
    Write-Host "Optional: install ExifTool so exports keep the camera's metadata (winget install OliverBetz.ExifTool)."
}
