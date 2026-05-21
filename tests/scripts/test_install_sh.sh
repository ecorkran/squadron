#!/usr/bin/env bash
# Idempotency smoke test for scripts/install.sh.
#
# Verifies INVOCATION-idempotency: running install.sh twice does not issue
# a second "pipx install" or "npm install" when the tools are already present.
# State-idempotency (host system ends up the same) is delegated to the tools
# themselves (pipx install is a no-op on second run; npm i -g converges).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/install.sh"

# ---------------------------------------------------------------------------
# Setup: controlled environment
# ---------------------------------------------------------------------------

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

STUBS_DIR="$WORK_DIR/stubs"
mkdir -p "$STUBS_DIR"

LOG1="$WORK_DIR/run1.log"
LOG2="$WORK_DIR/run2.log"

# ---------------------------------------------------------------------------
# Write stub binaries that record calls and simulate "already installed" state
# ---------------------------------------------------------------------------

# sq stub: already installed, and sq setup must not fail the test.
# We make sq setup a no-op by having it print a message and exit 0.
cat > "$STUBS_DIR/sq" << 'EOF'
#!/usr/bin/env bash
echo "sq-stub: $*"
exit 0
EOF

cat > "$STUBS_DIR/uv" << 'EOF'
#!/usr/bin/env bash
# Record the call, then report success.
echo "uv $*" >> "$SQUADRON_INSTALL_LOG"
exit 0
EOF

cat > "$STUBS_DIR/pipx" << 'EOF'
#!/usr/bin/env bash
echo "pipx $*" >> "$SQUADRON_INSTALL_LOG"
exit 0
EOF

cat > "$STUBS_DIR/npm" << 'EOF'
#!/usr/bin/env bash
echo "npm $*" >> "$SQUADRON_INSTALL_LOG"
exit 0
EOF

cat > "$STUBS_DIR/cf" << 'EOF'
#!/usr/bin/env bash
echo "cf-stub"
exit 0
EOF

chmod +x "$STUBS_DIR/sq" "$STUBS_DIR/uv" "$STUBS_DIR/pipx" "$STUBS_DIR/npm" "$STUBS_DIR/cf"

# ---------------------------------------------------------------------------
# First run: sq and cf are on PATH -> install stubs should NOT be called
# ---------------------------------------------------------------------------

export SQUADRON_INSTALL_LOG="$LOG1"
touch "$LOG1"

HOME="$WORK_DIR" PATH="$STUBS_DIR:/usr/bin:/bin" \
    bash "$SCRIPT" --yes > /dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# Second run: same stubs, still on PATH -> install stubs still should NOT be called
# ---------------------------------------------------------------------------

export SQUADRON_INSTALL_LOG="$LOG2"
touch "$LOG2"

HOME="$WORK_DIR" PATH="$STUBS_DIR:/usr/bin:/bin" \
    bash "$SCRIPT" --yes > /dev/null 2>&1 || true

# ---------------------------------------------------------------------------
# Assert: neither run should have invoked package-install stubs
# (because sq and cf were already on PATH both times)
# ---------------------------------------------------------------------------

for log in "$LOG1" "$LOG2"; do
    if grep -qE "^(uv tool install|pipx install|npm install)" "$log" 2>/dev/null; then
        echo "FAIL: install stub was called in $log:" >&2
        cat "$log" >&2
        exit 1
    fi
done

echo "PASS: install.sh idempotency smoke test"
exit 0
