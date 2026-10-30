#!/usr/bin/env bash
set -uo pipefail
cd -- "$(dirname -- "$0")" || exit 1
shopt -s nullglob
mkdir -p .handoff/{todo,done,failed} || exit 1
EXTRA=(); for o in --ephemeral --color; do codex exec --help </dev/null 2>/dev/null | grep -q -- "$o" && EXTRA+=("$o"); done; [[ " ${EXTRA[*]-} " == *" --color "* ]] && EXTRA+=(never)
luna() { codex exec -m "${LOG_MODEL:-gpt-6-luna}" --sandbox read-only -c "model_reasoning_effort=\"${LOG_EFFORT:-low}\"" -c project_doc_max_bytes=0 -c 'approval_policy="never"' ${EXTRA[@]+"${EXTRA[@]}"} -; }
field() { sed -n "s/^$1: //p" "$2" | head -n 1; }
risky_repo() {
  local root dir
  root=$(git rev-parse --show-toplevel 2>/dev/null) || return 1
  for dir in "${HOME:-}" "${CODEX_HOME:-${HOME:-}/.codex}"; do
    dir=$(cd -- "${dir:-/nonexistent}" 2>/dev/null && pwd -P) || continue
    [[ "$dir/" == "${root%/}/"* ]] && return 0
  done
  return 1
}
process() {
  local card="$1" step title check body attempt key valid archived
  step=$(field step "$card"); title=$(field title "$card"); check=$(field 확인 "$card")
  archived=".handoff/done/${card##*/}"
  for attempt in 1 2; do
    if [[ "$step" =~ ^[0-9]+$ && -n "$title" && -n "$check" && ! -e "$archived" ]]; then
      if body=$({ cat LUNA.md; printf '\nmode: card\n'; cat "$card"; } | luna) && [[ -n "$body" ]]; then
        valid=1
        for key in step title time '한 일' 근거 숫자 확인 '못 한 것' '맡긴 것' '정한 것' 우려; do
          [[ $'\n'"$body" == *$'\n'"$key: "* ]] || valid=0
        done
        if (( valid )); then
          printf '[%s] step%s %s\n%s\n\n' "$(date '+%Y-%m-%d %H:%M')" "$step" "$title" "$body" >> work.log || break
          mv -- "$card" "$archived" || break
          if risky_repo; then
            echo "자동 커밋 건너뜀: 저장소가 홈이나 Codex 폴더를 품어 세션 파일이 섞인다. 기록은 work.log에 남겼다: $archived" >&2
          else
            git add -A 2>/dev/null && git commit -q -m "step${step}: ${title} | check: ${check}" 2>/dev/null || echo "커밋 실패(git 저장소와 사용자 설정 확인). 기록은 work.log에 남겼다: $archived" >&2
          fi
          return 0
        fi
      fi
    fi
  done
  printf '[%s] step%s %s\n확인: 기록 처리 두 번 실패; 카드 원문\n' "$(date '+%Y-%m-%d %H:%M')" "$step" "$title" >> work.log
  cat -- "$card" >> work.log
  printf '\n\n' >> work.log
  mv -- "$card" ".handoff/failed/${card##*/}"
  return 1
}
scan() {
  local mode="$1" card mtime now scan_failed=0
  for card in .handoff/todo/*.md; do
    if [[ "$mode" == watch ]]; then
      mtime=$(stat -c %Y "$card" 2>/dev/null || stat -f %m "$card") || continue
      now=$(date +%s)
      (( now - mtime >= 10 )) || continue
    fi
    process "$card" || scan_failed=1
  done
  return "$scan_failed"
}
case "${1:-}" in
  report)
    [[ -f work.log && -f DECISIONS.md ]] || { echo "report: work.log와 DECISIONS.md가 있어야 한다" >&2; exit 1; }
    body=$({ cat LUNA.md; printf '\nmode: report\n--- work.log ---\n'; cat work.log; printf '\n--- DECISIONS.md ---\n'; cat DECISIONS.md; printf '\n--- git log --oneline ---\n'; git log --oneline 2>/dev/null || echo '커밋 없음'; } | luna) || exit 1
    [[ -n "$body" ]] || exit 1
    printf '%s\n' "$body" > REPORT.md
    ;;
  watch)
    while :; do scan watch || :; sleep 20; done
    ;;
  '') scan once ;;
  *) printf '사용법: %s [watch|report]\n' "$0" >&2; exit 2 ;;
esac
