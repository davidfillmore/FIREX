#!/usr/bin/env bash
# Stage a subset of plots from ~/FIREX/output/<region>/plots/ to ~/Desktop/
# with the region appended to each filename. SLUGS is the *active review
# queue*, not a canonical mirror — once a slug is approved, remove it
# from SLUGS so future syncs don't re-stage it. The canonical copy lives
# in ~/FIREX/output/<region>/plots/. See CLAUDE.md §"Presentation plot
# set" for the workflow. Idempotent.
set -euo pipefail

SLUGS=(dF_sfc_compare dF_toa_compare)
REGIONS=(pacific-northwest eastern-canada eastern-australia eastern-siberia)
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
