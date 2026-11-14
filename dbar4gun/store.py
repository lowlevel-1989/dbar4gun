"""
Calibraciones guardadas en JSON, con escritura atomica (tmp + rename) y
un lock entre procesos (cada Wiimote corre en su propio proceso).

Clave por Wiimote:
- Bluetooth: "bt:<MAC>" (HID_UNIQ de sysfs).
- DolphinBar (USB): "usb:<HID_PHYS>" (ruta USB + interfaz = slot de la barra).
Ademas se guarda siempre una entrada "default", que se usa si la clave no existe.
"""

import fcntl
import json
import os

from dbar4gun.core.calibration.data import CalibrationData
from dbar4gun.core.hardware import HardwareConfig

RETROPIE_CONFIGS = "/opt/retropie/configs/all"
FALLBACK_CONFIG_DIR = "/var/lib/dbar4gun"

# directorio de configuracion por plataforma (el primero que exista)
PLATFORM_CONFIGS = [
    ("retropie", RETROPIE_CONFIGS, "dbar4gun"),
]
CALIBRATION_FILE = "calibration.json"
# valores medidos con el calibrator y ultimo informe de hardware
HARDWARE_FILE = "hardware.json"
HARDWARE_REPORT = "hardware_report.json"
DEFAULT_KEY = "default"
# calibraciones anteriores guardadas por Wiimote
HISTORY_MAX = 20

BUS_BLUETOOTH = 0x0005


def default_config_dir(retropie_configs=None, platforms=None):
    """
    RetroPie: /opt/retropie/configs/all/dbar4gun; si no, /var/lib/dbar4gun.
    --config-dir lo cambia. (Batocera y Recalbox quedan fuera por ahora.)
    """
    if retropie_configs is not None:
        platforms = [("retropie", retropie_configs, "dbar4gun")]
    for _, base, sub in (platforms or PLATFORM_CONFIGS):
        if os.path.isdir(base):
            return os.path.join(base, sub)
    return FALLBACK_CONFIG_DIR


def parse_uevent(text):
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def key_from_uevent(info):
    """Clave del Wiimote desde el uevent del dispositivo HID, o None."""
    bus = None
    hid_id = info.get("HID_ID", "")
    if hid_id:
        try:
            bus = int(hid_id.split(":")[0], 16)
        except ValueError:
            bus = None

    uniq = info.get("HID_UNIQ", "").lower()
    phys = info.get("HID_PHYS", "")

    if bus == BUS_BLUETOOTH and uniq and uniq.strip("0:"):
        return "bt:" + uniq
    if phys:
        return "usb:" + phys
    if uniq and uniq.strip("0:"):
        return "bt:" + uniq
    return None


def device_key(hidraw_path, sysfs_root="/sys"):
    """Clave para /dev/hidrawN. Si sysfs no da nada, "hidraw:hidrawN"."""
    name = os.path.basename(hidraw_path)
    path = os.path.join(sysfs_root, "class", "hidraw", name, "device", "uevent")
    try:
        with open(path, "r") as f:
            key = key_from_uevent(parse_uevent(f.read()))
            if key:
                return key
    except (OSError, IOError):
        pass
    return "hidraw:" + name


