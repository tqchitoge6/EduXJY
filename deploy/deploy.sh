#!/usr/bin/env bash
# Deploy EduXJY to a fresh Ubuntu/Debian or RHEL-family host.
# Run as root after the repository is placed at /opt/EduXJY and .env is filled.
set -euo pipefail

APP_DIR="/opt/EduXJY"
APP_USER="eduxjy"
HOSTNAME_VALUE="xiaojunyang"
PUBLIC_IP="121.40.192.55"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Please run as root." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/manage.py" ]]; then
  echo "$APP_DIR/manage.py not found; clone the repository there first." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "$APP_DIR/.env not found; copy deploy/env.production.example and fill it." >&2
  exit 1
fi

hostnamectl set-hostname "$HOSTNAME_VALUE"
if grep -q '^127\.0\.1\.1' /etc/hosts; then
  sed -i "s/^127\.0\.1\.1.*/127.0.1.1 ${HOSTNAME_VALUE}/" /etc/hosts
else
  echo "127.0.1.1 ${HOSTNAME_VALUE}" >> /etc/hosts
fi

if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y python3 python3-venv python3-pip nginx git make
  NGINX_SITE="/etc/nginx/sites-available/eduxjy"
  NGINX_LINK="/etc/nginx/sites-enabled/eduxjy"
  NGINX_GROUP="www-data"
  SERVICE_GROUP="www-data"
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3 python3-pip nginx git make
  NGINX_SITE="/etc/nginx/conf.d/eduxjy.conf"
  NGINX_LINK=""
  NGINX_GROUP="nginx"
  SERVICE_GROUP="nginx"
else
  echo "Unsupported package manager; install Python 3.10+, nginx, git, make manually." >&2
  exit 1
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

# The repository is owned by the app user, so run its Makefile as that user.
sudo -u "$APP_USER" -H make -C "$APP_DIR" install
sudo -u "$APP_USER" -H "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate
sudo -u "$APP_USER" -H "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput
sudo -u "$APP_USER" -H "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" seed_demo

install -m 644 "$APP_DIR/deploy/eduxjy.service" /etc/systemd/system/eduxjy.service
sed -i "s/^Group=www-data$/Group=${SERVICE_GROUP}/" /etc/systemd/system/eduxjy.service
systemctl daemon-reload
systemctl enable eduxjy
systemctl restart eduxjy

if [[ -n "$NGINX_LINK" ]]; then
  install -m 644 "$APP_DIR/deploy/nginx-eduxjy.conf" "$NGINX_SITE"
  ln -sfn "$NGINX_SITE" "$NGINX_LINK"
else
  install -m 644 "$APP_DIR/deploy/nginx-eduxjy.conf" "$NGINX_SITE"
fi

# RHEL-family SELinux may block the reverse proxy and static reads.
if command -v getenforce >/dev/null 2>&1 && [[ "$(getenforce)" == "Enforcing" ]]; then
  setsebool -P httpd_can_network_connect 1 || true
  chcon -R -t httpd_sys_content_t "$APP_DIR/staticfiles" || true
fi

nginx -t
systemctl enable nginx
systemctl reload nginx

echo "Deployment complete."
echo "Hostname: $(hostname)"
echo "Public URL: http://${PUBLIC_IP}/"
echo "Check: systemctl status eduxjy nginx"
