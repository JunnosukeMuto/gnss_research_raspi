#!/bin/bash

# コマンドが失敗した場合にスクリプトを終了する
# 未定義変数を使用した場合にエラーにする
# パイプライン内の途中で失敗したら全体を失敗とみなす
set -euo pipefail

APP_NAME=gnss-research
APP_USER=gnssresearch
APP_GROUP=gnssresearch

APPDIR=/opt/${APP_NAME}
ENVDIR=/etc/${APP_NAME}
VENVDIR=${APPDIR}/venv
SYSTEMD_DIR=/etc/systemd/system

# root権限で実行されているか確認
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root." >&2
  exit 1
fi

# uvがインストールされているか確認
if ! command -v uv >/dev/null 2>&1; then
  echo "uv command not found. Please install 'uv' before running this script." >&2
  exit 1
fi

##########################################################################

echo "[1/7] Creating application user and group..."

# ユーザ、グループを作成
if ! id -u ${APP_USER} >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin ${APP_USER}
fi

usermod -aG dialout,i2c,bluetooth ${APP_USER}

##########################################################################

echo "[2/7] Installing application files..."

# アプリケーションディレクトリを作成
install -d -o ${APP_USER} -g ${APP_GROUP} -m 755 ${APPDIR}
install -o ${APP_USER} -g ${APP_GROUP} -m 755 \
  main_ble.py \
  main_ublox.py \
  ${APPDIR}/
install -o ${APP_USER} -g ${APP_GROUP} -m 644 \
  i2c_thread.py \
  uart_thread.py \
  nmea_thread.py \
  ntrip_thread.py \
  pyproject.toml \
  uv.lock \
  ${APPDIR}/

##########################################################################

echo "[3/7] Installing environment files..."

# 環境設定ディレクトリを作成
install -d -o root -g root -m 755 ${ENVDIR}
install -o root -g root -m 644 .env.example ${ENVDIR}/gnss-research.env

##########################################################################

echo "[4/7] Setting up Python virtual environment..."

# Python仮想環境を作成
if [ ! -d "${VENVDIR}" ]; then
  sudo -u ${APP_USER} uv venv ${VENVDIR}
fi

sudo -u ${APP_USER} ${VENVDIR}/bin/uv sync --project ${APPDIR}

##########################################################################

echo "[5/7] Installing systemd service files..."

install -o root -g root -m 644 \
  gnss-research.target \
  gnss-research-ble.service \
  gnss-research-ublox.service \
  ${SYSTEMD_DIR}/

##########################################################################

echo "[6/7] Enabling systemd services..."

systemctl daemon-reload
systemctl enable gnss-research.target

##########################################################################

echo "[7/7] Setup completed successfully."

echo "You must configure following environment file before starting the services:"
echo "  ${ENVDIR}/gnss-research.env"
echo "You can start the GNSS Research services using the following commands:"
echo "  sudo systemctl start gnss-research.target"
echo "To check the logs, use:"
echo "  sudo journalctl -u gnss-research-ble.service -f"
echo "  sudo journalctl -u gnss-research-ublox.service -f"