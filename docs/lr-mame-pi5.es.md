Español | [English](lr-mame-pi5.md)

# lr-mame para Point Blank 2/3, Ghoul Panic y Golgo 13 en una Raspberry Pi 5

El lr-mame que instala RetroPie no mueve Point Blank 3 a velocidad completa en
una Raspberry Pi 5 (ver la tabla del [README](../README.es.md#raspberry-pi-5-point-blank-3-y-la-versión-de-lr-mame)).
Esta guía compila lr-mame 0.276 solo con los drivers de Namco System 10 y 12 y
para la CPU de la Pi 5, y lo añade a RetroPie como un emulador más. El lr-mame
de RetroPie sigue igual para el resto de juegos.

Juegos que cubre: Point Blank 2 (`ptblank2`), Point Blank 3 (`ptblank3`), Ghoul
Panic (`ghlpanic`), Golgo 13 (`golgo13`, `g13knd`) y el resto de juegos de
Namco System 10/12.

Dentro de RetroArch el core se sigue llamando "MAME", así que usa las mismas
opciones del core que lr-mame (`mame_current_xy_type = "lightgun"`, botones...).

## 1. Compilar

En la propia Raspberry Pi 5 (o en cualquier máquina ARM64 con Debian 12 /
Raspberry Pi OS Bookworm). Necesita unos 3 GB libres en disco y en la Pi puede
tardar más de una hora.

```
sudo apt install build-essential git python3
git clone --depth 1 --branch lrmame0276 https://github.com/libretro/mame.git lr-mame-0276
cd lr-mame-0276
make -j3 OSD=retro RETRO=1 PYTHON_EXECUTABLE=python3 NOWERROR=1 OS=linux \
    TARGETOS=linux CONFIG=libretro NO_USE_MIDI=1 NO_USE_PORTAUDIO=1 TARGET=mame PTR64=1 \
    OPTIMIZE=3 ARCHOPTS=-mcpu=cortex-a76 \
    SUBTARGET=namco1012 SOURCES=src/mame/namco/namcos10.cpp,src/mame/namco/namcos12.cpp
strip namco1012_libretro.so
```

`-j3` usa 3 de los 4 núcleos: con 4 GB de RAM, `-j4` se puede quedar sin
memoria.

Las opciones son las que usa RetroPie para lr-mame, más `OPTIMIZE=3
ARCHOPTS=-mcpu=cortex-a76` (la CPU de la Pi 5) y `SUBTARGET`/`SOURCES` (solo los
drivers de Namco System 10/12).

## 2. Instalar en RetroPie

Sin `sudo`, junto a tus ROMs:

```
mkdir -p ~/RetroPie/cores
cp namco1012_libretro.so ~/RetroPie/cores/mame0276-namco-pi5_libretro.so
echo 'lr-mame0276-namco-pi5 = "/opt/retropie/emulators/retroarch/bin/retroarch -L /home/'"$USER"'/RetroPie/cores/mame0276-namco-pi5_libretro.so --config /opt/retropie/configs/arcade/retroarch.cfg %ROM%"' \
    >> /opt/retropie/configs/lightgun/emulators.cfg
```

Cambia `lightgun` por el sistema donde tengas estos juegos (por ejemplo
`arcade`).

## 3. Usarlo en estos juegos

Elige `lr-mame0276-namco-pi5` como emulador de cada juego: ver
[Cambiar el emulador de un juego con el Wiimote](../README.es.md#cambiar-el-emulador-de-un-juego-con-el-wiimote-retropie).

Cuando RetroPie actualiza lr-mame, este core no cambia.
