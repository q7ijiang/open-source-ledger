# -*- coding: utf-8 -*-
"""垃圾字符串测试：URL 与无效模型 ID 都不应被识别为有效模型。"""

FAKE_MODEL = "OpenBMB/not-a-real-model-42"
README_URL = "https://www.modelscope.cn/models/Qwen/Qwen-Image-2.1"
ANOTHER_FAKE = "aihub/definitely-not-exist-9999"

print(FAKE_MODEL, README_URL, ANOTHER_FAKE)
