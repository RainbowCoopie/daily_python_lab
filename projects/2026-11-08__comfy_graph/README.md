# 2026-11-08 · ComfyUI 工作流图校验器

> 把 ComfyUI 那种节点连线结构建模成有向图, 提交前先查出断链和环, 不用等跑起来才发现报错。

标签: `ComfyUI` `DAG` `拓扑排序` `环检测`

## 今天练什么

- Kahn 算法做拓扑排序, 有环直接抛 CycleError 并说明原因
- missing_deps 在推送工作流前就能定位断掉的上游节点
- to_prompt 输出与 /prompt 接口一致的结构, 可直接拿去请求

## 目录结构

```
comfygraph/comfygraph/      # 核心实现
comfygraph/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd comfygraph
python -m pytest -q
```

## 设计说明

ComfyUI 的工作流 JSON 里, 一个节点的输入值要么是字面量, 要么是 `[上游节点 id, 输出槽位]`。
这种"字面量和引用混在同一个 dict"的结构最容易出问题。这里用显式 Graph 类承接:
link() 校验两端存在, topo_sort() 保证执行顺序, to_prompt() 负责吐出接口要的格式。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
