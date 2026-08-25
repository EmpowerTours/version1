#!/usr/bin/env bash
# =============================================================================
# THE VERIFIER
# =============================================================================
# The autoloop Stop hook (~/.claude/hooks/scripts/verify-loop.sh) runs this.
# Non-zero exit = not done. This file is the definition of "working" for this
# repo. Deterministic only, no LLM calls. Never weaken a check to make it pass.
#
# Detection happens at RUNTIME, so this stays correct as the repo changes.
#
#   VERIFY_SKIP_BUILD=1   skip the (slow) production build step
# =============================================================================

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export PATH="$HOME/.local/bin:$PATH"

FAILED=0
RAN=0          # CODE checks only. A verifier that skipped everything is NOT green.
SAFETY=0       # once 1, checks stop counting toward RAN: repo-safety checks pass
               # in an empty repo, and must never stand in for proof code works.

step() { printf '\n\033[1m-- %s\033[0m\n' "$1"; }
pass() { printf '\033[32m  PASS\033[0m %s\n' "$1"; [ "$SAFETY" = 0 ] && RAN=$((RAN+1)); return 0; }
fail() { printf '\033[31m  FAIL\033[0m %s\n' "$1"; FAILED=1; [ "$SAFETY" = 0 ] && RAN=$((RAN+1)); return 0; }
skip() { printf '\033[33m  SKIP\033[0m %s\n' "$1"; }   # could-not-check != failed

# Per-repo overrides, so a slow or unusual repo does not need its own fork of
# this file. Anything set here is visible in the output as a SKIP line.
#   STEP_TIMEOUT=420        raise the per-step cap
#   VERIFY_SKIP_PYTEST=1    suite too slow for a stop-gate (say why in the file)
#   VERIFY_SKIP_BUILD=1     skip the production build
# shellcheck disable=SC1091
[ -f .claude/verify.conf ] && . .claude/verify.conf

STEP_TIMEOUT="${STEP_TIMEOUT:-240}"   # keeps the whole run under the hook's 600s

run() {  # run <label> <command...>
    local label="$1"; shift
    local out rc
    out=$(timeout "$STEP_TIMEOUT" "$@" 2>&1); rc=$?
    if [ $rc -eq 0 ]; then pass "$label"
    elif [ $rc -eq 124 ]; then
        fail "$label - TIMED OUT after ${STEP_TIMEOUT}s (raise STEP_TIMEOUT, or make the step faster)"
    else
        fail "$label"; printf '%s\n' "$out" | tail -25 | sed 's/^/      /'
    fi
}

# =============================================================================
# SOLIDITY
# =============================================================================
FDIRS="."
[ -f contracts/foundry.toml ] && FDIRS="contracts"
for FDIR in $FDIRS; do
    [ -f "$FDIR/foundry.toml" ] || continue
    step "solidity ($FDIR)"
    if ! command -v forge >/dev/null 2>&1; then skip "forge not installed"; continue; fi

    BOUT=$( cd "$FDIR" && timeout "$STEP_TIMEOUT" forge build 2>&1 ); BRC=$?
    if [ $BRC -eq 0 ]; then pass "forge build"
    elif [ $BRC -eq 124 ]; then fail "forge build - TIMED OUT after ${STEP_TIMEOUT}s"
    else fail "forge build"; printf '%s\n' "$BOUT" | tail -20 | sed 's/^/      /'; fi

    # forge test EXITS 0 WHEN THERE ARE NO TESTS. An empty suite is the most
    # dangerous kind of green, so assert on parsed output, never the exit code.
    TOUT=$( cd "$FDIR" && timeout "$STEP_TIMEOUT" forge test 2>&1 ); TRC=$?
    if [ $TRC -eq 124 ]; then
        fail "forge test - TIMED OUT after ${STEP_TIMEOUT}s"
    elif printf '%s' "$TOUT" | grep -q 'No tests found'; then
        fail "forge test ran ZERO tests (exit 0 is a false green)"
    elif [ $TRC -ne 0 ]; then
        fail "forge test"; printf '%s\n' "$TOUT" | tail -25 | sed 's/^/      /'
    else
        N=$(printf '%s' "$TOUT" | grep -oE '[0-9]+ tests passed' | grep -oE '^[0-9]+' | awk '{s+=$1} END{print s+0}')
        if [ "${N:-0}" -eq 0 ]; then fail "forge test reported no passing tests"
        else pass "forge test ($N passed)"; fi
    fi
done

