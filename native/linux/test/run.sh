#!/bin/sh
# oz_frequencies.so against the stand-in server (fake_server.c).
#
#   member, free   the library must find the lookup, patch it, and every index must
#                  come out as base + index * step -- under every way of compiling
#                  the stand-in listed in FLAGS below
#   registers      the lookup is called with every register a callee may clobber
#                  holding a marker, and all of them must come back
#   inlined        there is no function to redirect: the library must change nothing
#                  and must say NOT PATCHED in its log, with the bytes it looked at
#   profile        the grid in the server's profile wins over the one beside the library
#   stranger       a process that is not DayZServer is left alone and leaves no log
#
# Run from anywhere: sh native/linux/test/run.sh (after native/linux/build.sh).
cd "$(dirname "$0")" || exit 1
SO=$(cd ../../build && pwd)/oz_frequencies.so
[ -f "$SO" ] || { echo "no $SO -- run native/linux/build.sh first"; exit 1; }

CC=${CC:-cc}
WORK=${TMPDIR:-/tmp}/oz-frequencies-test.$$
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

failed=0
check() {  # name, message, command...
    name=$1; msg=$2; shift 2
    if "$@" >/dev/null 2>&1; then
        echo "  ok    $name: $msg"
    else
        echo "  FAIL  $name: $msg"
        failed=1
    fi
}

expected_patched() {
    # base 136.0, step 0.05, count 400 -- native/oz_frequencies.json
    awk 'BEGIN { for (i = 0; i < 12; i++) printf "%d %.3f\n", i, 136.0 + i * 0.05 }'
}

build() {  # directory, variant, flags
    rm -rf "$1"
    mkdir -p "$1/lib" "$1/prof/OpenZone"
    $CC $3 -o "$1/DayZServer" fake_server.c -DVARIANT_$2 || exit 1
    cp "$SO" ../../oz_frequencies.json "$1/lib/"
}

run_patched() {  # directory, output file
    (cd "$1" && LD_PRELOAD="$1/lib/oz_frequencies.so" ./DayZServer -config=serverDZ.cfg -profiles=prof > "$2")
}

site() {  # what the library says it found, for the test's own output
    sed -n 's/.*found: lookup at \(+0x[0-9A-F]*\) (\([0-9]*\) bytes.*index in \([a-z]*\).*/\1, \2 bytes, \3/p' "$1/lib/oz_frequencies.log" | tail -1
}

# One line per way of compiling the stand-in: position-independent and at a fixed
# base, with and without the ENDBR64 landing pad, aligned functions and not.
FLAGS="
-O2
-O2 -fcf-protection=none
-O2 -no-pie -fno-pic
-O3 -no-pie -fno-pic -fcf-protection=none
-O1
-O1 -no-pie -fno-pic
-Os
"

echo "$FLAGS" | while IFS= read -r flags; do
    [ -n "$flags" ] || continue
    for variant in member free; do
        dir="$WORK/shape"
        build "$dir" $variant "$flags"
        (cd "$dir" && ./DayZServer > plain.txt)
        run_patched "$dir" patched.txt
        expected_patched > "$dir/expected.txt"
        check "$variant [$flags]" "every index is base + index * step ($(site "$dir"))" cmp -s "$dir/expected.txt" "$dir/patched.txt"
        check "$variant [$flags]" "unpatched it wraps, and the log says patched" sh -c "grep -q '^9 89.500$' '$dir/plain.txt' && grep -q 'patched: redirected 5 bytes' '$dir/lib/oz_frequencies.log' && grep -q 'channels: 400' '$dir/lib/oz_frequencies.log'"
    done

    dir="$WORK/registers"
    build "$dir" registers "$flags"
    run_patched "$dir" patched.txt
    check "registers [$flags]" "index 9 is 136.450 and all 24 registers come back ($(tail -1 "$dir/patched.txt"))" sh -c "grep -q '^9 136.450$' '$dir/patched.txt' && grep -q '^registers kept: 24 of 24$' '$dir/patched.txt'"
    [ "$failed" = "0" ] || echo failed > "$WORK/failed"
done
[ -f "$WORK/failed" ] && failed=1

echo "inlined:"
dir="$WORK/inlined"
build "$dir" inlined "-O2"
(cd "$dir" && ./DayZServer > plain.txt)
run_patched "$dir" patched.txt
check "inlined" "output unchanged" cmp -s "$dir/plain.txt" "$dir/patched.txt"
check "inlined" "log says NOT PATCHED" grep -q "NOT PATCHED" "$dir/lib/oz_frequencies.log"
check "inlined" "log shows the bytes it looked at" grep -q "reference 1:" "$dir/lib/oz_frequencies.log"
sed 's/^/    | /' "$dir/lib/oz_frequencies.log" | cut -c1-240

echo "profile grid:"
dir="$WORK/profile"
build "$dir" member "-O2"
printf '{ "base_mhz": 400.0, "step_mhz": 0.5, "count": 80 }\n' > "$dir/prof/OpenZone/OZ_Radio_Frequencies.json"
run_patched "$dir" patched.txt
check "profile" "index 3 is 401.500 with the profile's grid" grep -q "^3 401.500$" "$dir/patched.txt"
check "profile" "log says the grid came from the profile" grep -q "grid read from the profile" "$dir/lib/oz_frequencies.log"
sed 's/^/    | /' "$dir/lib/oz_frequencies.log" | cut -c1-240

echo "stranger:"
dir="$WORK/stranger"
build "$dir" member "-O2"
mv "$dir/DayZServer" "$dir/NotTheServer"
(cd "$dir" && LD_PRELOAD="$dir/lib/oz_frequencies.so" ./NotTheServer > out.txt)
check "stranger" "a process with another name is not patched" grep -q "^9 89.500$" "$dir/out.txt"
check "stranger" "and nothing is logged for it" test ! -f "$dir/lib/oz_frequencies.log"
(cd "$dir" && LD_PRELOAD="$dir/lib/oz_frequencies.so" ./NotTheServer -config=serverDZ.cfg > out.txt)
check "stranger" "started like a server under another name, it says so" grep -q "NOT PATCHED: loaded into \"NotTheServer\"" "$dir/lib/oz_frequencies.log"

if [ "$failed" = "0" ]; then
    echo "all checks passed"
else
    echo "SOME CHECKS FAILED"
    exit 1
fi
