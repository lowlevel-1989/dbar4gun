## Manual de configuración de la pistola para juegos de cores concretos

[English](README.md) | Español

Para asignar la configuración de la pistola a un juego, copia el archivo de configuración en:

```
roms/SYSTEMNAME/ROMNAME.cfg
```

**Nota:** el **ROMNAME** incluye la extensión original del archivo antes del `.cfg`. Por ejemplo, para una ROM llamada `House of the Dead 2, The (USA).gdi`, el archivo de configuración se llama `House of the Dead 2, The (USA).gdi.cfg`.

Esta configuración se usa al arrancar esa ROM.

Los cores de MAME usan en cambio su propia configuración de controles (archivos
`.cfg` en la carpeta `cfg` del core, dentro de la carpeta de partidas guardadas de
RetroArch): cada uno indica dónde copiarlo.

### En algunos cores hay que decirle a RetroArch que los dispositivos son pistolas:

1. Pulsa B + Home en el Wiimote para abrir el menú de RetroArch.
2. Entra en el Quick Menu con el botón más.
3. Elige Controls y después Port x Controls.
4. Pon Device Type en Lightgun.
5. Guarda el archivo de remap del juego.

**Nota:** para volver atrás, usa el botón menos.

Mapa de botones de cada gun en MAME y RetroArch: [docs/mapping.es.md](../docs/mapping.es.md).

### Configuraciones disponibles:

#### Mame
- [La Z del Nunchuk como botón 2 en todos los juegos (default.cfg)](mame/README.es.md)
- [Operation Wolf](mame/Operation%20Wolf/README.es.md)
- [Time Crisis](mame/Time%20Crisis/README.es.md)
#### Mame 2015
- [Lucky & Wild](mame2015/Lucky%20%26%20Wild/README.es.md)
#### Dreamcast
- [House of the Dead 2](dreamcast/House%20of%20the%20Dead%202/README.es.md)
