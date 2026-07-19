from __future__ import annotations

from pathlib import Path


def default_route_present(route_file: Path = Path("/proc/net/route")) -> bool:
    try:
        lines = route_file.read_text(encoding="utf-8").splitlines()[1:]
    except OSError:
        return True
    for line in lines:
        fields = line.split()
        if len(fields) >= 4 and fields[1] == "00000000":
            try:
                if int(fields[3], 16) & 0x1:
                    return True
            except ValueError:
                return True
    return False
