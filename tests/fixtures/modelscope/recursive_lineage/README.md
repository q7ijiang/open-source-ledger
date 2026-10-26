# 递归上游血缘测试数据

`model_catalog.json` 是离线响应夹具，不包含真实密钥，也不需要网络访问。

- `org/AppModel -> org/Layer3 -> org/Layer2 -> org/Layer1 -> org/BaseModel`：
  验证四层以上递归、`BaseModel` 与 `ParentsModels[].Name` 两种父模型来源。
- `org/AppModel.SonModels`：验证单模型调研可显示下游聚合，而项目模式可以关闭。
- `org/CycleA <-> org/CycleB`：验证循环检测不会无限请求。
- 测试通过 `max_upstream_nodes` 截断时，应保留 `budget_exhausted` 占位节点。

测试入口：`tests/test_modelscope_recursive_lineage.py`。
