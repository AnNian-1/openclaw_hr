#!/usr/bin/env bash
# 把 rarlab 的 unrar/rar 放进 conda openclaw-hr 的 bin（无需 sudo）。
# recruitment-run.sh 已把该 bin 前置到 PATH，rarfile 才能解 RAR。
set -euo pipefail
ENVBIN="${OPENCLAW_CONDA_BIN:-$HOME/miniconda3/envs/openclaw-hr/bin}"
URL="${RARLAB_TARBALL_URL:-https://www.rarlab.com/rar/rarlinux-x64-723.tar.gz}"

if [[ -x "$ENVBIN/unrar" && -x "$ENVBIN/rar" ]]; then
  echo "ok: $ENVBIN/unrar already present"
  exit 0
fi
if [[ ! -d "$ENVBIN" ]]; then
  echo "ensure-rar-tools: missing conda env bin $ENVBIN" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/rarlinux.tgz" "$URL"
tar -xzf "$tmp/rarlinux.tgz" -C "$tmp"
install -m 755 "$tmp/rar/unrar" "$ENVBIN/unrar"
install -m 755 "$tmp/rar/rar" "$ENVBIN/rar"
if [[ -f "$tmp/rar/default.sfx" ]]; then
  install -m 644 "$tmp/rar/default.sfx" "$ENVBIN/default.sfx"
fi
echo "installed: $ENVBIN/unrar"
"$ENVBIN/unrar" | head -n 2
