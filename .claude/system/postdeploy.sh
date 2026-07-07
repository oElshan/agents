#!/usr/bin/env bash
# G9: post-deploy verification через 72ч после production-деплоя. БЕЗ LLM: bash + jq + curl + gh.
# Сверяет реальные метрики с PROD AC (SDC слот #7) из spec. Расхождение → issue Type=tech-debt.
#
# Запуск (cron или CI schedule):  ./postdeploy.sh <issue-number>
# Требует: .claude/board.env; METRICS_URL (или infra.metrics_url в project-profile.md);
#          в spec docs/specs/feature-{N}-*.md блок "PROD AC" в формате:
#            PROD-AC: p95_ms=200 err_rate=0.001 rps=300 metric_prefix=http_server_requests
set -euo pipefail

N="${1:?usage: postdeploy.sh <issue-number>}"
cd "$(git rev-parse --show-toplevel)"
source .claude/board.env

METRICS_URL="${METRICS_URL:-$(grep -E '^\s*metrics_url:' .claude/project-profile.md | head -1 | sed 's/.*metrics_url:[[:space:]]*"\{0,1\}\([^"]*\)"\{0,1\}.*/\1/')}"
[ -z "$METRICS_URL" ] && { echo "G9 SKIP: metrics_url не задан (project-profile.md → infra.metrics_url)"; exit 0; }

SPEC=$(ls docs/specs/feature-${N}-*.md 2>/dev/null | head -1 || true)
[ -z "$SPEC" ] && SPEC=$(grep -rlE "^\s*story:\s*${N}\b" docs/specs/*.md 2>/dev/null | head -1 || true)
[ -z "$SPEC" ] && { echo "G9 SKIP: spec для #$N не найден"; exit 0; }

AC_LINE=$(grep -E '^PROD-AC:' "$SPEC" | head -1 || true)
[ -z "$AC_LINE" ] && { echo "G9 SKIP: строка PROD-AC не найдена в $SPEC"; exit 0; }

get(){ echo "$AC_LINE" | grep -oE "$1=[^ ]+" | cut -d= -f2; }
P95_TARGET=$(get p95_ms); ERR_TARGET=$(get err_rate); PREFIX=$(get metric_prefix)
PREFIX="${PREFIX:-http_server_requests}"

promq(){ curl -sf --max-time 10 "${METRICS_URL}/api/v1/query" --data-urlencode "query=$1" | jq -r '.data.result[0].value[1] // "NaN"'; }

P95_REAL=$(promq "histogram_quantile(0.95, sum(rate(${PREFIX}_seconds_bucket[1h])) by (le)) * 1000")
ERR_REAL=$(promq "sum(rate(${PREFIX}_seconds_count{status=~\"5..\"}[1h])) / sum(rate(${PREFIX}_seconds_count[1h]))")

FAILS=""
awk_gt(){ awk -v a="$1" -v b="$2" 'BEGIN{exit !(a>b)}'; }
[ -n "${P95_TARGET:-}" ] && [ "$P95_REAL" != "NaN" ] && awk_gt "$P95_REAL" "$P95_TARGET" && FAILS="${FAILS}\n- p95: real ${P95_REAL}ms > target ${P95_TARGET}ms"
[ -n "${ERR_TARGET:-}" ] && [ "$ERR_REAL" != "NaN" ] && awk_gt "$ERR_REAL" "$ERR_TARGET" && FAILS="${FAILS}\n- error rate: real ${ERR_REAL} > target ${ERR_TARGET}"

if [ -z "$FAILS" ]; then
  gh issue comment "$N" --body "✅ **G9 post-deploy (+72h): PASS** — p95=${P95_REAL}ms (target ${P95_TARGET:-—}), err=${ERR_REAL} (target ${ERR_TARGET:-—})"
  echo "G9 PASS #$N"
else
  BUG=$(gh issue create \
    --title "[G9] Post-deploy metrics mismatch for #${N}" \
    --body "$(printf 'Реальные метрики за 1h не соответствуют PROD AC из %s:%b\n\nSource story: #%s' "$SPEC" "$FAILS" "$N")" \
    --json number --jq .number 2>/dev/null) || BUG=""
  if [ -n "$BUG" ]; then
    # поля доски — через хелперы протокола (kb_meta недоступен вне агента → минимальный inline)
    gh issue comment "$N" --body "🚫 **G9 post-deploy (+72h): FAIL** — создан #${BUG} (Type=tech-debt).${FAILS}"
    echo "G9 FAIL #$N → tech-debt #$BUG (выставь Type=tech-debt через kb_meta $BUG type=tech-debt)"
  fi
  exit 1
fi
