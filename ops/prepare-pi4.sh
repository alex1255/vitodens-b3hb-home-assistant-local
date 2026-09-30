#!/usr/bin/env bash
set -euo pipefail

STAGE=/home/pi/vito-pi4-stage
SPLITTER=/home/optolink/optolink-splitter
DISPLAY=/opt/vitodens-display

fail() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail "Bitte mit sudo ausführen."
[[ -r "$STAGE/home/optolink/optolink-splitter/settings_ini.py" ]] || fail "Staging-Dateien fehlen unter $STAGE."

mode=${1:-prepare}
case "$mode" in
  prepare)
    [[ $(dpkg --print-architecture) == arm64 ]] || fail "Erwartet wird ein 64-Bit-Raspberry Pi OS."
    [[ -e /boot/firmware/config.txt && -e /boot/firmware/cmdline.txt ]] || fail "Raspberry-Pi-Bootdateien nicht gefunden."

    if ! getent group optolink >/dev/null; then
      groupadd optolink
    fi
    if ! id optolink >/dev/null 2>&1; then
      getent passwd 1001 >/dev/null && fail "UID 1001 ist bereits belegt."
      useradd --uid 1001 --gid optolink --home-dir /home/optolink --create-home \
        --shell /usr/sbin/nologin optolink
    fi
    usermod -aG dialout,spi,gpio optolink

    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      python3-paho-mqtt python3-serial python3-requests python3-venv \
      python3-pil python3-numpy python3-spidev python3-gpiozero python3-lgpio rsync zstd

    install -d -o optolink -g optolink -m 0755 "$SPLITTER"
    cp -a "$STAGE/home/optolink/optolink-splitter/." "$SPLITTER/"
    chown -R optolink:optolink "$SPLITTER"

    if [[ -e "$DISPLAY" && ! -e /opt/vitodens-display.pi4-dev ]]; then
      mv "$DISPLAY" /opt/vitodens-display.pi4-dev
    elif [[ -e "$DISPLAY" ]]; then
      fail "Pi-4-Entwicklungsumgebung liegt bereits unter /opt/vitodens-display.pi4-dev; nichts überschrieben."
    fi
    install -d -o optolink -g optolink -m 0755 "$DISPLAY"
    cp -a "$STAGE/opt/vitodens-display/." "$DISPLAY/"
    chown -R optolink:optolink "$DISPLAY"
    sed -i 's/^SCALE = 2$/SCALE = 3/' "$DISPLAY/app/vitodens_display.py"

    install -o root -g root -m 0600 "$STAGE/etc/default/vitodens-display" /etc/default/vitodens-display
    install -o root -g root -m 0600 "$STAGE/etc/default/optolink-backup" /etc/default/optolink-backup
    install -d -o root -g root -m 0700 /root/.ssh
    install -o root -g root -m 0600 "$STAGE/root/.ssh/optolink_ha_backup_ed25519" /root/.ssh/
    install -o root -g root -m 0644 "$STAGE/root/.ssh/optolink_ha_backup_ed25519.pub" /root/.ssh/

    install -o root -g root -m 0755 "$STAGE/usr/local/sbin/optolink-backup" /usr/local/sbin/
    install -o root -g root -m 0755 "$STAGE/usr/local/sbin/optolink-backup-status" /usr/local/sbin/
    install -o root -g root -m 0644 "$STAGE/etc/systemd/system/optolinkvs2_switch.service" /etc/systemd/system/
    install -o root -g root -m 0644 "$STAGE/etc/systemd/system/vitodens_ww_actions.service" /etc/systemd/system/
    install -o root -g root -m 0644 "$STAGE/etc/systemd/system/vitodens-display.service" /etc/systemd/system/
    install -o root -g root -m 0644 "$STAGE/etc/systemd/system/optolink-backup.service" /etc/systemd/system/
    install -o root -g root -m 0644 "$STAGE/etc/systemd/system/optolink-backup.timer" /etc/systemd/system/

    config=/boot/firmware/config.txt
    cp -a "$config" "$config.before-optolink-clone-20260930"
    grep -qxF 'dtparam=spi=on' "$config" || printf '\ndtparam=spi=on\n' >> "$config"
    grep -qxF 'enable_uart=1' "$config" || printf 'enable_uart=1\n' >> "$config"
    grep -qxF 'dtoverlay=disable-bt' "$config" || printf 'dtoverlay=disable-bt\n' >> "$config"
    cp -a /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.before-optolink-clone-20260930
    python3 - <<'PY'
from pathlib import Path

path = Path('/boot/firmware/cmdline.txt')
parts = path.read_text().split()
parts = [part for part in parts if not part.startswith('console=serial0,')]
path.write_text(' '.join(parts) + '\n')
PY
    systemctl disable --now hciuart.service serial-getty@ttyAMA0.service 2>/dev/null || true

    hostnamectl set-hostname optolink
    if grep -q '^127\.0\.1\.1[[:space:]]' /etc/hosts; then
      sed -i 's/^127\.0\.1\.1[[:space:]].*/127.0.1.1\toptolink/' /etc/hosts
    else
      printf '127.0.1.1\toptolink\n' >> /etc/hosts
    fi

    systemctl daemon-reload
    printf '\nVorbereitet. Dienste sind absichtlich noch nicht aktiviert.\n'
    printf 'Jetzt den Pi 4 neu starten und danach UART/SPI prüfen.\n'
    printf 'Nach dem physischen Adapterwechsel: sudo %s activate\n' "$0"
    ;;
  activate)
    [[ -e /dev/ttyAMA0 ]] || fail "/dev/ttyAMA0 fehlt; erst Boot-Konfiguration und Neustart prüfen."
    [[ -e /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 ]] || \
      fail "Der Optolink-USB-Adapter ist noch nicht unter seinem erwarteten by-id-Pfad sichtbar."
    systemctl enable --now optolinkvs2_switch.service vitodens_ww_actions.service \
      vitodens-display.service optolink-backup.timer
    systemctl --no-pager --full status optolinkvs2_switch.service \
      vitodens_ww_actions.service vitodens-display.service optolink-backup.timer
    ;;
  *) fail "Aufruf: $0 [prepare|activate]" ;;
esac
