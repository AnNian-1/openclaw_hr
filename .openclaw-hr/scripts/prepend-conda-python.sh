# 给 bash 壳脚本 source：把 conda 环境 python 放到 PATH 最前。
# 默认 openclaw-hr。转写请用 funasr_me（numpy<2 / torch），不要混进这个环境。
# 用法: OPENCLAW_CONDA_ENV=openclaw-hr source this file
_oc_env="${OPENCLAW_CONDA_ENV:-openclaw-hr}"
_oc_bin="${HOME}/miniconda3/envs/${_oc_env}/bin"
if [ -x "${_oc_bin}/python3" ]; then
  export PATH="${_oc_bin}:${PATH}"
fi
unset _oc_env _oc_bin
