import struct

DOT_ABSENT = 0x3FF

ACC_ZERO = 0x80
ACC_1G = 0x1A   # ~26 cuentas por g en 8 bits (wiibrew)


def ir_basic_payload(dots):
    """
    IR basico de 10 bytes (wiibrew). `dots`: hasta 4 (raw_x, raw_y) o None.

    Byte 0: X1<7:0>, 1: Y1<7:0>, 2: Y1<9:8> X1<9:8> Y2<9:8> X2<9:8>,
         3: X2<7:0>, 4: Y2<7:0>; y lo mismo para los dots 3 y 4.
    """
    dots = list(dots) + [None] * (4 - len(dots))
    out = bytearray()
    for i in (0, 2):
        pair = []
        for d in dots[i:i + 2]:
            if d is None:
                pair.append((DOT_ABSENT, DOT_ABSENT))
            else:
                pair.append((int(d[0]) & 0x3FF, int(d[1]) & 0x3FF))
        (x1, y1), (x2, y2) = pair
        out += bytes([
            x1 & 0xFF,
            y1 & 0xFF,
            ((y1 >> 8) << 6) | ((x1 >> 8) << 4) | ((y2 >> 8) << 2) | (x2 >> 8),
            x2 & 0xFF,
            y2 & 0xFF,
        ])
    return bytes(out)


def acc_bytes(gravity):
    return tuple(max(0, min(255, int(round(ACC_ZERO + ACC_1G * g)))) for g in gravity)


def report_0x37(buttons, acc, ir_payload, ext=b"\x00" * 6):
    """37 BB BB AA AA AA II*10 EE*6 (22 bytes)."""
    assert len(ir_payload) == 10 and len(ext) == 6
    return struct.pack(">BH3B", 0x37, buttons, *acc) + ir_payload + ext
