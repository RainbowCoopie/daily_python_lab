# 2026-11-08 · 任意进制双向转换器

> 十进制 <-> 2~36 进制的双向转换, 用 divmod 迭代实现, 零第三方依赖, 负数和边界值全部纳入测试。

标签: `CPython` `算法` `stdlib` `边界值`

## 今天练什么

- divmod 迭代替代 sympy.log 求位数——原实现的精度 bug 从根上消失
- 双向转换 (to_base / parse_base) 互为往返验证, 7 个进制 × 11 个样本 = 77 组参数化用例
- 自定义异常层次: InvalidBase / InvalidDigit, 让调用方能区分参数错和数据错

## 目录结构

```
baseconv/baseconv/      # 核心实现
baseconv/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd baseconv
python -m pytest -q
```

## 设计说明

原版用 `int(sympy.log(num, base))` 预分配结果长度, 一旦浮点误差让 log 少 1, 最高位就丢了。
这里换成 `while rest: rest, r = divmod(rest, base)`, 位数由数据自己决定, 不需要预先算长度,
也不需要 decimal / sympy 这类重依赖。反向解析用 Horner 法, 逐位累乘。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
