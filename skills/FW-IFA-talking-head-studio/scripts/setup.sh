#!/bin/bash
# 安装已改成跨平台的 setup.py（Windows 没有 bash；国内网络要走镜像）。这个文件只为兼容旧说明：等于 python3 scripts/setup.py "$@"
exec python3 "$(cd "$(dirname "$0")" && pwd)/setup.py" "$@"
