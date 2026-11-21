# 2026-11-21 · 下载文件名与分段请求解析

> 解析 Content-Disposition 取下载文件名(filename* 优先, 中文不乱码), 以及 Range 分段请求。

标签: `HTTP 头` `RFC 6266` `中文文件名` `Range`

## 今天练什么

- filename* 按 RFC 5987 解: 只认 utf-8 与 iso-8859-1, 坏值或别的字符集一律忽略并退回 filename
- 参数切分自己做, 处理引号内的分号与转义引号 —— 用 split(';') 会把文件名切碎
- Range 区分三种形态: 闭区间、开区间、后缀区间, 并提供按文件大小落地成具体字节区间

## 目录结构

```
httpname/httpname/      # 核心实现
httpname/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd httpname
python -m pytest -q
```

## 设计说明

两个头, 各自的坑:

**Content-Disposition** 的关键在于"两个文件名并存时听谁的"。按 RFC 6266 第 4.3 节,
`filename*` 优先; 但 `filename*` 可能解析失败(缺字符集、字符集不支持、百分号编码坏掉),
这时必须干净地退回 `filename`, 而不是抛错或者返回空 —— 下载流程不能因为一个头写错就断。

**Range** 有三种写法, 语义完全不同:
- `bytes=0-499` 前 500 字节
- `bytes=500-` 从 500 到结尾
- `bytes=-500` 最后 500 字节(注意这里数字是"长度", 不是位置)

第三种最容易写错: 它算的是**倒数的长度**, 要靠文件总大小才能落成具体区间,
所以提供 `resolve(size)` 而不是直接返回一对数字。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
