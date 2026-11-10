#!/bin/bash
# 自检已并进 setup.py（--check 只检查、不改任何东西）。这个文件只为兼容旧说明：等于 python3 scripts/setup.py --check "$@"
exec python3 "$(cd "$(dirname "$0")" && pwd)/setup.py" --check "$@"
