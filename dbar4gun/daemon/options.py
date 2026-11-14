"""
Opciones del servicio: las de la linea de comandos, hardware.json y
profiles.cfg, y con ellas las opciones del pipeline de cada Wiimote.
"""

import logging
import os

from dbar4gun.core.area import AreaProfile
from dbar4gun.core.calibration.data import MODE_3PT
from dbar4gun.core.gun import GunOptions, parse_targets
from dbar4gun.core.hardware import HardwareConfig
from dbar4gun.inputgrab import InputGrab
from dbar4gun.store import HardwareStore


log = logging.getLogger("dbar4gun")


class Options(object):
    """Opciones del servicio y del pipeline."""

    # opciones del pipeline desde la CLI (con valores por defecto si faltan)
    def _cfg(self, name, default):
        value = getattr(self.config, name, default)
        return default if value is None else value

    def input_grab(self, key, hidraw_path):
        """
        Bloqueo del mando de botones del kernel (solo Bluetooth: por la
        DolphinBar no hay); --no-input-grab lo desactiva.
        """
        enabled = (key or "").startswith("bt:") and not self._cfg("no_input_grab", False)
        return InputGrab(hidraw_path, enabled=enabled)

    def screen_aspect(self):
        w = self._cfg("width", 1920)
        h = self._cfg("height", 1080)
        return float(w) / float(h) if h else 16.0 / 9.0

    def gun_options(self):
        targets = self._cfg("calibration_targets", None)
        if isinstance(targets, str):
            targets = parse_targets(targets)
        return GunOptions(
            calibration_mode=self._cfg("calibration", MODE_3PT),
            tilt_correction=not self._cfg("disable_tilt_correction", False),
            distance_compensation=not self._cfg("no_distance_compensation", False),
            area=AreaProfile.parse(self.area, self.screen_aspect()),
            useful_zone=self.useful_zone,
            smoothing_level=self._cfg("smoothing_level", 3),
            targets=targets,
            screen_aspect=self.screen_aspect(),
            hardware=self.load_hardware())

    def ir_sensitivity(self, hardware=None):
        """Nivel de la camara IR: el de hardware.json si esta fijado, si no el del servicio."""
        if hardware is not None and hardware.ir_sensitivity:
            return hardware.ir_sensitivity
        return self._cfg("ir_sensitivity", "marcan")

    def load_hardware(self, refresh=False):
        """
        hardware.json (FOV, signo del acelerometro, ancho de barra, IR
        sensitivity). Se lee una vez; `refresh` lo vuelve a leer del disco.
        Devuelve una copia.
        """
        if refresh or self._hardware is None:
            try:
                self._hardware = self.store().load_hardware()
            except Exception as e:
                log.warning("hardware config: %s", e)
                self._hardware = HardwareConfig()
        return self._hardware.copy()

    def store(self):
        return HardwareStore(self._cfg("config_dir", None))

    def profiles_path(self):
        return os.path.join(self.store().config_dir, "profiles.cfg")

    def load_profile_defaults(self):
        """
        profiles.cfg puede fijar el perfil por defecto ("default") y la zona
        util ("useful_zone"); si no, valen las opciones del servicio.
        """
        from dbar4gun import profiles
        table = profiles.load_profiles(self.profiles_path())
        area = table.get("default")
        if area:
            try:
                AreaProfile.parse(area, self.screen_aspect())
                self.area = self.default_area = area
            except ValueError as e:
                log.warning("profiles.cfg default: %s", e)
        uz = table.get("useful_zone")
        if uz:
            try:
                self.useful_zone = min(1.0, max(0.3, float(uz)))
            except ValueError:
                log.warning("profiles.cfg useful_zone: %s", uz)
