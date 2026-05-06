#!/usr/bin/env bash
# Fetch MERRA-2 monthly-mean 2D diagnostics (tavgM_2d_*) from GES DISC.
# Idempotent: existing complete files are skipped, so re-runs resume.
# Future-dated files (latest month not yet produced) return HTTP 4xx and are counted as MISS.
#
# Auth: requires ~/.netrc with an entry for urs.earthdata.nasa.gov:
#     machine urs.earthdata.nasa.gov login <user> password <pass>
#     chmod 600 ~/.netrc
# The user must have authorized "NASA GESDISC DATA ARCHIVE" in their Earthdata profile
# (urs.earthdata.nasa.gov/profile/applications). curl follows the URS redirect dance
# using a cookie jar at ~/.urs_cookies.
#
# Collections fetched (fire-relevant 2D monthly means):
#   aer_Nx (M2TMNXAER) — aerosol diagnostics (BC, OC, SO4, dust, sea salt)
#   slv_Nx (M2TMNXSLV) — single-level surface meteorology (T2M, U10M, V10M, TQV)
#   lnd_Nx (M2TMNXLND) — land surface (soil moisture, runoff, snow)
#   flx_Nx (M2TMNXFLX) — surface turbulent fluxes (PBLH, SHFLX, EFLUX, USTAR)
#   rad_Nx (M2TMNXRAD) — SFC+TOA SW/LW all- and clear-sky fluxes, CLDTOT (CERES analogues)
# Note: there is no 2D monthly CHM collection — chemistry is only available on model
# levels (M2I3NVCHM daily) or pressure levels (M2TMNPCHM monthly 3D). Add separately
# if needed; M2TMNPCHM is large.
set -uo pipefail

BASE_URL="https://goldsmr4.gesdisc.eosdis.nasa.gov/data/MERRA2_MONTHLY"
DEST_ROOT="${MERRA2_DEST_ROOT:-${HOME}/Data/MERRA2_tavgM}"
START_YEAR="${MERRA2_START_YEAR:-2000}"
END_YEAR="${MERRA2_END_YEAR:-2026}"
PARALLEL_MAX="${MERRA2_PARALLEL_MAX:-4}"
# shellcheck disable=SC2206
COLLECTIONS=(${MERRA2_COLLECTIONS:-aer})

if [[ ! -f "${HOME}/.netrc" ]]; then
  echo "missing ~/.netrc — see header of $0 for setup" >&2
  exit 1
fi

mkdir -p "$DEST_ROOT"
LOG="${DEST_ROOT}/_fetch_merra2_monthly.log"
LOCK="${DEST_ROOT}/_fetch_merra2_monthly.lock"
COOKIE_JAR="${HOME}/.urs_cookies"
touch "$COOKIE_JAR"; chmod 600 "$COOKIE_JAR"

if [[ -f "$LOCK" ]] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "fetch_merra2_monthly.sh already running (PID $(cat "$LOCK")); exiting" >&2
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

find "$DEST_ROOT" -name '*.part' -delete 2>/dev/null || true

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG" >&2; }

cur_year=$(date -u +%Y)
cur_month=$(date -u +%m)

got=0; had=0; miss=0; fail=0

# MERRA-2 stream code by year. Stream 401 is forward-processing for very recent data
# not yet bridged into the canonical reanalysis; we try the canonical stream first
# and fall back to 401 on 404 for years 2011+.
merra2_stream_primary() {
  local y=$1
  if   (( y < 1992 )); then echo 100
  elif (( y < 2001 )); then echo 200
  elif (( y < 2011 )); then echo 300
  else                       echo 400
  fi
}
merra2_stream_fallback() {
  local y=$1
  if (( y >= 2011 )); then echo 401; else echo ""; fi
}

# Map short collection code (aer/slv/lnd/flx/rad) → GES DISC product identifier (M2TMNX{ID}).
collection_id() {
  case "$1" in
    aer) echo AER ;;
    slv) echo SLV ;;
    lnd) echo LND ;;
    flx) echo FLX ;;
    rad) echo RAD ;;
    *)   echo "" ;;
  esac
}

# Fetch one file with stream fallback. Returns 0 on got, 1 on had, 2 on miss, 3 on fail.
fetch_one() {
  local coll=$1 y=$2 mm=$3
  local cid; cid=$(collection_id "$coll")
  if [[ -z "$cid" ]]; then log "BAD collection: $coll"; return 3; fi

  local prod="M2TMNX${cid}.5.12.4"
  local fname_base="tavgM_2d_${coll}_Nx.${y}${mm}.nc4"
  local dest_dir="${DEST_ROOT}/${coll}_Nx"
  mkdir -p "$dest_dir"

  # Existing file may have been written under either the primary or the fallback
  # stream; check both names before deciding to download.
  local s_pri s_fb dest_pri dest_fb
  s_pri=$(merra2_stream_primary "$y")
  s_fb=$(merra2_stream_fallback "$y")
  dest_pri="${dest_dir}/MERRA2_${s_pri}.${fname_base}"
  if [[ -s "$dest_pri" ]]; then return 1; fi
  if [[ -n "$s_fb" ]]; then
    dest_fb="${dest_dir}/MERRA2_${s_fb}.${fname_base}"
    if [[ -s "$dest_fb" ]]; then return 1; fi
  fi

  local stream
  for stream in "$s_pri" "$s_fb"; do
    [[ -z "$stream" ]] && continue
    local fname="MERRA2_${stream}.${fname_base}"
    local url="${BASE_URL}/${prod}/${y}/${fname}"
    local dest="${dest_dir}/${fname}"
    local part="${dest}.part"

    local code
    code=$(curl -n -L -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
                --retry 3 --retry-delay 2 \
                --connect-timeout 30 --max-time 600 \
                -fsS -o "$part" -w '%{http_code}' "$url" 2>/dev/null) || code="${code:-000}"

    if [[ -s "$part" && "$code" =~ ^2 ]]; then
      mv "$part" "$dest"
      return 0
    fi
    rm -f "$part"
    if [[ "$code" =~ ^4 ]]; then
      # 404 on primary stream → try fallback; 404 on both → genuine miss
      continue
    fi
    log "FAIL code=${code} ${url}"
    return 3
  done
  return 2
}

main() {
  log "START base=$BASE_URL dest=$DEST_ROOT years=${START_YEAR}..${END_YEAR} colls=${COLLECTIONS[*]}"
  local mm rc
  for y in $(seq "$START_YEAR" "$END_YEAR"); do
    for m in $(seq 1 12); do
      if (( y > cur_year )) || (( y == cur_year && m > 10#$cur_month )); then continue; fi
      mm=$(printf '%02d' "$m")
      for coll in "${COLLECTIONS[@]}"; do
        fetch_one "$coll" "$y" "$mm"
        rc=$?
        case $rc in
          0) got=$((got + 1)) ;;
          1) had=$((had + 1)) ;;
          2) miss=$((miss + 1)) ;;
          3) fail=$((fail + 1)) ;;
        esac
      done
      log "Y${y}/M${mm} cum: got=$got had=$had miss=$miss fail=$fail"
    done
  done
  log "DONE got=$got had=$had miss=$miss fail=$fail"
}

main "$@"
