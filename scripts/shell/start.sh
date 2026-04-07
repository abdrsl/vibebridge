#!/bin/bash
cd "$(dirname "$0")"
source /home/user/workspace/MyCompany/.secrets/feishu.env
python3 main.py
