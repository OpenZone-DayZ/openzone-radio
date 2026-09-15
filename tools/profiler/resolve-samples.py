"""Turn the CSV that sample.ps1 collects into named functions.

sample.ps1 runs on the server's machine and only records addresses, so that box
needs nothing installed and the game process is not touched. This runs anywhere
the executable is available and does the naming, using the function ranges in
the executable's own .pdata plus the handful of names that were established by
reading the disassembly.

    python resolve-samples.py von-samples.csv --exe E:/dayzmod/dayzserver-retail/DayZServer_x64.exe
"""

import argparse
import bisect
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dayz_image as dz

# Named by reading the disassembly; everything else prints as an address.
KNOWN = {
    0x502D10: "frequency lookup leaf (the one hid.dll replaces)",
    0x502EA0: "VON: remove turned-off transmitter (loops ALL players)",
    0x502F70: "VON: EnableBroadcast(bool)",
    0x503070: "VON: update one transmitter against ALL players",
    0x568730: "transmitter network-state serializer",
    0x5685C0: "SetFrequencyByIndex",
    0x568600: "SetNextChannel",
    0x568660: "SetPrevChannel",
    0x6646F0: "VON: listener owner",
    0x870220: "VON: self-listen update",
    0x872D50: "VON: transmitter pass",
    0x8723F0: "world update (per frame: AI, VoN, script events, ...)",
    0x873150: "VON: for each transmitter -> update against all players",
    0x7EC70: "AI world update",
    0x7EB80: "AI spatial grid sweep (re-bucket agents by cell)",
    0x2E01E0: "Enforce script VM: interpreter loop",
    0x2DDC80: "Enforce script VM: call helper",
    0x2E00E0: "Enforce script VM: stack",
    0x2DDDC0: "Enforce script VM: stack guard",
    0x2DDED0: "Enforce script VM",
    0x2DF890: "Enforce script VM: variable access",
    0x2DF9A0: "Enforce script VM: native dispatch",
    0x9D5C40: "Enforce script VM: native call thunk",
    0x9A4570: "VON map: Add(freq)",
    0x9A4FB0: "VON map: Contains(freq)",
    0x9A69A0: "VON map: Remove(freq)",
    0x9AA800: "VON: reconcile listener set (desired list in, stale entries out)",
    0x9D20D0: "VON: per-frame update(dt)",
    0x8735D0: "VON: for-each-player callback of the transmitter pass",
    0x258570: "entity event -> script handler lookup (walks the class chain)",
    0x257F90: "script event handler call (refcounted delegate)",
    0x257E30: "script event handler call (refcounted delegate)",
    0xAAF880: "Bullet: btCollisionWorld::objectQuerySingle (ray/shape cast)",
    0xAB4120: "Bullet: collision shape support (14-way shape switch)",
    0xAC2DA0: "Bullet: dbvt tree traversal",
    0xAB3E70: "Bullet: transform AABB",
    0x2F2AD0: "clock: milliseconds",
}

# Leaves without a .pdata entry: hand-written or unwind-less code that the
# range lookup cannot name. (start, end) -> description.
RAW = [
    (0x2C8A90, 0x2C8AA9, "script: class-chain walk (Cast / IsInherited / type check)"),
    (0x2C8510, 0x2C8532, "script VM: variable slot address"),
    (0x2C8540, 0x2C8554, "script VM: variable slot address"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--exe", default=r"E:\dayzmod\dayzserver-retail\DayZServer_x64.exe")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    img = dz.load(args.exe)
    pd = dz.Pdata(img)
    starts = [e[0] for e in pd.entries]

    per_thread = collections.defaultdict(collections.Counter)
    header = []
    with open(args.csv, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                header.append(line)
                continue
            if line.startswith("tid,"):
                continue
            parts = line.split(",")
            if len(parts) != 4:
                continue
            tid, kind, where, count = parts[0], parts[1], parts[2], int(parts[3])
            if kind == "module":
                per_thread[tid]["[module] " + where] += count
                continue
            rva = int(where, 16)
            i = bisect.bisect_right(starts, rva) - 1
            key = "unknown +0x%X" % rva
            for lo, hi, what in RAW:
                if lo <= rva < hi:
                    key = "+0x%X  %s" % (lo, what)
                    i = -1
                    break
            if i >= 0:
                b, e, _ = pd.entries[i]
                if b <= rva < e:
                    key = "+0x%X" % b
                    if b in KNOWN:
                        key += "  " + KNOWN[b]
            per_thread[tid][key] += count

    for h in header:
        print(h)
    print()

    totals = {t: sum(c.values()) for t, c in per_thread.items()}
    for tid in sorted(totals, key=lambda t: -totals[t]):
        c = per_thread[tid]
        n = totals[tid]
        waiting = sum(
            v
            for k, v in c.items()
            if k.startswith("[module] ntdll") or k.startswith("[module] KERNEL")
        )
        busy = 100.0 * (n - waiting) / max(1, n)
        if busy < 1.0:
            continue  # a thread that only ever waits says nothing
        print("thread %s: %d samples, %.0f%% doing work" % (tid, n, busy))
        for key, cnt in c.most_common(args.top):
            print("    %6.2f%%  %6d  %s" % (100.0 * cnt / max(1, n), cnt, key))
        print()

    idle = [t for t in totals if t not in ()]
    print("threads that only waited are omitted; %d thread(s) seen in total" % len(idle))


if __name__ == "__main__":
    main()
