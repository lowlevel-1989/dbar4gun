#!/bin/sh
# Empareja un Wiimote por Bluetooth (BlueZ) sin tener que saber su MAC.
#
# Uso: pulsar el boton SYNC rojo del Wiimote (debajo de la tapa de las pilas)
# y lanzar enseguida:
#
#     bluez/pair-wiimote.sh            # busca el Wiimote en modo SYNC
#     bluez/pair-wiimote.sh XX:XX:...  # o con una MAC concreta
#
# Mismos pasos que a mano: escanear para que BlueZ vea el Wiimote, emparejar
# con simple-agent (pide el PIN por teclado: Enter sin escribir nada) y
# marcarlo como de confianza para que se reconecte solo al pulsar un boton.

DIR=$(cd "$(dirname "$0")" && pwd)
SCAN_SECONDS=20
MAC="$1"

# sudo antes de escanear: la contrasena no debe comerse los 20 s del modo SYNC
sudo -v || exit 1

bluetoothctl --timeout "$SCAN_SECONDS" scan on >/dev/null 2>&1 &
SCAN=$!
trap 'kill $SCAN 2>/dev/null' EXIT

if [ -z "$MAC" ]; then
    echo "Searching for a Wiimote in SYNC mode (press the red SYNC button)..."
    i=0
    while [ $i -lt "$SCAN_SECONDS" ]; do
        # el primer Wiimote visible que aun no este emparejado
        for m in $(bluetoothctl devices | grep -iE "Nintendo RVL-(CNT|WBC)" | awk '{print $2}'); do
            if ! bluetoothctl info "$m" | grep -q "Paired: yes"; then
                MAC="$m"
                break
            fi
        done
        [ -n "$MAC" ] && break
        sleep 1
        i=$((i + 1))
    done
fi

if [ -z "$MAC" ]; then
    echo "No unpaired Wiimote found. Press the red SYNC button and run it again."
    echo "Already paired before? Remove it first: bluetoothctl remove <MAC>"
    exit 1
fi

echo "Pairing $MAC (if it asks for a PIN code, just press Enter)"
sudo python3 "$DIR/simple-agent" -c DisplayYesNo hci0 "$MAC" || exit 1
bluetoothctl trust "$MAC" >/dev/null
bluetoothctl info "$MAC" | grep -E "Name|Paired|Trusted|Connected"
echo "Done. From now on the Wiimote reconnects when you press any button."
