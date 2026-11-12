import io
import logging
import select
import time
import typing

from typing import Tuple
import struct

from dbar4gun.core.parser import parse_ir_basic_raw, parse_ir_extended_raw, normalize
from dbar4gun.core.tracker import SQUARE_Y
from dbar4gun.core.gun import CALIBRATION_BUTTONS_MASK, GunPipeline
from dbar4gun.core.feedback import Rumble

WIIMOTE_CORE_BUTTON_TWO_MASK   = 1 << 0x0
WIIMOTE_CORE_BUTTON_ONE_MASK   = 1 << 0x1
WIIMOTE_CORE_BUTTON_B_MASK     = 1 << 0x2
WIIMOTE_CORE_BUTTON_A_MASK     = 1 << 0x3
WIIMOTE_CORE_BUTTON_MINUS_MASK = 1 << 0x4

WIIMOTE_CORE_BUTTON_UNK_03     = 1 << 0x5
WIIMOTE_CORE_BUTTON_UNK_04     = 1 << 0x6

WIIMOTE_CORE_BUTTON_HOME_MASK  = 1 << 0x7

WIIMOTE_CORE_BUTTON_LEFT_MASK  = 1 << 0x8
WIIMOTE_CORE_BUTTON_RIGHT_MASK = 1 << 0x9
WIIMOTE_CORE_BUTTON_DOWN_MASK  = 1 << 0xa
WIIMOTE_CORE_BUTTON_UP_MASK    = 1 << 0xb
WIIMOTE_CORE_BUTTON_PLUS_MASK  = 1 << 0xc

WIIMOTE_CORE_BUTTON_UNK_00     = 1 << 0xd
WIIMOTE_CORE_BUTTON_UNK_01     = 1 << 0xe
WIIMOTE_CORE_BUTTON_UNK_02     = 1 << 0xf

WIIMOTE_NUNCHUCK_BUTTON_Z_MASK = 1 << 0
WIIMOTE_NUNCHUCK_BUTTON_C_MASK = 1 << 1

WIIMOTE_LED_1 = 0x10
WIIMOTE_LED_2 = 0x20
WIIMOTE_LED_3 = 0x40
WIIMOTE_LED_4 = 0x80

WIIMOTE_REPORT_STATUS_ID   = 0x20
WIIMOTE_REPORT_RESULT_ID   = 0x22
WIIMOTE_REPORT_MODE_X37_ID = 0x37
# D9 (experimental): botones + acelerometro + IR extendido (tamano de los dots)
WIIMOTE_REPORT_MODE_X33_ID = 0x33

# E6: espera maxima de un report en read() (s); el bucle sigue vivo sin datos
READ_TIMEOUT = 0.5
# sin reports o con el mismo report completo repetido durante este tiempo se
# considera el Wiimote desconectado (DolphinBar con el Wiimote apagado)
NO_REPORT_TIMEOUT = 10.0
# intervalo minimo entre reenvios del DRM
DRM_RESEND_INTERVAL = 0.5
# Nunchuk ya conectado al emparejar: el Wiimote solo envia un status (0x20)
# al enchufar/desenchufar la extension, asi que se pide hasta recibir uno
# (con la DolphinBar la primera peticion durante la configuracion del IR
# puede perderse)
STATUS_RETRY_INTERVAL = 1.0
STATUS_RETRIES = 10
# Por Bluetooth, hid-wiimote apaga la camara IR cuando un programa cierra sus
# dispositivos evdev (IR / acelerometro); los reports 0x37 siguen llegando sin
# dots. Se pide el status cada IR_CHECK_INTERVAL s y, si la camara esta
# apagada (bit 0x08 de LF), se vuelve a configurar el IR.
IR_CHECK_INTERVAL = 5.0
STATUS_IR_ON = 0x08
# como mucho una reconfiguracion por camara apagada cada este tiempo: si algun
# hardware no reflejara bien el bit, no se congela el cursor cada 5 s
IR_REENABLE_INTERVAL = 30.0
# reintentos al configurar un Wiimote que no responde (apagado, slot vacio de
# la DolphinBar): cada vez mas espaciados, de 0.2 s a 2 s. Cada intento es una
# escritura que la barra rechaza; sin espaciar eran ~10 por segundo y slot,
# dias seguidos
RESET_BACKOFF_MIN = 0.2
RESET_BACKOFF_MAX = 2.0

