#!/usr/bin/env bash
# =============================================================================
# Squadron install bootstrap
#
# What this script does:
#   1. Detects whether `sq` (squadron-ai) is already installed; if not, installs
#      it via uv tool install (preferred) or pipx install (fallback).
#   2. Detects whether `cf` (context-forge) is already installed; if not,
#      installs it via npm i -g @context-forge/cli.
#   3. Hands off to `sq setup` which walks through the remaining configuration
#      steps interactively.
#
# This script only handles the pre-Squadron bootstrap -- the parts that cannot
# be done from inside Python.  All orchestration logic lives in `sq setup`.
#
# Canonical URL (read before running):
#   https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh
#
# Inspect before running:
#   curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh \
#       -o install.sh && less install.sh && bash install.sh
#
# Usage:
#   bash install.sh [--yes|-y] [--help|-h]
#
#   --yes / -y   Skip all interactive "Install X? [y/N]" prompts (auto-yes).
#   --help / -h  Print this usage block and exit.
#
# Requirements:
#   - bash 4+ on macOS or Linux
#   - Internet access (for package installs)
#   - This script does NOT run with sudo unless you invoke it that way yourself.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

AUTO_YES=0

usage() {
    grep '^#' "$0" | grep -v '^#!/' | sed 's/^# \{0,1\}//'
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=1 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $arg" >&2; echo "Run '$0 --help' for usage." >&2; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_print_header() {
    echo ""
    echo "==> $*"
}

_confirm() {
    # Returns 0 (yes) or 1 (no/skip).
    if [[ "$AUTO_YES" -eq 1 ]]; then
        return 0
    fi
    local reply
    read -r -p "$1 [y/N] " reply
    case "$reply" in
        [Yy]*) return 0 ;;
        *) return 1 ;;
    esac
}

_log_call() {
    # Append to install-stub-log if the env var is set (used by idempotency test).
    if [[ -n "${SQUADRON_INSTALL_LOG:-}" ]]; then
        echo "$1" >> "$SQUADRON_INSTALL_LOG"
    fi
}

# ---------------------------------------------------------------------------
# Step 1: Install squadron-ai if not already present
# ---------------------------------------------------------------------------

_print_header "Checking for Squadron (sq)"

if command -v sq > /dev/null 2>&1; then
    echo "  ok: sq already installed at $(command -v sq)"
else
    if command -v uv > /dev/null 2>&1; then
        if _confirm "Install squadron-ai via uv tool install?"; then
            _log_call "uv tool install squadron-ai"
            uv tool install squadron-ai
        else
            echo "  Skipped. Install later with: uv tool install squadron-ai" >&2
            exit 1
        fi
    elif command -v pipx > /dev/null 2>&1; then
        if _confirm "Install squadron-ai via pipx?"; then
            _log_call "pipx install squadron-ai"
            pipx install squadron-ai
        else
            echo "  Skipped. Install later with: pipx install squadron-ai" >&2
            exit 1
        fi
    else
        echo "" >&2
        echo "Neither uv nor pipx is available. Install one of them first:" >&2
        echo "  uv:   https://docs.astral.sh/uv/#installation" >&2
        echo "  pipx: https://pipx.pypa.io/stable/#install-pipx" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Step 2: Install context-forge (cf) if not already present
# ---------------------------------------------------------------------------

_print_header "Checking for Context Forge (cf)"

if command -v cf > /dev/null 2>&1; then
    echo "  ok: cf already installed at $(command -v cf)"
else
    if command -v npm > /dev/null 2>&1; then
        if _confirm "Install @context-forge/cli via npm?"; then
            _log_call "npm install -g @context-forge/cli"
            npm install -g @context-forge/cli
        else
            echo "  Skipped. Install later with: npm i -g @context-forge/cli" >&2
        fi
    else
        echo "" >&2
        echo "npm is not available. Install Node.js/npm first:" >&2
        case "$(uname -s)" in
            Darwin) echo "  macOS:  brew install node" >&2 ;;
            Linux)  echo "  Linux:  https://nodejs.org/en/download/package-manager" >&2 ;;
            *)      echo "  See:    https://nodejs.org/en/download/" >&2 ;;
        esac
        echo "Then re-run this script." >&2
    fi
fi

# Installing the binary alone leaves the user without the /cf:* slash
# commands, which is a half-finished state they have no reason to expect.
# Idempotent, so it is safe when cf was already present.
if command -v cf > /dev/null 2>&1; then
    _log_call "cf install-commands"
    cf install-commands || echo "  Warning: cf install-commands failed; run it manually." >&2
fi

# ---------------------------------------------------------------------------
# Step 3: Hand off to sq setup
# ---------------------------------------------------------------------------

_print_header "Handing off to sq setup"
echo ""

exec sq setup "$@"
