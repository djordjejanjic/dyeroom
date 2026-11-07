#!/bin/sh
# Dyeroom for macOS and Linux:   curl -LsSf https://dyeroom.app/install.sh | sh
#
# Installs uv (Astral's Python installer, which brings its own Python) if it is not there,
# then Dyeroom from PyPI with uv, and adds an icon: Dyeroom.app in ~/Applications on macOS, an
# entry in the app list on Linux. Run it again to update. Nothing needs administrator rights.
# Source: https://github.com/djordjejanjic/dyeroom
set -eu

say() { printf '%s\n' "$*"; }

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) say "This installer is for macOS and Linux. On Windows, in PowerShell:"
     say '  powershell -ExecutionPolicy ByPass -c "irm https://dyeroom.app/install.ps1 | iex"'; exit 1 ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv, which installs Dyeroom and its Python..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"  # where uv's installer puts it
fi

say "Installing Dyeroom..."
uv tool install --upgrade --compile-bytecode --python 3.12 "${DYEROOM_PACKAGE:-dyeroom}"  # compiled now: a quicker first start
uv tool update-shell >/dev/null 2>&1 || true  # so the dyeroom command is found in new terminals

dyeroom="$(uv tool dir --bin)/dyeroom"
if [ -z "${DYEROOM_NO_SHORTCUT:-}" ]; then
  "$dyeroom" shortcut
fi

say ""
say "Dyeroom is installed. Open it from your applications, or type dyeroom in a new terminal window."
if ! command -v exiftool >/dev/null 2>&1; then
  say "Optional: install ExifTool so exports keep the camera's metadata"
  say "  (macOS: brew install exiftool; Linux: sudo apt install libimage-exiftool-perl)."
fi
