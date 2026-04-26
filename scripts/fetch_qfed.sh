#!/usr/bin/env bash
# Fetch QFED v2.6r1 0.25-deg biomass-burning emissions from the NCCS portal.
# Idempotent: existing complete files are skipped, so re-runs resume.
# Future-dated files (latest month not yet produced) return HTTP 4xx and are counted as MISS.
# Per-month batches are fetched with `curl --parallel` to amortize TCP/TLS handshake
# across many small files (~250 KB each); set QFED_PARALLEL_MAX to tune (default 4).
set -uo pipefail

BASE_URL="https://portal.nccs.nasa.gov/datashare/iesa/aerosol/emissions/QFED/v2.6r1/0.25/QFED"
DEST_ROOT="${QFED_DEST_ROOT:-${HOME}/Data/QFED}"
START_YEAR="${QFED_START_YEAR:-2020}"
END_YEAR="${QFED_END_YEAR:-2026}"
PARALLEL_MAX="${QFED_PARALLEL_MAX:-4}"
# shellcheck disable=SC2206
SPECIES=(${QFED_SPECIES:-bc oc pm25 co so2 no nh3})

mkdir -p "$DEST_ROOT"
LOG="${DEST_ROOT}/_fetch_qfed.log"
LOCK="${DEST_ROOT}/_fetch_qfed.lock"

if [[ -f "$LOCK" ]] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "fetch_qfed.sh already running (PID $(cat "$LOCK")); exiting" >&2
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

find "$DEST_ROOT" -name '*.part' -delete 2>/dev/null || true

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG" >&2; }

cur_year=$(date -u +%Y)
cur_month=$(date -u +%m)

got=0; had=0; miss=0; fail=0

days_in_month() {
  local y=$1 m=$2 ny=$1 nm
  nm=$(( 10#$m + 1 ))
  if [[ $nm -gt 12 ]]; then nm=1; ny=$((y + 1)); fi
  date -j -v-1d -f "%Y-%m-%d" "$(printf '%04d-%02d-01' "$ny" "$nm")" +%d
}

# Fetch all missing files for one Y/M in a single curl --parallel invocation.
fetch_month() {
  local y=$1 mm=$2 n=$3
  local dest_dir="${DEST_ROOT}/Y${y}/M${mm}"
  mkdir -p "$dest_dir"

  local -a urls=() dests=() cargs=()
  local d dd s fname dest
  for d in $(seq 1 "$n"); do
    dd=$(printf '%02d' "$d")
    for s in "${SPECIES[@]}"; do
      fname="qfed2.emis_${s}.061.${y}${mm}${dd}.nc4"
      dest="${dest_dir}/${fname}"
      if [[ -s "$dest" ]]; then
        had=$((had + 1))
        continue
      fi
      urls+=( "${BASE_URL}/Y${y}/M${mm}/${fname}" )
      dests+=( "$dest" )
      cargs+=( -o "${dest}.part" "${BASE_URL}/Y${y}/M${mm}/${fname}" )
    done
  done

  if (( ${#urls[@]} == 0 )); then return; fi

  local report; report=$(mktemp)
  curl --parallel --parallel-max "$PARALLEL_MAX" \
       --retry 3 --retry-delay 2 \
       --connect-timeout 30 --max-time 120 \
       -fsS \
       --write-out '%{filename_effective}\t%{http_code}\t%{exitcode}\n' \
       "${cargs[@]}" >"$report" 2>/dev/null || true

  # macOS /bin/bash is 3.2 (no associative arrays); look up per-file outcome
  # by grepping the curl report file (TAB-separated: filename, http_code, exitcode).
  local i part line code exc
  for ((i=0; i<${#urls[@]}; i++)); do
    part="${dests[i]}.part"
    line=$(grep -F "${part}"$'\t' "$report" | head -1)
    code=$(printf '%s' "$line" | awk -F'\t' '{print $2}')
    exc=$(printf '%s'  "$line" | awk -F'\t' '{print $3}')
    if [[ "$exc" == "0" && -s "$part" ]]; then
      mv "$part" "${dests[i]}"
      got=$((got + 1))
    else
      rm -f "$part"
      if [[ "$code" =~ ^4 ]]; then
        miss=$((miss + 1))
      else
        fail=$((fail + 1))
        log "FAIL code=${code:-?} exc=${exc:-?} ${urls[i]}"
      fi
    fi
  done
  rm -f "$report"
}

main() {
  log "START base=$BASE_URL dest=$DEST_ROOT years=${START_YEAR}..${END_YEAR} species=${SPECIES[*]} parallel_max=${PARALLEL_MAX}"
  local mm n
  for y in $(seq "$START_YEAR" "$END_YEAR"); do
    for m in $(seq 1 12); do
      if (( y > cur_year )) || (( y == cur_year && m > 10#$cur_month )); then continue; fi
      mm=$(printf '%02d' "$m")
      n=$(days_in_month "$y" "$m")
      log "Y${y}/M${mm} (${n} days)"
      fetch_month "$y" "$mm" "$n"
      log "  cum: got=$got had=$had miss=$miss fail=$fail"
    done
  done
  log "DONE got=$got had=$had miss=$miss fail=$fail"
}

main "$@"
