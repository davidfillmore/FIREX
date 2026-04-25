#!/usr/bin/env bash
# Fetch QFED v2.6r1 0.25-deg biomass-burning emissions from the NCCS portal.
# Idempotent: existing complete files are skipped, so re-runs resume.
# Future-dated files (latest month not yet produced) return HTTP 4xx and are counted as MISS.
set -uo pipefail

BASE_URL="https://portal.nccs.nasa.gov/datashare/iesa/aerosol/emissions/QFED/v2.6r1/0.25/QFED"
DEST_ROOT="${QFED_DEST_ROOT:-${HOME}/Data/QFED}"
START_YEAR="${QFED_START_YEAR:-2020}"
END_YEAR="${QFED_END_YEAR:-2026}"
# shellcheck disable=SC2206
SPECIES=(${QFED_SPECIES:-bc oc pm25 co so2 no nh3})

mkdir -p "$DEST_ROOT"
LOG="${DEST_ROOT}/_fetch_qfed.log"
find "$DEST_ROOT" -name '*.part' -delete 2>/dev/null || true

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG" >&2; }

cur_year=$(date -u +%Y)
cur_month=$(date -u +%m)

days_in_month() {
  local y=$1 m=$2 ny=$1 nm
  nm=$(( 10#$m + 1 ))
  if [[ $nm -gt 12 ]]; then nm=1; ny=$((y + 1)); fi
  date -j -v-1d -f "%Y-%m-%d" "$(printf '%04d-%02d-01' "$ny" "$nm")" +%d
}

fetch_one() {
  local y=$1 mm=$2 dd=$3 s=$4
  local fname="qfed2.emis_${s}.061.${y}${mm}${dd}.nc4"
  local url="${BASE_URL}/Y${y}/M${mm}/${fname}"
  local dest_dir="${DEST_ROOT}/Y${y}/M${mm}"
  local dest="${dest_dir}/${fname}"

  if [[ -s "$dest" ]]; then return 100; fi
  mkdir -p "$dest_dir"
  if curl -fsS --retry 3 --retry-delay 2 --connect-timeout 30 \
        -o "${dest}.part" "$url"; then
    mv "${dest}.part" "$dest"
    return 0
  fi
  local rc=$?
  rm -f "${dest}.part"
  return $rc
}

main() {
  log "START base=$BASE_URL dest=$DEST_ROOT years=${START_YEAR}..${END_YEAR} species=${SPECIES[*]}"
  local got=0 had=0 miss=0 fail=0 mm n d dd s rc
  for y in $(seq "$START_YEAR" "$END_YEAR"); do
    for m in $(seq 1 12); do
      if (( y > cur_year )) || (( y == cur_year && m > 10#$cur_month )); then continue; fi
      mm=$(printf '%02d' "$m")
      n=$(days_in_month "$y" "$m")
      log "Y${y}/M${mm} (${n} days)"
      for d in $(seq 1 "$n"); do
        dd=$(printf '%02d' "$d")
        for s in "${SPECIES[@]}"; do
          fetch_one "$y" "$mm" "$dd" "$s"
          rc=$?
          case $rc in
            0)   got=$((got + 1))  ;;
            100) had=$((had + 1))  ;;
            22)  miss=$((miss + 1)) ;;
            *)   fail=$((fail + 1)); log "FAIL rc=$rc Y${y}/M${mm}/${dd} ${s}" ;;
          esac
        done
      done
      log "  cum: got=$got had=$had miss=$miss fail=$fail"
    done
  done
  log "DONE got=$got had=$had miss=$miss fail=$fail"
}

main "$@"
