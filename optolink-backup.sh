#!/bin/bash
set -euo pipefail

SOURCE_DIR="/home/optolink/optolink-splitter"
DEST_HOST="${DEST_HOST:-homeassistant.local}"
DEST_DIR="${DEST_DIR:-/config/optolink-backup}"
SSH_KEY="${SSH_KEY:-/root/.ssh/optolink_ha_backup_ed25519}"
KEEP="${KEEP:-7}"
STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="/tmp/optolink-${STAMP}.tar.zst"
WORK="$(mktemp -d)"

cleanup() { rm -rf "$WORK" "$ARCHIVE"; }
trap cleanup EXIT

mkdir -p "$WORK/etc/systemd/system" "$WORK/etc/default" "$WORK/usr/local/sbin" \
  "$WORK/boot" "$WORK/metadata"
rsync -a --exclude='.git/' --exclude='__pycache__/' --exclude='*.log' \
  --exclude='*.bak*' --exclude='*.before-*' --exclude='viconnlog.txt' \
  "$SOURCE_DIR/" "$WORK/optolink-splitter/"

cp -a /etc/systemd/system/optolinkvs2_switch.service "$WORK/etc/systemd/system/"
cp -a /etc/systemd/system/vitodens_ww_actions.service "$WORK/etc/systemd/system/"
cp -a /etc/systemd/system/optolink-backup.service "$WORK/etc/systemd/system/"
cp -a /etc/systemd/system/optolink-backup.timer "$WORK/etc/systemd/system/"
cp -a /etc/default/optolink-backup "$WORK/etc/default/" 2>/dev/null || true
cp -a /usr/local/sbin/optolink-backup "$WORK/usr/local/sbin/"
cp -a /usr/local/sbin/optolink-backup-status "$WORK/usr/local/sbin/"
cp -a /etc/hostname /etc/os-release "$WORK/metadata/"
cp -a /boot/config.txt /boot/cmdline.txt "$WORK/boot/" 2>/dev/null || true
cp -a /boot/firmware/config.txt /boot/firmware/cmdline.txt "$WORK/boot/" 2>/dev/null || true
dpkg-query -W -f='${binary:Package}\t${Version}\n' > "$WORK/metadata/packages.tsv"
python3 -m pip freeze > "$WORK/metadata/python-requirements.txt" 2>/dev/null || true
systemctl is-enabled optolinkvs2_switch.service vitodens_ww_actions.service \
  > "$WORK/metadata/enabled-services.txt"

cat > "$WORK/RESTORE.txt" <<'EOF'
Optolink restoration summary

1. Install a current Raspberry Pi OS and enable UART.
2. Restore optolink-splitter to /home/optolink/optolink-splitter.
3. Restore the systemd units from etc/systemd/system.
4. Install packages listed under metadata and Python requirements as needed.
5. Restore usr/local/sbin and the optional etc/default/optolink-backup file.
6. Run systemctl daemon-reload and enable the operational services and backup timer.
7. Verify UART wiring, MQTT connectivity and service logs before writing.

The archive contains local credentials. Keep it inside encrypted HA backups.
EOF

tar --zstd -cf "$ARCHIVE" -C "$WORK" .
ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  root@"$DEST_HOST" "mkdir -p '$DEST_DIR'"
scp -i "$SSH_KEY" -o BatchMode=yes "$ARCHIVE" root@"$DEST_HOST":"$DEST_DIR/"
ssh -i "$SSH_KEY" -o BatchMode=yes root@"$DEST_HOST" \
  "cd '$DEST_DIR' && ls -1t optolink-*.tar.zst | tail -n +$((KEEP + 1)) | xargs -r rm --"

ARCHIVE_SIZE="$(stat -c %s "$ARCHIVE")"
/usr/local/sbin/optolink-backup-status "$(date --iso-8601=seconds)" "$ARCHIVE_SIZE"

logger -t optolink-backup "Backup ${STAMP} erfolgreich nach Home Assistant übertragen"
