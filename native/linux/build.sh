#!/bin/sh
# Build the frequency library for the native Linux server.
#
#   sh native/linux/build.sh          -> native/build/oz_frequencies.so
#   sh native/linux/build.sh test     build, then run it against the stand-in server
#
# One C file, the system compiler, no dependency beyond libc. The newest glibc
# symbol version the result asks for is printed at the end: a server whose glibc
# is older than that refuses to load the library, so build on the oldest
# distribution you mean to support (the release is built on the runner's oldest).
set -e
cd "$(dirname "$0")"
mkdir -p ../build

CC=${CC:-cc}
$CC -shared -fPIC -O2 -Wall -Wextra -Werror -o ../build/oz_frequencies.so oz_frequencies.c -ldl
echo "built native/build/oz_frequencies.so ($(wc -c < ../build/oz_frequencies.so) bytes)"

if command -v objdump >/dev/null 2>&1; then
    newest=$(objdump -T ../build/oz_frequencies.so | grep -o 'GLIBC_[0-9.]*' | sort -u -t_ -k2 -V | tail -1)
    echo "newest glibc symbol version required: ${newest:-none}"
fi

if [ "$1" = "test" ]; then
    sh test/run.sh
fi
