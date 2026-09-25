#!/usr/bin/env bash
# Full build of all radios in sequence: print -> Blender (LODs, baking, textures, MLOD p3d).
#
#   bash tools/build_all.sh [radio ...] [-- Blender flags]    no radio - all six
#   bash tools/build_all.sh uv5r -- --passes albedo           rebake only the color
#   bash tools/build_all.sh -- --skip-bake                    no baking, from work/bake (paths, lod)
#   bash tools/build_all.sh uv5r -- --high-only               detailed model only -> <radio>_high.blend
#
# Writes into the main mod: OpenZone_Radio/model/<radio>/ (data\, model.cfg), MLOD - into the binarize root
# build/model-root/OpenZone_Radio/model/<radio>/. After it, for each radio,
# asset_build(mod="OpenZone_Radio", source="model/<radio>"), then mod_build (dayz-mcp, project
# openzone-radio - repository root).
# Blender and the system Python - paths on this machine (see CLAUDE.md).
set -u
BLENDER="/e/SteamLibrary/steamapps/common/Blender/blender.exe"
PY="/c/Users/Crystal/AppData/Local/Programs/Python/Python312/python.exe"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
declare -A SCRIPT=([uv5r]=uv5r [lxt]=lxt [pmr_t388]=t388 [uvs9]=uvs9 [xts]=xts [prc152]=prc152)
RADIOS=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do RADIOS+=("$1"); shift; done
[ "${1:-}" = "--" ] && shift
EXTRA=("$@")
[ ${#RADIOS[@]} -eq 0 ] && RADIOS=(uv5r lxt pmr_t388 uvs9 xts prc152)

for r in "${RADIOS[@]}"; do
    s=${SCRIPT[$r]}
    d="$ROOT/assets/$r"
    mkdir -p "$d/work"
    t0=$(date +%s)
    (cd "$d/scripts" && "$PY" "make_prints_$s.py" > "$d/work/prints.log" 2>&1) || { echo "$r: prints FAILED"; continue; }
    (cd "$d/scripts" && "$BLENDER" -b -P "build_$s.py" -- --no-high-previews "${EXTRA[@]}" > "$d/work/build_game.log" 2>&1)
    code=$?
    t1=$(date +%s)
    lods=$(grep -a "  LOD [1-4]:" "$d/work/build_game.log" | sed 's/^ *//' | tr '\n' ';')
    err=$(grep -a -c "Traceback\|Error:" "$d/work/build_game.log")
    echo "$r: exit $code, $(( (t1 - t0) / 60 )) min, tracebacks $err | $lods"
done
