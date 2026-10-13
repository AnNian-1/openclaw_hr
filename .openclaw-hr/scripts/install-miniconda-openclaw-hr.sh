#!/usr/bin/env bash
# 把 Miniconda 装到 ~/miniconda3，并创建 conda 环境 openclaw-hr（不含 funasr_me）。
set -euo pipefail
PREFIX="/usr/local/miniconda3"
PROFILE="/opt/openclaw-hr/.openclaw-hr"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) FN="Miniconda3-latest-Linux-x86_64.sh" ;;
  aarch64) FN="Miniconda3-latest-Linux-aarch64.sh" ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

download_installer() {
  local dest="$1"
  local urls=(
    "https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/${FN}"
    "https://repo.anaconda.com/miniconda/${FN}"
  )
  local u
  for u in "${urls[@]}"; do
    echo "download: $u"
    if curl -fL --retry 3 --connect-timeout 20 -o "$dest" "$u"; then
      return 0
    fi
    echo "failed: $u" >&2
  done
  return 1
}

if [ ! -x "${PREFIX}/bin/conda" ]; then
  tmp="$(mktemp -d)"
  download_installer "${tmp}/${FN}"
  bash "${tmp}/${FN}" -b -p "$PREFIX"
  rm -rf "$tmp"
else
  echo "miniconda already at $PREFIX"
fi

# 不交互：接受 Anaconda ToS（新版 conda 会拦）
export CONDA_PLUGINS_AUTO_ACCEPT_TOS=true
CONDA="${PREFIX}/bin/conda"
"$CONDA" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main 2>/dev/null || true
"$CONDA" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r 2>/dev/null || true

"$CONDA" env update -f "${PROFILE}/conda/environment-openclaw-hr.yml"
ENVPY="${PREFIX}/envs/openclaw-hr/bin/python3"
"$ENVPY" -m pip install -r "${PROFILE}/hcm/backend/requirements.txt"
bash "${PROFILE}/scripts/ensure-rar-tools.sh"

if ! grep -q 'miniconda3/bin/conda' /opt/openclaw-hr/.bashrc 2>/dev/null; then
  "$CONDA" init bash
fi

echo "---- verify ----"
"$ENVPY" -c "import pandas, matplotlib, fastapi, sqlalchemy, uvicorn; print('openclaw-hr ok', __import__('sys').executable)"
echo "done: $ENVPY"