class CalibrationStore(object):
    def __init__(self, config_dir=None):
        self.config_dir = config_dir or default_config_dir()
        self.path = os.path.join(self.config_dir, CALIBRATION_FILE)
        self.lock_path = os.path.join(self.config_dir, ".calibration.lock")

    def _ensure_dir(self):
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir)
            self._chown_like_parent(self.config_dir)

    def _chown_like_parent(self, path):
        # en RetroPie los configs son del usuario pi; el daemon corre como root
        try:
            st = os.stat(os.path.dirname(os.path.abspath(path)))
            if os.geteuid() == 0:
                os.chown(path, st.st_uid, st.st_gid)
        except OSError:
            pass

    def _read(self):
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("devices"), dict):
                return data
        except (OSError, IOError, ValueError):
            pass
        return {"version": 1, "devices": {}, "history": {}}

    def load(self, key):
        """CalibrationData de `key`, o la entrada default, o None."""
        devices = self._read()["devices"]
        entry = devices.get(key) or devices.get(DEFAULT_KEY)
        if not entry:
            return None
        try:
            return CalibrationData.from_dict(entry)
        except (KeyError, ValueError, TypeError):
            return None

    def _update(self, fn):
        """Lee, modifica con fn(content) y escribe de forma atomica, con lock."""
        self._ensure_dir()
        with open(self.lock_path, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                content = self._read()
                content.setdefault("history", {})
                result = fn(content)
                tmp = self.path + ".tmp.{}".format(os.getpid())
                with open(tmp, "w") as f:
                    json.dump(content, f, indent=2, sort_keys=True)
                    f.flush()
                    os.fsync(f.fileno())
                os.rename(tmp, self.path)
                self._chown_like_parent(self.path)
                return result
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save(self, key, data, add_history=True):
        """
        Guarda la calibracion actual de `key` (y la entrada default). Con
        add_history, ademas la anade al history.
        """
        d = data.to_dict()

        def fn(content):
            content["devices"][key] = d
            content["devices"][DEFAULT_KEY] = d
            hist = content["history"].setdefault(key, [])
            if add_history:
                hist.append({"timestamp": data.timestamp, "calibration": d, "accuracy": None})
                del hist[:-HISTORY_MAX]
            elif hist:
                # p. ej. un ajuste del filter: se actualiza la entrada vigente
                hist[-1]["calibration"] = d
        self._update(fn)

    def history(self, key):
        return list(self._read().get("history", {}).get(key, []))

    def set_accuracy(self, key, accuracy):
        """
        Anota la precision medida (shooting gallery) en la ultima calibracion.
        Con "game" (que se simulo) se guarda ademas por juego en "games", asi
        varias pruebas de la misma calibracion no se pisan.
        """
        def fn(content):
            hist = content["history"].get(key)
            if not hist:
                return False
            prev = hist[-1].get("accuracy") or {}
            acc = dict(accuracy)
            games = dict(prev.get("games") or {})
            if acc.get("game"):
                games[acc["game"]] = {k: v for k, v in acc.items() if k != "game"}
            if games:
                acc["games"] = games
            hist[-1]["accuracy"] = acc
            return True
        return self._update(fn)

    def restore(self, key, index):
        """Vuelve a una calibracion del history. Devuelve CalibrationData o None."""
        def fn(content):
            hist = content["history"].get(key, [])
            if not -len(hist) <= index < len(hist):
                return None
            entry = hist[index]["calibration"]
            content["devices"][key] = entry
            content["devices"][DEFAULT_KEY] = entry
            return entry
        entry = self._update(fn)
        return CalibrationData.from_dict(entry) if entry else None


def _write_atomic(path, text):
    tmp = path + ".tmp.{}".format(os.getpid())
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp, path)


class HardwareStore(CalibrationStore):
    """hardware.json (comun a todos los Wiimotes) y hardware_report.json."""

    def __init__(self, config_dir=None):
        CalibrationStore.__init__(self, config_dir)
        self.hw_path = os.path.join(self.config_dir, HARDWARE_FILE)
        self.report_path = os.path.join(self.config_dir, HARDWARE_REPORT)

    def load_hardware(self):
        try:
            with open(self.hw_path, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return HardwareConfig.from_dict(data)
        except (OSError, IOError, ValueError):
            pass
        return HardwareConfig()

    def _locked_write(self, path, text):
        self._ensure_dir()
        with open(self.lock_path, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                _write_atomic(path, text)
                self._chown_like_parent(path)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def save_hardware(self, hw):
        self._locked_write(self.hw_path, json.dumps(hw.to_dict(), indent=2, sort_keys=True) + "\n")

    def save_report(self, report):
        self._locked_write(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return self.report_path