# =============================================================================
# NODE / TYPESCRIPT
# =============================================================================
if [ -f package.json ]; then
    step "node"
    PM="npm run"; [ -f pnpm-lock.yaml ] && PM="pnpm run"; [ -f yarn.lock ] && PM="yarn"
    if [ ! -d node_modules ]; then
        skip "node_modules absent - run install first (could not check, not a pass)"
    else
        has() { jq -e --arg s "$1" '.scripts[$s] // empty' package.json >/dev/null 2>&1; }
        if has typecheck; then run "typecheck" bash -lc "$PM typecheck"
        elif [ -f tsconfig.json ]; then run "tsc --noEmit" bash -lc "npx --no-install tsc --noEmit"; fi
        has lint  && run "lint"  bash -lc "$PM lint"
        has test  && run "test"  bash -lc "$PM test"
        if has build; then
            if [ "${VERIFY_SKIP_BUILD:-0}" = "1" ]; then skip "build (VERIFY_SKIP_BUILD=1)"
            else run "build" bash -lc "$PM build"; fi
        fi
    fi
fi

# =============================================================================
# PYTHON
# =============================================================================
if [ -f requirements.txt ] || [ -f pyproject.toml ]; then
    step "python"
    PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
    PYTEST=""; [ -x .venv/bin/pytest ] && PYTEST=.venv/bin/pytest
    [ -z "$PYTEST" ] && command -v pytest >/dev/null 2>&1 && PYTEST=pytest

    command -v ruff >/dev/null 2>&1 && run "ruff check" bash -lc "ruff check ." || true

    HAVE_TESTS=$(find . -path ./.venv -prune -o -path ./node_modules -prune -o -name 'test_*.py' -print 2>/dev/null | head -1)
    if [ "${VERIFY_SKIP_PYTEST:-0}" = "1" ]; then
        skip "pytest (VERIFY_SKIP_PYTEST=1 in .claude/verify.conf - run VERIFY_SKIP_PYTEST=0 to include)"
    elif [ -d tests ] && [ -n "$PYTEST" ]; then
        # Use the CI-style bare invocation. `python -m pytest` inserts CWD into
        # sys.path and `pytest` does not, so the two are NOT interchangeable.
        run "pytest tests/" bash -lc "$PYTEST tests/ -q"
    elif [ -n "$HAVE_TESTS" ]; then
        skip "pytest not installed"
    else
        # No suite: the floor is that every tracked module at least compiles.
        FILES=$(git ls-files '*.py' 2>/dev/null | grep -v '^\.venv/' | head -200 | tr '\n' ' ')
        if [ -n "$FILES" ]; then
            # shellcheck disable=SC2086
            run "python compiles (no test suite present)" bash -lc "$PY -m py_compile $FILES"
        fi
    fi
fi

# =============================================================================
# GO
# =============================================================================
if [ -f go.mod ]; then
    step "go"
    if command -v go >/dev/null 2>&1; then
        run "go build ./..." bash -lc "go build ./..."
        run "go vet ./..."   bash -lc "go vet ./..."
        if go test ./... -run XXXNONEXISTENT >/dev/null 2>&1; then
            run "go test ./..." bash -lc "go test ./..."
        else
            skip "go test skipped (packages do not build for test)"
        fi
    else
        skip "go not installed"
    fi
fi

# =============================================================================
# REPO SAFETY - encodes mistakes that have actually happened on this machine
# =============================================================================
SAFETY=1
step "repo safety"

# .env must never be tracked.
if git ls-files 2>/dev/null | grep -qE '(^|/)\.env($|\.local$|\.production$)'; then
    fail ".env is tracked by git"
else
    pass ".env not tracked"
fi

# A hardcoded private key. Matched as an ASSIGNMENT to a key-shaped name so that
# a 64-hex tx hash in a comment or fixture does not trip it.
if git ls-files '*.ts' '*.tsx' '*.js' '*.jsx' '*.py' '*.sol' '*.go' 2>/dev/null | xargs -r grep -lInE \
     '(PRIVATE_KEY|privateKey|MNEMONIC|mnemonic|SECRET_KEY)[^=]{0,20}=[[:space:]]*["'"'"']?(0x)?[a-fA-F0-9]{64}' 2>/dev/null \
     | grep -q .; then
    fail "hardcoded private key / mnemonic assigned in tracked source"
else
    pass "no hardcoded key material"
fi

# NOTE: a "no --broadcast" check deliberately does NOT live here. Every contracts
# repo has a human-run deploy script, and fcempowertours broadcasts from a keeper
# workflow by design, so a universal version fires constantly on correct code.
# Put it in a repo-specific verifier where the policy is actually known.

# =============================================================================
step "result"
if [ "$RAN" -eq 0 ]; then
    printf '\n\033[31mFAIL: no checks could run - this verifier proved nothing.\033[0m\n'
    exit 1
fi
if [ "$FAILED" -ne 0 ]; then
    printf '\n\033[31mVERIFY FAILED (%s checks ran)\033[0m\n' "$RAN"
    exit 1
fi
printf '\n\033[32mALL CHECKS PASSED (%s checks ran)\033[0m\n' "$RAN"
exit 0
