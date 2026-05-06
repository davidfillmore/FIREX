#!/usr/bin/env bash
# One-shot sync of new ~/Data content to /Volumes/Io.
# Io is exFAT, so no perm/owner/group preservation; --modify-window=1 for FAT mtime granularity.
set -u

SRC="$HOME/Data"
DST="/Volumes/Io"
LOG="$DST/_sync_to_io.log"
LOCK="$DST/_sync_to_io.lock"

if [[ -e "$LOCK" ]]; then
  pid=$(cat "$LOCK" 2>/dev/null || echo "")
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "another sync running (pid=$pid)"; exit 1
  fi
  rm -f "$LOCK"
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

if [[ ! -d "$DST" ]]; then
  log "ERROR: $DST not mounted"; exit 1
fi

# Common exFAT-safe rsync flags
RFLAGS=(-rltDv --modify-window=1 --human-readable --stats)

run_rsync() {
  local label="$1"; shift
  log "BEGIN $label"
  rsync "${RFLAGS[@]}" "$@" 2>&1 | tee -a "$LOG"
  local rc=${PIPESTATUS[0]}
  log "END   $label (rc=$rc)"
  return $rc
}

# 1. QFED — new top-level dir on Io
run_rsync "QFED (full)"            "$SRC/QFED/"            "$DST/QFED/"

# 2. VIIRS — new top-level dir on Io
run_rsync "VIIRS (full)"           "$SRC/VIIRS/"           "$DST/VIIRS/"

# 3. MERRA2_tavgM — delta only (rsync skips matching files)
run_rsync "MERRA2_tavgM (delta)"   "$SRC/MERRA2_tavgM/"    "$DST/MERRA2_tavgM/"

# 4. MOD08_M3 — delta
run_rsync "MOD08_M3 (delta)"       "$SRC/MOD08_M3/"        "$DST/MOD08_M3/"

# 5. MYD08_M3 — delta
run_rsync "MYD08_M3 (delta)"       "$SRC/MYD08_M3/"        "$DST/MYD08_M3/"

# 6. Optics — full mirror (Mac was reorganized into subdirs; remove flat-file legacy on Io)
run_rsync "Optics (mirror+delete)" --delete "$SRC/Optics/" "$DST/Optics/"

# 7. FIREX merged.nc per region → /Volumes/Io/FIREX/<region>/data/merged.nc.
# Mirrors the local ~/FIREX/output/<region>/data/ layout so other artifacts
# (mask.nc, smoke_attribution.nc, the per-source loader outputs) can be
# slotted in later without restructuring. Region list is auto-discovered
# from the local glob — any region with a merged.nc gets synced.
log "BEGIN FIREX merged datasets"
mkdir -p "$DST/FIREX"
shopt -s nullglob
for src_merged in "$HOME/FIREX/output"/*/data/merged.nc; do
  region=$(basename "$(dirname "$(dirname "$src_merged")")")
  dst_dir="$DST/FIREX/$region/data"
  mkdir -p "$dst_dir"
  run_rsync "FIREX merged.nc ($region)" "$src_merged" "$dst_dir/"
done
shopt -u nullglob
log "END   FIREX merged datasets"

log "ALL DONE"