# E7: longitud minima de cada report
REPORT_MIN_LEN = {0x20: 7, 0x22: 5, 0x33: 18, 0x37: 22}

log = logging.getLogger("dbar4gun.wiimote")

# C15: bloques de sensibilidad de la camara IR (wiibrew). "marcan" es el que
# usaba la v0.18.2 (por defecto).
IR_SENSITIVITY = {
    "1":      (b"\x02\x00\x00\x71\x01\x00\x64\x00\xfe", b"\xfd\x05"),
    "2":      (b"\x02\x00\x00\x71\x01\x00\x96\x00\xb4", b"\xb3\x04"),
    "3":      (b"\x02\x00\x00\x71\x01\x00\xaa\x00\x64", b"\x63\x03"),
    "4":      (b"\x02\x00\x00\x71\x01\x00\xc8\x00\x36", b"\x35\x03"),
    "5":      (b"\x07\x00\x00\x71\x01\x00\x72\x00\x20", b"\x1f\x03"),
    "marcan": (b"\x00\x00\x00\x00\x00\x00\x90\x00\xc0", b"\x40\x00"),
    "cliff":  (b"\x00\x00\x00\x00\x00\x00\x90\x00\x41", b"\x40\x00"),
}
DEFAULT_IR_SENSITIVITY = "marcan"


def _register_write(offset, data):
    """Output report 0x16: escribir `data` (<= 16 bytes) en el registro 0xb000XX."""
    report = bytearray(22)
    report[0:6] = bytes([0x16, 0x04, 0xb0, 0x00, offset, len(data)])
    report[6:6 + len(data)] = data
    return report


IR_MODE_BASIC    = 0x01
IR_MODE_EXTENDED = 0x03

WIIMOTE_LED_ALL = WIIMOTE_LED_1 | WIIMOTE_LED_2 | WIIMOTE_LED_3 | WIIMOTE_LED_4

# jugador (1..4, = mouse index + 1) -> LED, como en la Wii: el primero, el LED 1.
# Que el driver ya tiene el Wiimote se ve con la senal de conexion (announce)
_PLAYER_LED = {
    1: WIIMOTE_LED_1,
    2: WIIMOTE_LED_2,
    3: WIIMOTE_LED_3,
    4: WIIMOTE_LED_4,
}

# senal de conexion: barrido de LEDs (s desde el inicio, LEDs) y despues el
# LED del jugador. La DolphinBar solo enciende un LED fijo (el de su slot), asi
# que el barrido solo puede venir del driver
ANNOUNCE_LEDS = (
    (0.00, WIIMOTE_LED_1),
    (0.08, WIIMOTE_LED_2),
    (0.16, WIIMOTE_LED_3),
    (0.24, WIIMOTE_LED_4),
    (0.32, WIIMOTE_LED_ALL),
)
ANNOUNCE_END = 0.50


def player_leds(player):
    """
    LEDs para un index de VirtualGun.
    0: todos los LEDs.
    >= 1: ciclo de 4 jugadores, ((player - 1) % 4) + 1.
    El index puede superar 16 (incluye los mouse reales del sistema).
    (0xF, usado como test de conexion, da el jugador 3 -> LED_3)
    """
    if player <= 0:
        return WIIMOTE_LED_ALL
    return _PLAYER_LED[((player - 1) % 4) + 1]


