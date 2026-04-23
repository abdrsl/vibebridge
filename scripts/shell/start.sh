#!/bin/bash
cd "$(dirname "$0")"
source /home/user/workspace/VibeBridge/.secrets/feishu.env
python3 main.py
