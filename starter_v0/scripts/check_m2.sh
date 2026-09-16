#!/usr/bin/env bash
# M2 (Tool/Backend) completion check. Usage from anywhere in the repo:
#   bash starter_v0/scripts/check_m2.sh            # offline + live preflight
#   bash starter_v0/scripts/check_m2.sh --offline  # skip the live API call
set -u
cd "$(dirname "$0")/.."
unset PYTHONPATH  # ROS/system site-packages shadow the venv (old Brotli, missing urllib3)
PY=.venv/bin/python
failures=0
pass() { echo "  PASS $1"; }
fail() { echo "  FAIL $1"; failures=$((failures + 1)); }

git fetch -q origin 2>/dev/null || echo "  (could not fetch origin; comparing with last fetched state)"

echo "== 1. Smoke test: tools.yaml, registry, data, tool behavior (offline)"
summary=$($PY scripts/smoke_tools.py | tail -1)
[[ "$summary" == *" 0 failed" ]] && pass "$summary" || fail "$summary"

echo "== 2. Preflight: live structured tool call via Anthropic"
if [[ "${1:-}" == "--offline" ]]; then
  echo "  SKIP (--offline)"
else
  out=$($PY scripts/preflight_provider.py --provider anthropic 2>&1)
  if grep -q "^tool=get_robot_status" <<<"$out"; then
    pass "$(grep -E '^(tool|args)=' <<<"$out" | tr '\n' ' ')"
  else
    fail "$(tail -1 <<<"$out")"
  fi
fi

echo "== 3. M2 files present on origin/main"
files=(
  docs/AMR_TOOL_CONTRACT.md
  hospital_data/README.md hospital_data/robots.json hospital_data/locations.json
  hospital_data/routes.json hospital_data/missions.json
  tools/__init__.py tools/_hospital.py
  artifacts/tools.yaml artifacts/reference/tools_it_helpdesk.yaml
  scripts/smoke_tools.py scripts/preflight_provider.py providers/anthropic_provider.py
  server.py
)
for tool in get_robot_status list_robots get_location_info get_route_info dispatch_mission cancel_mission; do
  files+=("tools/$tool/tool.py" "tools/$tool/TOOL.md")
done
missing=()
for f in "${files[@]}"; do
  git cat-file -e "origin/main:starter_v0/$f" 2>/dev/null || missing+=("$f")
done
[[ ${#missing[@]} -eq 0 ]] && pass "all ${#files[@]} files" || fail "missing: ${missing[*]}"

echo "== 4. No secrets or generated files tracked"
tracked=$(git ls-files | grep -E '(^|/)(\.env|\.env\.[^e].*|missions/.*|tickets/.*|\.venv/.*)$' || true)
[[ -z "$tracked" ]] && pass "no .env, missions/, tickets/, .venv/" || fail "tracked: $tracked"

echo "== 5. No uncommitted changes in M2 paths"
dirty=$(git status --porcelain -- tools hospital_data artifacts/tools.yaml artifacts/reference docs scripts providers)
[[ -z "$dirty" ]] && pass "working tree clean" || fail $'uncommitted:\n'"$dirty"

echo "== 6. Local main synced with origin/main"
read -r behind ahead < <(git rev-list --left-right --count origin/main...HEAD)
[[ "$behind" == 0 && "$ahead" == 0 ]] && pass "up to date" || fail "behind $behind, ahead $ahead (pull/push needed)"

echo
if [[ $failures -eq 0 ]]; then
  echo "M2 CHECK: ALL PASS"
else
  echo "M2 CHECK: $failures FAILED"
  exit 1
fi