# REF: https://wiibrew.org/wiki/Wiimote
# REF: https://github.com/xwiimote/xwiimote/blob/master/doc/PROTOCOL
class WiiMoteDevice(object):

    # DATA:           37 BB BB AA AA AA II II II II II II II II II II EE EE EE EE EE EE
    # REPORT:         37
    # BUTTONS:        BB BB
    # ACCELEROMETER:  AA AA AA
    # IR:             II II II II II II II II II II
    # PERIPHERAL:     EE EE EE EE EE EE
    REPORT_MODE     = b"\x37"
    DATA_FORMAT_X37 = ">BH3B10sBB3xB"

    # DATA:           22 BB BB RR EE
    # REPORT:         22
    # BUTTONS:        BB BB
    # CB REPORT:      RR
    # ERROR:          EE                0 is ok
    DATA_FORMAT_X22 = ">BHBB"

    # DATA:           20 BB BB LF 00 00 VV
    # LF:             flags (0x02 extension conectada)
    # VV:             bateria (0x00..0xC8)
    BATTERY_MAX = 0xC8

    def __init__(self,
                 hidraw_io : io.FileIO,
                 pipeline : typing.Optional[GunPipeline] = None,
                 ir_sensitivity : str = DEFAULT_IR_SENSITIVITY):

        self.is_pair = False
        self.ir_sensitivity = ir_sensitivity

        # D9: IR basico (report 0x37) o extendido (0x33, sin Nunchuk)
        self.ir_mode     = IR_MODE_BASIC
        self.REPORT_MODE = b"\x37"

        self.pipeline   = pipeline or GunPipeline()
        self.rumble     = Rumble()
        # reloj inyectable (el simulador avanza 10 ms por report)
        self.clock      = time.monotonic
        self.rumble_bit = 0x00

        # callback para guardar: on_save(CalibrationData, add_history)
        self.on_save = None
        # ultimo error de captura (status / GUI)
        self.last_calibration_error = None

        self.io      = hidraw_io
        self.player  = 0

        self.buf = bytearray(struct.calcsize(self.DATA_FORMAT_X37))

        self.core_button = 0x0000
        # botones tal cual llegan (sin la mascara de calibracion), para la GUI
        self.raw_buttons = 0x0000

        # dots en bruto (raw_x, raw_y) o None, y tamano (0xFF = desconocido)
        self.ir_raw   = [None, None, None, None]
        self.ir_sizes = [0xFF, 0xFF, 0xFF, 0xFF]

        # all normalized
        self.core_ir_dot             = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        self.core_ir_dot_sorted      = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        self.core_accelerometer      = [1.0, 1.0, 1.0]
        self.acc_raw                 = None

        self.cursor = (0.5, 0.5)

        self.enable_nunchuck =     False
        self.nunchuck_button =      0x00
        self.nunchuck_joy    = [0.5, 0.5]

        self.battery = None
        # status (0x20) recibido desde el ultimo emparejamiento
        self.status_seen      = False
        self.status_requested = 0
        self.status_req_time  = -1e9
        self.ir_reenable_time = -1e9
        # comprobar la camara IR cada IR_CHECK_INTERVAL s: solo hace falta por
        # Bluetooth (hid-wiimote la apaga); con la DolphinBar el daemon lo
        # desactiva para no escribir a la barra durante dias sin necesidad
        self.ir_check = True
        # pasos pendientes de la senal de conexion: [(t, leds)]
        self.led_anim = []
        # reconfiguracion a proposito (IR sensitivity, irmode, camara apagada por
        # hid-wiimote): sin senal de conexion, que no se ha reconectado nada
        self.quiet_reset = False
        self.reset_backoff = RESET_BACKOFF_MIN
        self.next_reset    = -1e9

        # frecuencia de reports 0x37
        self.hz       = 0.0
        self.hz_count = 0
        self.hz_t0    = time.monotonic()

        self.is_alive_time_last = time.time()

        # E6: deteccion de desconexion (sin reports o report identico repetido)
        self.last_report      = b""
        self.last_change_time = None
        self.last_drm_time    = -1e9

        self.reset()

    @property
    def calibration_on(self) -> int:
        return 1 if self.pipeline.calibrating else 0

    def to_bytes(self, val : int) -> bytearray:
        return bytearray(bytes.fromhex("{:02x}".format(val)))

    def write(self, data) -> None:
        """
        Output report. El bit 0 del primer byte de datos es el rumble en todos
        los reports, asi que se conserva el estado actual del motor.
        """
        data = bytearray(data)
        if len(data) > 1:
            data[1] = (data[1] & 0xFE) | self.rumble_bit
        self.io.write(data)

    def set_tilt_correction(self, enable: bool) -> None:
        self.pipeline.options.tilt_correction = enable

    def enable_ir(self) -> None:

        # ENABLE IR
        # REF: https://www.wiibrew.org/wiki/Wiimote
        # ==== IR Set1 Report (Output) ====
        self.write(bytearray(b"\x13\x04"))
        time.sleep(0.1)

        # ==== IR Set2 Report (Output) ====
        self.write(bytearray(b"\x1a\x04"))
        time.sleep(0.1)

        # DATA: 52 16 CC OO OO OO SS DD DD DD DD DD DD DD DD DD DD DD DD DD DD DD DD
        # CC -> 0x04: Rumble Off but write to Registers
        # DATA:                     16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.write(bytearray(b"\x16\x04\xb0\x00\x30\x01\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)
        # DATA BLOCK 1:             16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        block1, block2 = IR_SENSITIVITY.get(self.ir_sensitivity, IR_SENSITIVITY[DEFAULT_IR_SENSITIVITY])
        self.write(_register_write(0x00, block1))
        time.sleep(0.1)
        # DATA BLOCK 2:             16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.write(_register_write(0x1a, block2))
        time.sleep(0.1)
        # IR MODE:                  16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        mode = bytearray(b"\x16\x04\xb0\x00\x33\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
        mode[6] = self.ir_mode
        self.write(mode)
        time.sleep(0.1)
        # DATA:                     16  CC  OO  OO  OO  SS  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD  DD
        self.write(bytearray(b"\x16\x04\xb0\x00\x30\x01\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"))
        time.sleep(0.1)

        # DATA:           37 BB BB AA AA AA II II II II II II II II II II EE EE EE EE EE EE
        # REPORT:         37
        # BUTTONS:        BB BB
        # ACCELEROMETER:  AA AA AA
        # IR:             II II II II II II II II II II
        # PERIPHERAL:     EE EE EE EE EE EE
        # ==== DRM Set Report (Output) ====
        self.write(bytearray(b"\x12\x00") + bytearray(self.REPORT_MODE))
        time.sleep(1)

    def parser_ir(self, payload : bytes) -> None:
        # C14: ausente si Y (10 bits) == 0x3FF
        self.ir_raw = parse_ir_basic_raw(payload)
        for i, raw in enumerate(self.ir_raw):
            self.core_ir_dot[i] = list(normalize(raw))

    def set_ir_sensitivity(self, level : str) -> None:
        """C15 en caliente: si cambia, se vuelve a configurar la camara IR."""
        if level not in IR_SENSITIVITY or level == self.ir_sensitivity:
            return
        log.info("wiimote %s: IR sensitivity %s -> %s", self.player, self.ir_sensitivity, level)
        self.ir_sensitivity = level
        if self.is_pair:
            self.quiet_reset = True
            self.is_pair = False

    def set_ir_extended(self, enable : bool) -> None:
        """Experimental: cambia al report 0x33 para tener el tamano de los dots."""
        self.ir_mode     = IR_MODE_EXTENDED if enable else IR_MODE_BASIC
        self.REPORT_MODE = b"\x33" if enable else b"\x37"
        self.ir_sizes    = [0xFF, 0xFF, 0xFF, 0xFF]
        self.quiet_reset = True
        self.reset()

    def _ir_frame(self, buttons, acc, now) -> None:
        self.raw_buttons        = buttons
        self.acc_raw            = acc
        self.core_accelerometer = [acc[0] / 0xff, acc[1] / 0xff, acc[2] / 0xff]
        self.cursor, self.core_button = self.pipeline.process(
                self.core_ir_dot, self.acc_raw, buttons, now)
        self.core_ir_dot_sorted = self._tracked_dots()
        self._count_hz(now)

    def set_rumble(self, on : bool) -> None:
        self.rumble_bit = 0x01 if on else 0x00
        self.write(bytearray([0x10, self.rumble_bit]))

    def set_leds(self, leds : int) -> None:
        self.write(bytearray([0x11, leds & 0xF0]))

    def request_status(self) -> None:
        self.write(bytearray(b"\x15\x00"))

    def _status_retry(self, now : float) -> None:
        """
        Pide el status hasta recibir uno tras emparejar (extension y bateria) y,
        despues, cada IR_CHECK_INTERVAL s (camara IR encendida, bateria).
        """
        if not self.is_pair:
            return
        if self.status_seen:
            if not self.ir_check or now - self.status_req_time < IR_CHECK_INTERVAL:
                return
        elif self.status_requested >= STATUS_RETRIES or \
                now - self.status_req_time < STATUS_RETRY_INTERVAL:
            return
        self.status_req_time = now
        self.status_requested += 1
        try:
            self.request_status()
        except OSError as e:
            log.debug("status request: %s", e)

    def announce(self) -> None:
        """
        Senal de que el driver tiene el Wiimote: vibracion corta y barrido de
        LEDs que acaba en el LED del jugador. Sin sleep: avanza con los reports.
        """
        now = self.clock()
        self.rumble.start("connect", now)
        self.led_anim = [(now + t, leds) for t, leds in ANNOUNCE_LEDS]
        self.led_anim.append((now + ANNOUNCE_END, None))     # None: LED del jugador
        self._run_actions(now)

    def _led_animation(self, now : float) -> None:
        if self.pipeline.calibrating:
            # la calibracion usa los LEDs para sus pasos
            self.led_anim = []
            return
        due = None
        while self.led_anim and self.led_anim[0][0] <= now:
            due = self.led_anim.pop(0)[1] or player_leds(self.player)
        if due is not None:
            try:
                self.set_leds(due)
            except OSError as e:
                log.debug("leds: %s", e)

    def _run_actions(self, now : float) -> None:
        for action in self.pipeline.drain_actions():
            kind = action[0]
            if kind == "leds":
                self.set_leds(action[1])
            elif kind == "restore_leds":
                # E12: al terminar la calibracion vuelven los LEDs del jugador
                self.set_leds(player_leds(self.player))
            elif kind == "rumble":
                self.rumble.start(action[1], now)
            elif kind == "calibration_error":
                self.last_calibration_error = action[1]
            elif kind == "save":
                self.last_calibration_error = None
                if self.on_save:
                    try:
                        self.on_save(action[1], action[2] if len(action) > 2 else True)
                    except Exception as e:
                        log.error("calibration save: %s", e)

        self._led_animation(now)

        # C12: el rumble se apaga por timestamp, sin sleep
        state = self.rumble.update(now)
        if state is not None:
            self.set_rumble(state)

    def idle(self) -> None:
        """
        Sin report nuevo (modo de un solo proceso): lo mismo que el timeout de
        read(): deteccion de desconexion (E6) y acciones pendientes (rumble).
        """
        now = self.clock()
        self._check_alive_reports(None, now)
        self._run_actions(now)

    def _tracked_dots(self):
        """TL/TR del tracker en el formato de core_ir_dot (para la GUI)."""
        dots = [[1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0], [1.0, 1.0, 0.0]]
        track = self.pipeline.track
        if track is not None and track.valid:
            for i, (p, rec) in enumerate(((track.tl, track.tl_rec), (track.tr, track.tr_rec))):
                # 1.0 = visto, 0.5 = reconstruido
                dots[i] = [p[0], p[1] / SQUARE_Y, 0.5 if rec else 1.0]
        return dots

    # unsupport python < version 3.12
    # def get_cursor(self) -> Cursor:
    def get_cursor(self) -> Tuple[float, float]:
        return self.cursor

    def _count_hz(self, now : float) -> None:
        self.hz_count += 1
        dt = now - self.hz_t0
        if dt >= 1.0:
            self.hz = self.hz_count / dt
            self.hz_count = 0
            self.hz_t0 = now

    # unsupport python < version 3.12
    # def read(self) -> tuple[
    #        CoreButtons, CoreIRCollection, CoreIRSortCollection, CoreAccelerometer,
    #        NunchuckButtons, NunchuckJoy]:
    def _state(self):
        return [
            self.core_button,
            [d[:] for d in self.core_ir_dot],
            [d[:] for d in self.core_ir_dot_sorted],
            self.core_accelerometer,
            self.nunchuck_button,
            self.nunchuck_joy
        ]

    def _fileno(self):
        try:
            return self.io.fileno()
        except (AttributeError, io.UnsupportedOperation, ValueError, OSError):
            return None

    def _disconnected(self, now : float) -> None:
        """E6: sin reports nuevos: se vuelve a configurar el Wiimote."""
        log.info("wiimote %s: no new reports for %.0f s, reconnecting", self.player, NO_REPORT_TIMEOUT)
        self.is_pair = False
        self.last_change_time = now
        try:
            self.io.write(bytearray(b"\x11\xf0"))
        except OSError as e:
            log.debug("leds: %s", e)

    def _check_alive_reports(self, data, now : float) -> None:
        if self.last_change_time is None:
            self.last_change_time = now
        if data is not None and data != self.last_report:
            self.last_report = data
            self.last_change_time = now
        elif self.is_pair and now - self.last_change_time >= NO_REPORT_TIMEOUT:
            self._disconnected(now)

    # unsupport python < version 3.12
    # def read(self) -> tuple[
    #        CoreButtons, CoreIRCollection, CoreIRSortCollection, CoreAccelerometer,
    #        NunchuckButtons, NunchuckJoy]:
    def read(self, timeout=READ_TIMEOUT):
        """
        Lee y procesa un report. Con `timeout` (E6) espera con select y, si no
        llega nada, devuelve el estado actual (el bucle sigue atendiendo P1).
        """
        if not self.is_pair:
            self.reset()

        fd = self._fileno()
        if timeout is not None and fd is not None:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                now = self.clock()
                self._check_alive_reports(None, now)
                self._run_actions(now)
                return self._state()

        n = self.io.readinto(self.buf)
        now = self.clock()
        # E7: lecturas vacias o cortas no se procesan
        if not n:
            self._check_alive_reports(None, now)
            return self._state()
        report_id = self.buf[0]
        if n < REPORT_MIN_LEN.get(report_id, 1):
            log.debug("short report 0x%02x: %d bytes", report_id, n)
            return self._state()
        self._check_alive_reports(bytes(self.buf[:n]), now)

        # E6: un report de datos que no es el modo pedido: reenviar el DRM
        mode = self.REPORT_MODE[0]
        if 0x30 <= report_id <= 0x3f and report_id != mode and \
                now - self.last_drm_time >= DRM_RESEND_INTERVAL:
            self.last_drm_time = now
            try:
                self.write(bytearray(b"\x12\x00") + bytearray(self.REPORT_MODE))
            except OSError as e:
                log.debug("drm: %s", e)

        if report_id == WIIMOTE_REPORT_RESULT_ID:
            # DATA:      22 BB BB RR EE
            report_id, \
            buttons,   \
            result,    \
            err        = struct.unpack(self.DATA_FORMAT_X22, self.buf[:5])

            # con la misma mascara que el pipeline: durante la calibracion, los
            # ACK de los LEDs y el rumble no deben dejar pasar B al juego
            self.raw_buttons = buttons
            if self.pipeline.calibrating:
                buttons &= CALIBRATION_BUTTONS_MASK
            self.core_button = buttons

        elif report_id == WIIMOTE_REPORT_MODE_X37_ID and mode == WIIMOTE_REPORT_MODE_X37_ID:
            # DATA:            37 BB BB AA AA AA II II II II II II II II II II EE EE EE EE EE EE
            report_id,       \
            buttons,         \
            acc_x,           \
            acc_y,           \
            acc_z,           \
            ir_payload,      \
            nunchuck_joy_x,  \
            nunchuck_joy_y,  \
            nunchuck_buttons = struct.unpack(self.DATA_FORMAT_X37, self.buf)

            self.nunchuck_button = 0x00
            self.nunchuck_joy    = [0.5, 0.5]

            if self.enable_nunchuck:
                self.nunchuck_button    = (nunchuck_buttons & 0x3) ^ 0x3
                self.nunchuck_joy       = [
                    nunchuck_joy_x / 0xff,
                    nunchuck_joy_y / 0xff,
                ]

            self.parser_ir(ir_payload)
            self._ir_frame(buttons, (acc_x, acc_y, acc_z), now)

        elif report_id == WIIMOTE_REPORT_MODE_X33_ID and mode == WIIMOTE_REPORT_MODE_X33_ID:
            # DATA: 33 BB BB AA AA AA II*12
            report_id, buttons, acc_x, acc_y, acc_z, ir_payload = \
                    struct.unpack(">BH3B12s", self.buf[:18])
            raw = parse_ir_extended_raw(ir_payload)
            self.ir_raw   = [None if r is None else (r[0], r[1]) for r in raw]
            self.ir_sizes = [0xFF if r is None else r[2] for r in raw]
            for i, r in enumerate(self.ir_raw):
                self.core_ir_dot[i] = list(normalize(r))
            self.nunchuck_button = 0x00
            self.nunchuck_joy    = [0.5, 0.5]
            self._ir_frame(buttons, (acc_x, acc_y, acc_z), now)

        elif report_id == WIIMOTE_REPORT_STATUS_ID:
            # DATA: 20 BB BB LF 00 00 VV
            self.enable_nunchuck = (self.buf[0x03] & 0xf & 0x02) >> 1
            self.status_seen = True
            # la siguiente comprobacion de la camara, IR_CHECK_INTERVAL s despues
            self.status_req_time = now
            self.battery = min(100, int(self.buf[6] * 100 / self.BATTERY_MAX))
            if self.is_pair and not self.buf[0x03] & STATUS_IR_ON:
                if now - self.ir_reenable_time >= IR_REENABLE_INTERVAL:
                    # la camara IR se apago (hid-wiimote): se reconfigura entera
                    log.info("wiimote %s: IR camera turned off by another driver, enabling it again",
                             self.player)
                    self.ir_reenable_time = now
                    self.quiet_reset = True
                    self.is_pair = False
                    self._run_actions(now)
                    return self._state()
                log.debug("wiimote %s: IR camera reported off again, waiting", self.player)
            # E8: un status report cambia el report mode; basta con reenviar el DRM
            try:
                self.write(bytearray(b"\x12\x00") + bytearray(self.REPORT_MODE))
                self.last_drm_time = now
            except OSError as e:
                log.debug("drm: %s", e)
                self.is_pair = False

        self._status_retry(now)
        self._run_actions(now)
        return self._state()

    def status(self) -> dict:
        st = self.pipeline.status()
        st.update({
            "player":   self.player,
            "paired":   self.is_pair,
            "ir_sensitivity": self.ir_sensitivity,
            # segundos desde el ultimo report distinto (desconexion)
            "report_age": (round(self.clock() - self.last_change_time, 2)
                           if self.last_change_time is not None else None),
            "battery":  self.battery,
            "hz":       round(self.hz, 1),
            "nunchuck": bool(self.enable_nunchuck),
            "last_calibration_error": self.last_calibration_error,
        })
        return st

    def _new_pairing(self) -> None:
        """Camara IR recien configurada: volver a preguntar por la extension."""
        self.status_seen = False
        self.status_requested = 0
        self.status_req_time = -1e9

    def reset(self) -> None:
        now = self.clock()
        if now < self.next_reset:
            return
        try:
            # una sola configuracion del IR (antes update_index la repetia,
            # porque is_pair seguia en False: 1.6 s bloqueado en vez de 0.8)
            self.enable_ir()
            self._new_pairing()
            self.is_pair = True
            self.update_index(self.player)
            self.reset_backoff = RESET_BACKOFF_MIN
            # reconexion: la misma senal que al conectar
            if self.player and self.player != 0xF and not self.quiet_reset:
                self.announce()
            self.quiet_reset = False
        except Exception as e:
            log.debug("reset: %s", e)
            self.is_pair = False
            self.next_reset = now + self.reset_backoff
            self.reset_backoff = min(self.reset_backoff * 2.0, RESET_BACKOFF_MAX)

    # fix slow dolphinbar
    def check_is_alive(self) -> None:
        now = time.time()
        if now - self.is_alive_time_last >= 3:
            self.is_alive_time_last = now
            self.update_index(self.player)

    def update_index(self, player : int =0) -> bool:
        if self.calibration_on > 0:
            return True
        try:
            if not self.is_pair:
                self.enable_ir()
                self._new_pairing()

            # se guarda el index original (1..16), no el reducido,
            # check_is_alive lo reutiliza
            self.player = player
            self.set_leds(player_leds(player))

            self.is_pair = True
            return True
        except Exception as e:
            log.debug("update_index: %s", e)
            self.is_pair = False
            return False
