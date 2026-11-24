#!/usr/bin/env python3
# Gerber query script
# Usage: ./size.py board_edges.gbr
# Written by Matthew Beckler for Wayne and Layne, LLC
# Based on a script from @laen
# Released into the Public Domain. Have fun
# Upgraded to Python3: Jorge Londono

import re
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: %s gerberfile" % sys.argv[0])
        sys.exit()

    filename = sys.argv[1]
    decimals = None   # coordinate decimal digits, from %FS...%
    unit = None       # "MM" or "IN", from %MO...%
    xmin = None
    xmax = None
    ymin = None
    ymax = None

    with open(filename) as f:
        for line in f:
            line = line.strip()

            # Format statement, e.g. %FSLAX46Y46*%  -> 6 decimal digits
            fs = re.search(r"%FSLAX(\d)(\d)Y(\d)(\d)\*%", line)
            if fs:
                decimals = int(fs.group(2))
                continue

            # Unit statement, e.g. %MOMM*% or %MOIN*%
            mo = re.search(r"%MO(MM|IN)\*%", line)
            if mo:
                unit = mo.group(1)
                continue

            # Coordinate data, e.g. X43620000Y-26190000D03*
            results = re.search(r"^X([\d-]+)Y([\d-]+)", line)
            if results:
                x = int(results.group(1))
                y = int(results.group(2))
                xmin = x if xmin is None else min(xmin, x)
                xmax = x if xmax is None else max(xmax, x)
                ymin = y if ymin is None else min(ymin, y)
                ymax = y if ymax is None else max(ymax, y)

    if decimals is None or unit is None:
        sys.exit("Error: %s has no %%FS or %%MO header" % filename)
    if xmin is None:
        sys.exit("Error: no coordinates found in %s" % filename)

    # Convert raw integer coordinates to real units (mm or inches).
    scale = 10.0 ** -decimals
    w = (xmax - xmin) * scale
    h = (ymax - ymin) * scale
    if unit == "MM":
        w_mm, h_mm = w, h
        w_in, h_in = w / 25.4, h / 25.4
    else:
        w_in, h_in = w, h
        w_mm, h_mm = w * 25.4, h * 25.4

    print("Board dimensions:")
    print("  (%.4f, %.4f) inches" % (w_in, h_in))
    print("  (%.4f, %.4f) mm" % (w_mm, h_mm))


if __name__ == "__main__":
    main()
