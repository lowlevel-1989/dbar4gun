"""
Simulador de la camara IR del Wiimote para tests sin hardware.

- camera.py:  vectores y proyeccion pinhole (1024x768, FOV horizontal 33 grados).
- scene.py:   TV 16:9 por pulgadas, barra de 2 dots, jugador; genera reports 0x37.
- payload.py: formato IR basico de 10 bytes (wiibrew) y report 0x37.
- metrics.py: grid 7x7 en el area 4:3, error en px de TV y px de juego.
"""
