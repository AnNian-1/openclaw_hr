# 给 bash 壳脚本 source：openclaw CLI 的 shebang 是 env node，PATH 里若先是 Node 20 会直接失败。
if [ -d "${HOME}/.local/node/node-22/bin" ]; then
  export PATH="${HOME}/.local/node/node-22/bin:${PATH}"
fi
