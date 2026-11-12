"""
P2: perfil de area por juego/system/emulator desde runcommand de RetroPie.

profiles.cfg (formato "clave = perfil", # para comentarios). Prioridad:

    rom:<nombre de la rom sin extension>
    <system>/<emulator>
    <emulator>
    <system>
    default

Los hooks se instalan en runcommand-onstart.sh / runcommand-onend.sh dentro de
un bloque delimitado, de forma idempotente y sin tocar el resto del archivo.
"""

import os

from dbar4gun.store import RETROPIE_CONFIGS, default_config_dir

PROFILES_FILE = "profiles.cfg"
BLOCK_BEGIN = "# >>> dbar4gun >>>"
BLOCK_END = "# <<< dbar4gun <<<"
DEFAULT_BIN = "/opt/retropie/supplementary/dbar4gun/bin/dbar4gun"

DEFAULT_PROFILES = """# dbar4gun: perfil de area del gun por juego, system o emulator.
# Perfiles: full, 4:3 (cualquier a:b), custom:x0,y0,w,h (normalizado a la TV).
# Prioridad: rom:<rom sin extension> > system/emulator > emulator > system > default
# Sin coincidencia se usa el perfil por defecto del servicio (opcion --area).
#
# RetroArch (todos los cores lr-*, por ejemplo lr-mame, lr-mame2003-plus,
# lr-mame2016 o lr-flycast) convierte la posicion del gun a la imagen del juego,
# tambien un 4:3 dentro de una TV 16:9, y fuera de la imagen es "offscreen"
# (recargar). Con ellos va "full": un 4:3 aqui lo corregiria dos veces.
#
# Los emuladores standalone que estiran el rango del gun sobre la imagen del
# juego necesitan el aspecto del juego. Sin verificar con cada uno:
# mame = 4:3
# advmame = 4:3
# flycast = full

# default = full

# ejemplo por juego:
# rom:luckywld = custom:0.125,0,0.75,1
"""


def default_profiles_path():
    """profiles.cfg en el directorio de configuracion de la plataforma."""
    return os.path.join(default_config_dir(), PROFILES_FILE)


def parse_profiles(text):
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().strip('"').lower()
        value = value.strip().strip('"')
        if key and value:
            out[key] = value
    return out


def load_profiles(path):
    try:
        with open(path, "r") as f:
            return parse_profiles(f.read())
    except (OSError, IOError):
        return {}


def rom_name(rom):
    base = os.path.basename(rom or "")
    return os.path.splitext(base)[0].lower()


def resolve_profile(profiles, system=None, emulator=None, rom=None, fallback="default"):
    """Perfil para el juego; "default" = el perfil por defecto del servicio."""
    system = (system or "").lower()
    emulator = (emulator or "").lower()
    keys = []
    if rom:
        keys.append("rom:" + rom_name(rom))
    if system and emulator:
        keys.append(system + "/" + emulator)
    if emulator:
        keys.append(emulator)
    if system:
        keys.append(system)
    keys.append("default")
    for k in keys:
        if k in profiles:
            return profiles[k]
    return fallback


# ----------------------------------------------------------------------
# hooks de runcommand
def hook_block(bin_path, event):
    """Bloque para runcommand-onstart.sh (event="start") u onend.sh ("end")."""
    if event == "start":
        call = '"{}" profile start "$1" "$2" "$3"'.format(bin_path)
    else:
        call = '"{}" profile end'.format(bin_path)
    return "\n".join([
        BLOCK_BEGIN,
        'if [ -x "{}" ]; then'.format(bin_path),
        "    {} >/dev/null 2>&1 || true".format(call),
        "fi",
        BLOCK_END,
    ]) + "\n"


def remove_block(text):
    """Quita el bloque de dbar4gun (si esta) sin tocar el resto."""
    lines = text.splitlines(True)
    out = []
    inside = False
    for line in lines:
        s = line.strip()
        if s == BLOCK_BEGIN:
            inside = True
            continue
        if s == BLOCK_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "".join(out)


def _chown_like_parent(path):
    try:
        st = os.stat(os.path.dirname(os.path.abspath(path)))
        if os.geteuid() == 0:
            os.chown(path, st.st_uid, st.st_gid)
    except OSError:
        pass


def _write(path, text, mode=None):
    existed = os.path.exists(path)
    tmp = path + ".dbar4gun.tmp"
    with open(tmp, "w") as f:
        f.write(text)
    if existed:
        st = os.stat(path)
        os.chmod(tmp, st.st_mode & 0o7777)
        try:
            os.chown(tmp, st.st_uid, st.st_gid)
        except OSError:
            pass
    elif mode is not None:
        os.chmod(tmp, mode)
    os.rename(tmp, path)
    if not existed:
        _chown_like_parent(path)


def install_hooks(configs_dir=RETROPIE_CONFIGS, bin_path=DEFAULT_BIN):
    """Instala (o actualiza) los bloques. Devuelve los archivos tocados."""
    if not os.path.isdir(configs_dir):
        raise OSError("{} not found (is this RetroPie?)".format(configs_dir))
    touched = []
    for event, name in (("start", "runcommand-onstart.sh"), ("end", "runcommand-onend.sh")):
        path = os.path.join(configs_dir, name)
        text = ""
        if os.path.exists(path):
            with open(path, "r") as f:
                text = f.read()
        body = remove_block(text)
        if not body.strip():
            body = "#!/usr/bin/env bash\n"
        if not body.endswith("\n"):
            body += "\n"
        new = body + hook_block(bin_path, event)
        if new != text:
            _write(path, new, 0o755)
            touched.append(path)

    profiles = os.path.join(configs_dir, "dbar4gun", PROFILES_FILE)
    if not os.path.exists(profiles):
        d = os.path.dirname(profiles)
        if not os.path.isdir(d):
            os.makedirs(d)
            _chown_like_parent(d)
        _write(profiles, DEFAULT_PROFILES, 0o644)
        touched.append(profiles)
    return touched


def uninstall_hooks(configs_dir=RETROPIE_CONFIGS):
    """Quita solo los bloques de dbar4gun. profiles.cfg se conserva."""
    touched = []
    for name in ("runcommand-onstart.sh", "runcommand-onend.sh"):
        path = os.path.join(configs_dir, name)
        if not os.path.exists(path):
            continue
        with open(path, "r") as f:
            text = f.read()
        new = remove_block(text)
        if new != text:
            _write(path, new)
            touched.append(path)
    return touched


def set_entry(path, key, value):
    """
    D15: fija "key = value" en profiles.cfg sin tocar el resto: reemplaza la
    linea activa de esa clave o la anade al final.
    """
    lines = []
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.read().splitlines(True)
    new = "{} = {}\n".format(key, value)
    done = False
    for i, line in enumerate(lines):
        body = line.split("#", 1)[0]
        if "=" in body and body.split("=", 1)[0].strip().lower() == key.lower():
            lines[i] = new
            done = True
            break
    if not done:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(new)
    d = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(d):
        os.makedirs(d)
    _write(path, "".join(lines), 0o644)
