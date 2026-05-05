#!/usr/bin/env bash
# Mirror the curated presentation plot set from ~/FIREX/output/<region>/plots/
# to ~/Desktop/ with the region appended to each filename. Idempotent.
set -euo pipefail

SLUGS=(aod_sfc aod_sfc_all aod_toa aod_toa_all qfed_smoke_aod qfed_vs_smoke_aod_scatter smoke_radiative_efficiency)
REGIONS=(pacific-northwest eastern-australia)
EXTS=(png pdf)

src_root="${HOME}/FIREX/output"
dst="${HOME}/Desktop"

copied=0
missing=0
for region in "${REGIONS[@]}"; do
  for slug in "${SLUGS[@]}"; do
    for ext in "${EXTS[@]}"; do
      src="${src_root}/${region}/plots/${slug}.${ext}"
      out="${dst}/${slug}_${region}.${ext}"
      if [[ -f "$src" ]]; then
        cp "$src" "$out"
        copied=$((copied + 1))
      else
        echo "missing: $src" >&2
        missing=$((missing + 1))
      fi
    done
  done
done

# Region map is region-agnostic; one copy at the top level of output/.
for ext in "${EXTS[@]}"; do
  src="${src_root}/region_map.${ext}"
  out="${dst}/region_map.${ext}"
  if [[ -f "$src" ]]; then
    cp "$src" "$out"
    copied=$((copied + 1))
  else
    echo "missing: $src" >&2
    missing=$((missing + 1))
  fi
done

echo "synced ${copied} files to ${dst}"
if (( missing > 0 )); then
  echo "warning: ${missing} expected sources were missing" >&2
  exit 1
fi
