[Español](lr-mame-pi5.es.md) | English

# lr-mame for Point Blank 2/3, Ghoul Panic and Golgo 13 on a Raspberry Pi 5

The lr-mame that RetroPie installs does not run Point Blank 3 at full speed on a
Raspberry Pi 5 (see the table in [games.md](games.md#raspberry-pi-5-point-blank-3-and-the-lr-mame-version)).
This guide builds lr-mame 0.276 with only the Namco System 10 and 12 drivers and
for the Pi 5 CPU, and adds it to RetroPie as one more emulator. The lr-mame of
RetroPie stays as it is for the rest of the games.

Games covered: Point Blank 2 (`ptblank2`), Point Blank 3 (`ptblank3`), Ghoul
Panic (`ghlpanic`), Golgo 13 (`golgo13`, `g13knd`) and the rest of the Namco
System 10/12 games.

The core keeps the name "MAME" inside RetroArch, so it uses the same core
options as lr-mame (`mame_current_xy_type = "lightgun"`, buttons, ...).

## 1. Build

On the Raspberry Pi 5 itself (or any ARM64 machine with Debian 12 / Raspberry
Pi OS Bookworm). It needs about 3 GB of free disk and can take more than an
hour on the Pi.

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

`-j3` uses 3 of the 4 cores: with 4 GB of RAM, `-j4` can run out of memory.

The options are the ones RetroPie uses for lr-mame, plus `OPTIMIZE=3
ARCHOPTS=-mcpu=cortex-a76` (the Pi 5 CPU) and `SUBTARGET`/`SOURCES` (only the
Namco System 10/12 drivers).

## 2. Install in RetroPie

Without `sudo`, next to your ROMs:

```
mkdir -p ~/RetroPie/cores
cp namco1012_libretro.so ~/RetroPie/cores/mame0276-namco-pi5_libretro.so
echo 'lr-mame0276-namco-pi5 = "/opt/retropie/emulators/retroarch/bin/retroarch -L /home/'"$USER"'/RetroPie/cores/mame0276-namco-pi5_libretro.so --config /opt/retropie/configs/arcade/retroarch.cfg %ROM%"' \
    >> /opt/retropie/configs/lightgun/emulators.cfg
```

Change `lightgun` for the system where you keep these games (for example
`arcade`).

## 3. Use it for these games

Choose `lr-mame0276-namco-pi5` as the emulator of each game: see
[Change the emulator of a game with the Wiimote](games.md#change-the-emulator-of-a-game-with-the-wiimote-retropie).

When RetroPie updates lr-mame, this core does not change.
