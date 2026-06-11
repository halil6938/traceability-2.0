"""Timeline chronologique : ecritures vers le pistolet (handle 0x001c, 0x0019)
+ notifications de mesure (bc 05 00 5f), pour reconstituer le handshake exact."""
import struct
import sys
from pathlib import Path

PATH = sys.argv[1] if len(sys.argv) > 1 else "btcapture/btsnoop_hci.log"
HEADER = bytes.fromhex("bc05005f")
# handles d'interet cote pistolet (vus dans la capture)
CMD_HANDLES = {0x001c, 0x0019, 0x001b, 0x0017}


def records(path):
    data = Path(path).read_bytes()
    assert data[:8] == b"btsnoop\x00"
    off = 16
    out = []
    while off + 24 <= len(data):
        orig_len, incl_len, flags, drops, ts = struct.unpack_from(">IIIIq", data, off)
        off += 24
        out.append((ts, flags, data[off:off + incl_len]))
        off += incl_len
    return out


def main():
    recs = records(PATH)
    t0 = recs[0][0] if recs else 0
    events = []
    for ts, flags, p in recs:
        if len(p) < 9 or p[0] != 0x02:
            continue
        body = p[9:]
        if not body:
            continue
        op = body[0]
        rel = (ts - t0) / 1e6  # secondes
        # ecritures
        if op in (0x12, 0x52) and len(body) >= 3:
            h = struct.unpack_from("<H", body, 1)[0]
            val = body[3:]
            if h in CMD_HANDLES:
                tag = "WRITE_REQ" if op == 0x12 else "WRITE_CMD"
                events.append((rel, f"{tag} h=0x{h:04x}  {val.hex(' ')}"))
        # notifications
        elif op == 0x1b and len(body) >= 3:
            h = struct.unpack_from("<H", body, 1)[0]
            val = body[3:]
            if HEADER in val:
                t = struct.unpack_from("<h", val, val.find(HEADER) + 4)[0] / 10.0
                events.append((rel, f"NOTIFY    h=0x{h:04x}  MESURE {t:.1f}C  {val.hex(' ')}"))

    events.sort(key=lambda e: e[0])
    for rel, txt in events:
        print(f"[{rel:8.3f}s] {txt}")
    print(f"\n{len(events)} evenements pistolet")


main()
