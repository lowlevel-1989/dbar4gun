"""
Parser del IR basico (10 bytes, wiibrew).

Cada dot se devuelve como (x, y, found) normalizado:
    x = 1 - raw_x / 1023   (invertido: apuntar a la derecha -> x crece)
    y = raw_y / 767
Un dot esta ausente si su Y completa (10 bits) es 0x3FF.
"""

DOT_ABSENT = 0x3FF

RAW_W = 1023.0
RAW_H = 767.0

ABSENT_DOT = (1.0, 1.0, 0.0)


def _decode_pair(b0, b1, b2, b3, b4):
    x1 = b0 | ((b2 & 0x30) << 4)
    y1 = b1 | ((b2 & 0xC0) << 2)
    x2 = b3 | ((b2 & 0x03) << 8)
    y2 = b4 | ((b2 & 0x0C) << 6)
    return (x1, y1), (x2, y2)


def parse_ir_basic_raw(payload):
    """Lista de 4 (raw_x, raw_y) o None si el dot esta ausente."""
    out = []
    for off in (0, 5):
        for x, y in _decode_pair(*payload[off:off + 5]):
            out.append(None if y == DOT_ABSENT else (x, y))
    return out


def normalize(raw):
    if raw is None:
        return ABSENT_DOT
    x = 1.0 - raw[0] / RAW_W
    y = raw[1] / RAW_H
    return (min(1.0, max(0.0, x)), min(1.0, max(0.0, y)), 1.0)


def parse_ir_basic(payload):
    """Lista de 4 dots (x, y, found) normalizados."""
    return [normalize(r) for r in parse_ir_basic_raw(payload)]


def parse_ir_extended_raw(payload):
    """
    IR extendido (12 bytes, 3 por dot, report 0x33):
        X<7:0>, Y<7:0>, Y<9:8> X<9:8> S<3:0>
    Devuelve 4 (raw_x, raw_y, size) o None si el dot esta ausente.
    """
    out = []
    for k in range(4):
        b0, b1, b2 = payload[3 * k:3 * k + 3]
        x = b0 | ((b2 & 0x30) << 4)
        y = b1 | ((b2 & 0xC0) << 2)
        out.append(None if y == DOT_ABSENT else (x, y, b2 & 0x0F))
    return out
