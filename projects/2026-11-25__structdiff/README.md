# 2026-11-25 · JSON 结构比对

> 两份 JSON 的结构差异: 按 JSON Pointer 报出 add/remove/replace/type_change, 语义边界逐条固定。

标签: `JSON Pointer` `RFC 6902` `配置对比` `边界语义`

## 今天练什么

- 对象忽略键顺序, 数组按索引比较 —— 顺序变化就算变化, 这是刻意的
- 缺失与 null 不等价; True 与 1 不等价; 1 与 1.0 按数值比较视为相等
- 路径按 RFC 6901 转义: 键里的 ~ 记作 ~0, / 记作 ~1, 根节点是空字符串

## 目录结构

```
structdiff/structdiff/      # 核心实现
structdiff/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd structdiff
python -m pytest -q
```

## 设计说明

四条容易写错的语义, 都在测试里钉住了:

1. **缺失 ≠ null**。`{"a": null}` 与 `{}` 的差别是"有值且为空"和"根本没有", 前者是 replace,
   后者是 remove。很多实现把两者都当 None, 于是报"没变化"。
2. **True ≠ 1**。Python 里 `True == 1` 为真、`isinstance(True, int)` 也为真,
   所以比较时必须先判 bool。接口里 `"flag": true` 变成 `1` 是要报警的。
3. **1 == 1.0**。JSON 只有一种数字类型, RFC 6902 也按数值比较, 所以 `1` 与 `1.0` 视为相等。
   这和上一条方向相反, 但两者都符合各自的规范。
4. **数组按索引**。`[1,2]` 与 `[2,1]` 是两处 replace, 而不是"顺序变了"。要做"忽略顺序"的
   集合比较得由上层按业务键先归一化 —— 那是另一个问题, 混进来会让 diff 结果不可预测。

根节点的 Pointer 是空字符串, 不是 "/" —— "/" 表示"键名为空字符串的成员"。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
