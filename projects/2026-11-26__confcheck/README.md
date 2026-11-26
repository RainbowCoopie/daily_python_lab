# 2026-11-26 · 声明式配置校验

> 用声明式规则校验配置字典: 必填、类型、范围、长度、正则、枚举、嵌套与列表, 一次报出全部问题。

标签: `配置校验` `错误聚合` `类型严格性` `字段路径`

## 今天练什么

- 一次聚合全部错误, 不做 fail-fast —— 配置错了要一次改完, 而不是改一个跑一次
- 类型判定严格: bool 不算 int, 但 int 可以当 float 用
- 机器路径用 JSON Pointer, 人读路径用点号, 两套都提供

## 目录结构

```
confcheck/confcheck/      # 核心实现
confcheck/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd confcheck
python -m pytest -q
```

## 设计说明

几个刻意的取舍:

**全聚合 vs fail-fast**。校验器默认返回所有问题。fail-fast 适合"输入可能恶意"的场景
(早停省算力), 但配置校验的主体是"我自己写错了", 一次看全才有效率。

**类型严格性**。`type=int` 时 `True` 不算数, 因为 `isinstance(True, int)` 为真;
`type=float` 时整数可以过, 因为 1 是合法的 1.0。这两个方向不对称, 但都符合直觉。

**路径双轨**。`Issue.path` 是给人读的点号路径(`server.port`), `pointer` 属性给出
RFC 6901 的机器路径(`/server/port`)。混用会很难受: 前者能直接贴进报错信息,
后者能直接用来定位 JSON 节点。

**未知键**。默认允许(很多配置允许扩展字段), 但 `allow_unknown=False` 时会把多余键报出来 ——
拼错键名是最常见的配置事故, 而它本身不会报错, 只会让配置静默失效。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
