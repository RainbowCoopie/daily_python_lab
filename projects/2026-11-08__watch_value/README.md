# 2026-11-08 · 取值监控与变更告警

> 把网页/接口/报表里的值抽成快照, 下次运行比对出新增、消失、改动, 再按规则决定要不要告警。

标签: `监控预警` `快照比对` `RPA 场景` `stdlib`

## 今天练什么

- 快照用排序后的 JSON 做 sha256, 值没变就不告警, 避免刷屏
- diff 区分 added / removed / changed 三类, 每条都带旧值与新值
- 规则支持按 key 过滤和数值阈值, 阈值内的抖动不打扰人

## 目录结构

```
watcher/watcher/      # 核心实现
watcher/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd watcher
python -m pytest -q
```

## 设计说明

监控类项目最常见的失败不是抓不到数据, 是**告警太多**。这里的做法是:
先把值规范化成 dict -> 用摘要判断"整体有没有变" (一层粗筛),
变了再做逐 key 的 diff (二层细筛), 最后用规则过滤 (三层),
三层都过了才发告警。抓取层不在本模块, 只约定输入是 dict[str, str],
这样换成 requests / DrissionPage / Excel 读出来都能接。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
