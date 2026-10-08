# -*- coding: utf-8 -*-
"""pytest 公共配置：把仓库根目录加入 sys.path，便于导入各模块。"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
