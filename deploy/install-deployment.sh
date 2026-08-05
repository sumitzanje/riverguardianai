#!/bin/sh
set -eu

# Installer for deployment assets. Review commands before execution.
# This script is not run automatically by the repository.

if [ "${1:-}" = "--help" ]; then
  echo "Usage: sudo ./deploy/install-deployment.sh"
  exit 0
fi

install -o root -g root -m 0755 deploy/riverguardian-deploy /usr/local/sbin/riverguardian-deploy
install -o root -g root -m 0755 deploy/riverguardian-migrate-layout /usr/local/sbin/riverguardian-migrate-layout
install -o root -g root -m 0755 deploy/riverguardian-dhcp-renew /usr/local/sbin/riverguardian-dhcp-renew
install -o root -g root -m 0644 deploy/riverguardian.service /etc/systemd/system/riverguardian.service

echo "Next manual step (not performed by this script):"
echo "  sudo visudo -f /etc/sudoers.d/riverguardian-dhcp-renew"
echo "  # then paste content from deploy/riverguardian-dhcp-renew.sudoers"
echo

echo "After sudoers is installed, run:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable riverguardian.service"
echo "  sudo systemctl restart riverguardian.service"
echo
echo "Before first deployment on a host currently using /home/arduino/riverguardianai:"
echo "  sudo /usr/local/sbin/riverguardian-migrate-layout <approved-tag>"
