#!/bin/bash
# dbar4gun: lanzar un emulador con un perfil de area y volver al de por defecto.
# Uso: dbar4gun-run.sh <system> <emulator> <rom> -- <comando del emulador...>
# Ejemplo: dbar4gun-run.sh arcade mame ghoul.zip -- mame ghoul
DBAR4GUN="${DBAR4GUN:-dbar4gun}"
system="$1"; emulator="$2"; rom="$3"; shift 3
[ "$1" = "--" ] && shift
"$DBAR4GUN" profile start "$system" "$emulator" "$rom" >/dev/null 2>&1 || true
"$@"
status=$?
"$DBAR4GUN" profile end >/dev/null 2>&1 || true
exit $status
