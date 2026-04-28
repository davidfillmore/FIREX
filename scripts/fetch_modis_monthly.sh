#!/usr/bin/env bash
# Fetch MODIS C6.1 monthly L3 atmosphere/AOD products (MOD08_M3 Terra + MYD08_M3 Aqua)
# from LAADS DAAC. Stages each product flat at $DEST_ROOT/$product/ to match the
# user's existing layout at ~/Data/MOD08_M3/ and ~/Data/MYD08_M3/.
# Idempotent: existing complete files are skipped, so re-runs resume.
# Future-dated months return HTTP 4xx on the directory listing and are counted as MISS.
#
# Auth: requires a bearer token in ~/.laads_token (single line, no quotes, chmod 600).
# Either token type works in the Authorization header:
#   - LAADS DAAC token (faster, LAADS-only): generate at
#       https://ladsweb.modaps.eosdis.nasa.gov/profiles/#generate-token-modal
#   - Earthdata Login (EDL) token (works on all Earthdata sites, slower for LAADS):
#       generate at https://urs.earthdata.nasa.gov/profile → "Generate Token"
# EDL tokens expire after 60 days; regenerate when listing requests start returning 401.
#
# Filenames embed an unpredictable production timestamp, so we list each month's
# directory via the LAADS .csv listing endpoint, then download every file matching
# the product prefix that we don't already have.
set -uo pipefail

BASE_URL="https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/61"
DEST_ROOT="${MODIS_DEST_ROOT:-${HOME}/Data}"
START_YEAR="${MODIS_START_YEAR:-2000}"
END_YEAR="${MODIS_END_YEAR:-2026}"
PARALLEL_MAX="${MODIS_PARALLEL_MAX:-4}"
# shellcheck disable=SC2206
PRODUCTS=(${MODIS_PRODUCTS:-MOD08_M3 MYD08_M3})

TOKEN_FILE="${HOME}/.laads_token"
if [[ ! -f "$TOKEN_FILE" ]]; then
  echo "missing ~/.laads_token — see header of $0 for setup" >&2
  exit 1
fi
LAADS_TOKEN=$(tr -d '[:space:]' < "$TOKEN_FILE")

mkdir -p "$DEST_ROOT/${PRODUCTS[0]}"
LOG="${DEST_ROOT}/${PRODUCTS[0]}/_fetch_modis_monthly.log"
LOCK="${DEST_ROOT}/${PRODUCTS[0]}/_fetch_modis_monthly.lock"

if [[ -f "$LOCK" ]] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "fetch_modis_monthly.sh already running (PID $(cat "$LOCK")); exiting" >&2
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

find "$DEST_ROOT" -name '*.part' -delete 2>/dev/null || true

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG" >&2; }

cur_year=$(date -u +%Y)
cur_month=$(date -u +%m)

got=0; had=0; miss=0; fail=0

doy_first_of_month() {
  local y=$1 m=$2
  date -j -f "%Y-%m-%d" "$(printf '%04d-%02d-01' "$y" "$m")" +%j
}

# List filenames in a LAADS month directory matching the product prefix.
# Returns 0 with filenames on stdout, non-zero on listing failure or missing dir.
list_files() {
  local product=$1 y=$2 doy=$3
  local url="${BASE_URL}/${product}/${y}/${doy}.csv"
  local code body
  body=$(curl -H "Authorization: Bearer ${LAADS_TOKEN}" \
              --retry 3 --retry-delay 2 \
              --connect-timeout 30 --max-time 60 \
              -sS -w '\n__HTTP__%{http_code}' "$url" 2>/dev/null) || true
  code="${body##*__HTTP__}"
  body="${body%__HTTP__*}"
  if [[ ! "$code" =~ ^2 ]]; then
    [[ "$code" =~ ^4 ]] || log "LIST FAIL code=${code} ${url}"
    return 1
  fi
  # CSV: header line then `name,size,...` rows. Filter to product prefix and .hdf/.nc.
  printf '%s' "$body" | tail -n +2 | awk -F',' -v p="$product" '
    $1 ~ ("^" p "\\.") && ($1 ~ /\.hdf$/ || $1 ~ /\.nc$/) { print $1 }'
  return 0
}

# Fetch all files for one product/Y/M in a single curl --parallel call.
fetch_month() {
  local product=$1 y=$2 mm=$3 doy=$4
  local dest_dir="${DEST_ROOT}/${product}"
  mkdir -p "$dest_dir"

  local -a fnames=()
  local listing
  if ! listing=$(list_files "$product" "$y" "$doy"); then
    miss=$((miss + 1))
    return
  fi
  # shellcheck disable=SC2206
  fnames=( $listing )
  if (( ${#fnames[@]} == 0 )); then
    miss=$((miss + 1))
    return
  fi

  local -a urls=() dests=() cargs=()
  local f dest
  for f in "${fnames[@]}"; do
    dest="${dest_dir}/${f}"
    if [[ -s "$dest" ]]; then
      had=$((had + 1))
      continue
    fi
    urls+=( "${BASE_URL}/${product}/${y}/${doy}/${f}" )
    dests+=( "$dest" )
    cargs+=( -o "${dest}.part" "${BASE_URL}/${product}/${y}/${doy}/${f}" )
  done

  if (( ${#urls[@]} == 0 )); then return; fi

  local report; report=$(mktemp)
  curl -H "Authorization: Bearer ${LAADS_TOKEN}" \
       --parallel --parallel-max "$PARALLEL_MAX" \
       --retry 3 --retry-delay 2 \
       --connect-timeout 30 --max-time 600 \
       -fsS \
       --write-out '%{filename_effective}\t%{http_code}\t%{exitcode}\n' \
       "${cargs[@]}" >"$report" 2>/dev/null || true

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
  log "START base=$BASE_URL dest=$DEST_ROOT years=${START_YEAR}..${END_YEAR} products=${PRODUCTS[*]} parallel_max=${PARALLEL_MAX}"
  local mm doy
  for y in $(seq "$START_YEAR" "$END_YEAR"); do
    for m in $(seq 1 12); do
      if (( y > cur_year )) || (( y == cur_year && m > 10#$cur_month )); then continue; fi
      mm=$(printf '%02d' "$m")
      doy=$(doy_first_of_month "$y" "$m")
      for product in "${PRODUCTS[@]}"; do
        fetch_month "$product" "$y" "$mm" "$doy"
      done
      log "Y${y}/M${mm} (DOY ${doy}) cum: got=$got had=$had miss=$miss fail=$fail"
    done
  done
  log "DONE got=$got had=$had miss=$miss fail=$fail"
}

main "$@"
