# -*- coding: utf-8 -*-
"""pytest 公共配置：把仓库根目录加入 sys.path，便于导入各模块。"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# ModelScope 验证数据：场景夹具（模块 8/9/10 边界）与真实许可证快照（模块 4 识别率）。
# 详见 tests/fixtures/modelscope/README.md。
MODELSCOPE_FIXTURES = FIXTURES / "modelscope"
