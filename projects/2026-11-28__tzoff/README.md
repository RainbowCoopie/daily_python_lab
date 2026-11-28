# 2026-11-28 · 时区偏移与时间戳解析

> 解析 +08:00 / Z / GMT+8 / -00:00 各种偏移, 并把「偏移未知」这个语义与「偏移为零」分开保留。

标签: `RFC 3339` `时区偏移` `-00:00 语义` `datetime`

## 今天练什么

- `-00:00` 解析成「零偏移但未知」, 与 `Z`/`+00:00` 区分开 —— datetime 本身会丢这个信息
- 偏移范围按 ±18:00 校验, 分钟数必须小于 60
- 时间戳拆成「本地时间 + 偏移」两段存, 换算到 UTC 是显式动作而不是隐式发生

## 目录结构

```
tzoff/tzoff/      # 核心实现
tzoff/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd tzoff
python -m pytest -q
```

## 设计说明

为什么不能直接 `datetime.fromisoformat` 了事:

```python
datetime.fromisoformat("2026-11-28T09:30:00-00:00").utcoffset()   # timedelta(0)
datetime.fromisoformat("2026-11-28T09:30:00+00:00").utcoffset()   # timedelta(0)
```

两者一模一样 —— 语义差别在构造时就丢了。所以本模块自己扫尾部的偏移串, 单独保留
一个 `unknown` 标记, 再把时间部分交给 `fromisoformat`。

支持的偏移写法: `Z` / `+08:00` / `-05:30` / `+0800` / `GMT+8` / `UTC+05:30` / `UTC` / `GMT`。
**不支持**裸的 `+08`(只有小时没有分钟) —— 因为它和日期里的 `-28` 这类片段太容易混淆,
宁可让调用方把数据洗干净。这是刻意的取舍, 不是遗漏。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
