# 给 bash 壳脚本 source：openclaw CLI 的 shebang 是 env node，PATH 里若先是 Node 20 会直接失败。
# 按本机常见落点探测，不要写死 Annian nvm / 云主机 /opt。
for _n22 in \
  "${HOME}/.local/node/node-22/bin" \
  "/opt/openclaw-hr/.local/node/node-22/bin" \
  "/opt/node/node-22/bin"
do
  if [ -x "${_n22}/node" ]; then
    export PATH="${_n22}:${PATH}"
    break
  fi
done
unset _n22
