# 2026-11-09 · 显示宽度与表格对齐

> 按显示列宽而不是字符数计算: 中文/全角算 2、组合符算 0, 再做安全截断、填充和多列对齐渲染。

标签: `终端渲染` `East Asian Width` `CJK 对齐` `stdlib`

## 今天练什么

- East Asian Width 的 W/F 记 2 列, Mn/Me/Cf 类别记 0 列, 其余 1 列
- 截断不会把一个汉字劈成半个: 预算按列算, 塞不下就提前停, 再补省略号
- 渲染出来的每一行显示宽度严格相等, 用属性测试逐行校验

## 目录结构

```
widegrid/widegrid/      # 核心实现
widegrid/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd widegrid
python -m pytest -q
```

## 设计说明

核心约定只有一条: **一切以显示列宽为准, 不用 len()**。
`len("中文") == 2` 但显示占 4 列; `len("e\u0301") == 2` 但显示占 1 列。
这两个方向相反的坑, 只要暴露在同一个 `text_width()` 里, 上层就不用再各自算一遍。

Ambiguous(不明确宽度)字符默认按 1 列处理 —— 这是大多数终端和等宽字体的行为,
若要贴到 CJK 环境的终端里, 可以自行把 AMBIGUOUS_WIDTH 调成 2。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
