# 2026-11-15 · 近似重复检测（SimHash / MinHash）

> 字符 shingle + Jaccard + SimHash 指纹 + MinHash 签名, 判断「改了几个字」的两段文本是不是同一份。

标签: `SimHash` `MinHash` `去重` `RAG 预处理`

## 今天练什么

- 所有哈希走 blake2b 加盐, 不用内置 hash(), 跨进程结果稳定
- MinHash 用 signature 逐位相等比例估 Jaccard, 签名长度可换精度
- 聚类用并查集, 一次扫描把近似重复的文本归到同一组

## 目录结构

```
simdup/simdup/      # 核心实现
simdup/tests/          # 测试（pytest，零第三方依赖也能跑）
```

## 快速开始

```bash
cd simdup
python -m pytest -q
```

## 设计说明

三层设计, 越往下越慢、越准:

1. `jaccard(a, b)`: 精确值, 用来看"到底像到什么程度"。测试里当基准。
2. `minhash_similarity(sig1, sig2)`: 用 128 个最小哈希近似 Jaccard, 误差约 ±0.05。
   适合大规模两两比较, 只需比整数。
3. `simhash` + `hamming`: 把整段文本压成 64 位整数, 海明距离 <= 3 通常视为近似重复。
   最便宜, 适合先粗筛。

中文不需要分词: 按字符切 3-gram 对"改几个字"这类改动很敏感, 而分词反而会把
"用户名"和"用名户"这类乱序当成相同。

---
由 `daily_python_lab` 流水线生成，提交前通过 compileall + pytest 双闸门。
