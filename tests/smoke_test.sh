#!/usr/bin/env bash
# =============================================================================
# SENTINEL-AI — Unified Smoke Test Suite
# Covers: Auth, Detect, Dashboard, RBAC, ML integration, security
#
# Usage:
#   bash tests/smoke_test.sh
#   BASE_URL=http://myserver:8000 bash tests/smoke_test.sh
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API="${BASE_URL}/api/v1"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS=0; FAIL=0; ERRORS=()

pass()   { echo -e "${GREEN}  ✓ $1${NC}"; ((PASS++)) || true; }
fail()   { echo -e "${RED}  ✗ $1${NC}"; ((FAIL++)) || true; ERRORS+=("$1"); }
warn()   { echo -e "${YELLOW}  ⚠ $1${NC}"; }
section(){ echo -e "\n${CYAN}══ $1 ══${NC}"; }

post() {
    local url="$1" body="$2" token="${3:-}"
    curl -s -w "\n%{http_code}" -X POST "$url" \
        -H "Content-Type: application/json" \
        ${token:+-H "Authorization: Bearer $token"} \
        -d "$body"
}
get_req() {
    curl -s -w "\n%{http_code}" "$1" -H "Authorization: Bearer $2"
}
status_of() { echo "$1" | tail -1; }
body_of()   { echo "$1" | head -n -1; }
jq_get()    { echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print($2)" 2>/dev/null || echo ""; }

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  SENTINEL-AI — Unified Smoke Test Suite               ║"
echo "║  Target: ${BASE_URL}"
echo "╚════════════════════════════════════════════════════════╝"

section "1. Health"
R=$(curl -s -w "\n%{http_code}" "${BASE_URL}/health")
[[ "$(status_of "$R")" == "200" ]] && pass "GET /health → 200" || fail "GET /health → $(status_of "$R")"
body_of "$R" | grep -q '"ok"' && pass "health body contains status=ok" || fail "health body wrong"

section "2. Auth"
R=$(post "$API/auth/login" '{"username":"analyst","password":"analyst123"}')
[[ "$(status_of "$R")" == "200" ]] && pass "analyst login → 200" || fail "analyst login → $(status_of "$R")"
B=$(body_of "$R")
ANALYST_TOKEN=$(jq_get "$B" "d['access_token']")
[[ -n "$ANALYST_TOKEN" ]] && pass "access_token returned" || fail "access_token missing"
[[ "$(jq_get "$B" "d['role']")" == "analyst" ]] && pass "role=analyst" || fail "wrong role"
EXPIRES=$(jq_get "$B" "d['expires_in']")
python3 -c "assert int('${EXPIRES:-0}') > 0" 2>/dev/null && pass "expires_in=$EXPIRES" || fail "expires_in invalid"

R=$(post "$API/auth/login" '{"username":"admin","password":"admin123"}')
ADMIN_TOKEN=$(jq_get "$(body_of "$R")" "d['access_token']")
[[ "$(status_of "$R")" == "200" && -n "$ADMIN_TOKEN" ]] && pass "admin login → 200" || fail "admin login failed"

R=$(post "$API/auth/login" '{"username":"viewer","password":"viewer123"}')
VIEWER_TOKEN=$(jq_get "$(body_of "$R")" "d['access_token']")
[[ "$(status_of "$R")" == "200" && -n "$VIEWER_TOKEN" ]] && pass "viewer login → 200" || fail "viewer login failed"

[[ "$(status_of "$(post "$API/auth/login" '{"username":"analyst","password":"wrong"}')")" == "401" ]] \
    && pass "bad password → 401" || fail "bad password not rejected"
[[ "$(status_of "$(post "$API/auth/login" '{"username":"analyst"}')")" == "422" ]] \
    && pass "missing password → 422" || fail "missing password not rejected"

section "3. Detect — Happy Path"
TEXT1="Certainly I would be happy to explain how neural networks function. Furthermore it is important to note that these systems consist of multiple layers. In conclusion feel free to ask if you need further clarification about this topic."
R=$(post "$API/detect" "{\"text\":\"${TEXT1}\",\"platform\":\"twitter\",\"actor_id\":\"actor_001\"}" "$ANALYST_TOKEN")
S=$(status_of "$R"); B=$(body_of "$R")
[[ "$S" == "200" ]] && pass "POST /detect (analyst) → 200" || fail "POST /detect → $S: $B"

CONTENT_ID=$(jq_get "$B" "d['content_id']")
RISK=$(jq_get "$B" "d['risk_level']")
CLUSTER=$(jq_get "$B" "d['cluster_id']")
DETECTED=$(jq_get "$B" "d['detected_at']")
AI_PROB=$(jq_get "$B" "d['ai_probability']")

[[ -n "$CONTENT_ID" ]] && pass "content_id: ${CONTENT_ID:0:8}..." || fail "content_id missing"
python3 -c "assert 0 <= float('${AI_PROB:-99}') <= 1" 2>/dev/null && pass "ai_probability in [0,1]: $AI_PROB" || fail "ai_probability invalid: $AI_PROB"
[[ "$RISK" =~ ^(LOW|MEDIUM|HIGH|CRITICAL)$ ]] && pass "risk_level valid: $RISK" || fail "invalid risk_level: $RISK"
[[ "$(jq_get "$B" "d['model_attribution']")" =~ ^(GPT-family|Claude-family|Gemini-family|Unknown)$ ]] \
    && pass "model_attribution valid" || fail "invalid attribution: $(jq_get "$B" "d['model_attribution']")"
[[ "$CLUSTER" =~ ^CL-[0-9A-F]{2}$ ]] && pass "cluster_id CL-XX: $CLUSTER" || fail "bad cluster_id: $CLUSTER"
[[ -n "$DETECTED" && "$DETECTED" != "None" ]] && pass "detected_at non-null: ${DETECTED:0:19}" || fail "detected_at is null — BUG-1 NOT FIXED"
[[ -n "$(jq_get "$B" "d['explanation']")" ]] && pass "explanation present" || fail "explanation missing"

# Idempotency
R2=$(post "$API/detect" "{\"text\":\"${TEXT1}\",\"platform\":\"twitter\",\"actor_id\":\"actor_001\"}" "$ANALYST_TOKEN")
CID2=$(jq_get "$(body_of "$R2")" "d['content_id']")
[[ "$CONTENT_ID" == "$CID2" ]] && pass "idempotency: same text → same content_id" || fail "idempotency broken: $CONTENT_ID ≠ $CID2"

# Second detection
TEXT2="BREAKING Officials confirm emergency protocols activated. Coordinated disinformation across platforms. Share this everywhere before they delete it. The financial system is collapsing now."
R=$(post "$API/detect" "{\"text\":\"${TEXT2}\",\"platform\":\"reddit\",\"actor_id\":\"actor_reddit_99\"}" "$ANALYST_TOKEN")
[[ "$(status_of "$R")" == "200" ]] && pass "second detect → 200" || fail "second detect → $(status_of "$R")"

# Third — no actor_id
TEXT3="The rapid advancement of artificial intelligence has fundamentally transformed information ecosystems. Furthermore notwithstanding recent improvements organizations must remain vigilant. As such recommendations are offered for consideration."
R=$(post "$API/detect" "{\"text\":\"${TEXT3}\",\"platform\":\"manual\"}" "$ANALYST_TOKEN")
[[ "$(status_of "$R")" == "200" ]] && pass "detect without actor_id → 200" || fail "detect no actor → $(status_of "$R")"

section "4. Detect — Validation & RBAC"
[[ "$(status_of "$(post "$API/detect" '{"text":"hi","platform":"twitter"}' "$ANALYST_TOKEN")")" == "422" ]] \
    && pass "text < 10 chars → 422" || fail "short text not rejected"
LONG=$(python3 -c "print('x'*10001)")
[[ "$(status_of "$(post "$API/detect" "{\"text\":\"$LONG\",\"platform\":\"twitter\"}" "$ANALYST_TOKEN")")" == "422" ]] \
    && pass "text > 10000 chars → 422" || fail "long text not rejected"
[[ "$(status_of "$(post "$API/detect" '{"text":"this is a valid length text for platform test","platform":"instagram"}' "$ANALYST_TOKEN")")" == "422" ]] \
    && pass "invalid platform → 422" || fail "invalid platform not rejected"
[[ "$(status_of "$(post "$API/detect" "{\"text\":\"${TEXT1}\",\"platform\":\"twitter\"}" "$VIEWER_TOKEN")")" == "403" ]] \
    && pass "viewer POST /detect → 403" || fail "viewer not blocked from detect"
S=$(status_of "$(curl -s -w "\n%{http_code}" -X POST "$API/detect" -H "Content-Type: application/json" -d "{\"text\":\"${TEXT1}\",\"platform\":\"twitter\"}")")
[[ "$S" == "401" || "$S" == "403" ]] && pass "no token → 401/403" || fail "unauthenticated not blocked: $S"
[[ "$(status_of "$(post "$API/detect" "{\"text\":\"${TEXT1}\",\"platform\":\"email\"}" "$ADMIN_TOKEN")")" == "200" ]] \
    && pass "admin POST /detect → 200" || fail "admin detect failed"

section "5. Dashboard Overview"
R=$(get_req "$API/dashboard/overview?window=24h&limit=20" "$ANALYST_TOKEN")
S=$(status_of "$R"); B=$(body_of "$R")
[[ "$S" == "200" ]] && pass "GET /dashboard/overview (analyst) → 200" || fail "dashboard → $S: $B"

for KEY in stats recent trend graph; do
    python3 -c "import json; d=json.loads(open('/dev/stdin').read()); assert '$KEY' in d" 2>/dev/null <<< "$B" \
        && pass "overview.$KEY present" || fail "overview missing $KEY"
done
for KEY in total_analyzed ai_flagged high_risk campaign_clusters avg_confidence avg_latency_ms; do
    python3 -c "import json,sys; d=json.load(sys.stdin); assert '$KEY' in d['stats']" 2>/dev/null <<< "$B" \
        && pass "stats.$KEY present" || fail "stats.$KEY missing"
done

TOTAL=$(jq_get "$B" "d['stats']['total_analyzed']")
python3 -c "assert int('${TOTAL:-0}') >= 3" 2>/dev/null \
    && pass "total_analyzed=$TOTAL (≥3 from detect calls)" || fail "total_analyzed=$TOTAL too low"

# BUG-1 verification: detected_at never null
python3 -c "
import json,sys
d=json.load(sys.stdin)
bad=[r for r in d['recent'] if not r.get('detected_at')]
sys.exit(len(bad))
" 2>/dev/null <<< "$B" && pass "all recent.detected_at non-null (BUG-1 fixed)" || fail "null detected_at — BUG-1 NOT FIXED"

# Schema BUG-2: confidence in recent
python3 -c "
import json,sys
d=json.load(sys.stdin)
bad=[r for r in d['recent'] if 'confidence' not in r]
sys.exit(len(bad))
" 2>/dev/null <<< "$B" && pass "recent rows have confidence (schema fixed)" || fail "confidence missing from recent"

TREND_LEN=$(jq_get "$B" "len(d['trend'])")
[[ "${TREND_LEN:-0}" -ge 1 ]] && pass "trend has $TREND_LEN buckets" || fail "trend empty"
for KEY in bucket total ai_flagged high_risk; do
    python3 -c "import json,sys; d=json.load(sys.stdin); assert '$KEY' in d['trend'][0]" 2>/dev/null <<< "$B" \
        && pass "trend[0].$KEY present" || fail "trend missing $KEY"
done

NODES=$(jq_get "$B" "len(d['graph']['nodes'])")
LINKS=$(jq_get "$B" "len(d['graph']['links'])")
[[ "${NODES:-0}" -ge 1 ]] && pass "graph has $NODES nodes" || fail "graph nodes empty"
[[ "${LINKS:-0}" -ge 1 ]] && pass "graph has $LINKS links" || fail "graph links empty"

[[ "$(status_of "$(get_req "$API/dashboard/overview" "$VIEWER_TOKEN")")" == "200" ]] \
    && pass "viewer GET /dashboard/overview → 200" || fail "viewer blocked from dashboard"
[[ "$(status_of "$(get_req "$API/dashboard/overview?window=999d" "$ANALYST_TOKEN")")" == "422" ]] \
    && pass "invalid window → 422" || fail "invalid window not rejected"
S=$(status_of "$(curl -s -w "\n%{http_code}" "$API/dashboard/overview")")
[[ "$S" == "401" || "$S" == "403" ]] && pass "no token → 401/403 dashboard" || fail "unauth dashboard not blocked: $S"

section "6. Security"
S=$(status_of "$(get_req "$API/dashboard/overview" "bad.token.value")")
[[ "$S" == "401" || "$S" == "403" ]] && pass "tampered JWT → 401/403" || fail "bad token not rejected: $S"

ERR_BODY=$(body_of "$(post "$API/auth/login" '{"username":"x","password":"y"}')")
echo "$ERR_BODY" | grep -qiE "(Traceback|File \"|raise )" 2>/dev/null \
    && fail "Stack trace leaked!" || pass "No stack trace in error responses"

section "7. ML Integration"
C1=$(jq_get "$(body_of "$(post "$API/detect" "{\"text\":\"${TEXT1}\",\"platform\":\"manual\"}" "$ANALYST_TOKEN")")" "d['cluster_id']")
C2=$(jq_get "$(body_of "$(post "$API/detect" "{\"text\":\"${TEXT1}\",\"platform\":\"reddit\"}" "$ANALYST_TOKEN")")" "d['cluster_id']")
[[ "$C1" == "$C2" ]] && pass "cluster_id deterministic: $C1" || fail "cluster_id not deterministic: $C1 ≠ $C2"

for W in 1h 6h 24h 7d; do
    [[ "$(status_of "$(get_req "$API/dashboard/overview?window=$W" "$ANALYST_TOKEN")")" == "200" ]] \
        && pass "window=$W → 200" || fail "window=$W failed"
done

echo ""
echo "╔════════════════════════════════════════════════════════╗"
printf "║  Results: %-3d passed,  %-3d failed                     ║\n" "$PASS" "$FAIL"
echo "╚════════════════════════════════════════════════════════╝"

if [[ $FAIL -gt 0 ]]; then
    echo -e "\n${RED}FAILURES:${NC}"
    for E in "${ERRORS[@]}"; do echo "  • $E"; done
    echo ""
    exit 1
fi
echo -e "\n${GREEN}🎉  All smoke tests passed. System is demo-ready.${NC}\n"
exit 0