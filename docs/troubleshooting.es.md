# Problemas conocidos

[English](troubleshooting.md) | Español

## 1. Fallo de los LEDs IR de la DolphinBar

**Problema:** la DolphinBar tiene LEDs infrarrojos que se pueden quemar con facilidad, y entonces no se puede apuntar bien.
**Solución:** cambia los LEDs dañados o cambia la barra por una nueva. Las *IR diagnostics* del calibrator muestran cada dot; con `--experimental-ir-extended` también muestran su tamaño (un LED débil se ve más pequeño).

## 2. Puedo mover el puntero, pero no disparar

**Problema:** si puedes mover el puntero pero no disparar, puede que el driver esté detectando un teclado o un ratón como segunda light gun.
**Solución:** cambia el "mouse index" en los ajustes del emulador para que coincida con el de la light gun y evitar conflictos. La pantalla *Players and buttons* del calibrator muestra la relación LED → VirtualGun → mouse index y las teclas que envía cada botón.

~~~
LED 1 del wiimote  -> mouse index 0 (y 4, 8...)
LED 2 del wiimote  -> mouse index 1
LED 3 del wiimote  -> mouse index 2
LED 4 del wiimote  -> mouse index 3
~~~

El LED muestra el mouse index tal como RetroArch numera los ratones (udev):
cuentan todos los ratones del sistema, en el orden de libudev. Las teclas de
cada pistola son las del jugador con ese mouse index, así que en RetroArch la
pistola funciona para ese jugador sin cambiar nada. El índice se comprueba cada
3 segundos: si se conecta o se quita un ratón, el LED y las teclas lo siguen.
Un Wiimote conectado por Bluetooth conserva su VirtualGun (y su lugar en la
lista) cuando se desconecta y vuelve.

Cuando el driver toma un Wiimote (y cada vez que se reconecta), el Wiimote
vibra un momento y sus LEDs hacen un barrido 1-2-3-4-todos antes de mostrar su
LED. La DolphinBar solo enciende un LED fijo, así que el barrido indica que el
driver ya lo tiene.

## 3. El puntero se vuelve inestable sin motivo aparente

**Problema:** el puntero se mueve de forma errática sin motivo aparente.
**Causa posible:** la luz del sol, una lámpara o un reflejo interfieren con el sensor infrarrojo.
**Solución:** compruébalo con las *IR diagnostics* del calibrator (las fuentes IR de más se dibujan en rojo). Ahora los reflejos y otras fuentes se suelen ignorar; si no, prueba otro nivel de `--ir-sensitivity`.

## 4. Problemas de calibración

**Problema:** cuesta calibrar bien el Wiimote.
**Causas posibles y soluciones:**
- Dos rumbles cortos: se rechazó la captura (pulso inestable o la barra no se veía). Quédate quieto y vuelve a disparar.
- Estás demasiado cerca de la TV: la parte baja de la pantalla queda fuera del alcance de la cámara. Haz el *Reach test* del calibrator; te dice cuánto alejarte.
- Si usas la DolphinBar, puede que uno de sus LEDs IR esté dañado (ver 1).

## 5. El crosshair no llega a los bordes del juego

**Problema:** en juegos 4:3 sobre una TV 16:9, el rango de la pistola cubre toda la TV.
**Solución:** con RetroArch (cores `lr-*`) usa el perfil `full`: RetroArch ya lleva la pistola a la imagen del juego. Con un emulador standalone que estira el rango de la pistola sobre la imagen, usa el area profile `4:3` (`dbar4gun area 4:3`, la opción `--area` o por juego en `profiles.cfg`).
