# 稳定哈希、SimHash 指纹与 MinHash 签名。
from __future__ import annotations

import hashlib
from typing import Iterable

BITS = 64


def _hash64(token: str, salt: int = 0) -> int:
    """blake2b 加盐取 8 字节 —— 不用内置 hash(), 保证跨进程稳定。"""
    person = b"simdup" + salt.to_bytes(4, "big")
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8, person=person).digest()
    return int.from_bytes(digest, "big")


def simhash(tokens: Iterable[str], bits: int = BITS) -> int:
    """把一组 token 压成一个 bits 位整数指纹。"""
    vector = [0] * bits
    for token in tokens:
        value = _hash64(token)
        for index in range(bits):
            vector[index] += 1 if (value >> index) & 1 else -1
    out = 0
    for index, weight in enumerate(vector):
        if weight > 0:
            out |= 1 << index
    return out


def hamming(left: int, right: int) -> int:
    """两个指纹差多少位。"""
    return bin(left ^ right).count("1")


def simhash_similarity(left: int, right: int, bits: int = BITS) -> float:
    return 1.0 - hamming(left, right) / bits


def minhash_signature(tokens: Iterable[str], num_perm: int = 128, bits: int = BITS) -> tuple[int, ...]:
    """每个"置换"取一个最小哈希值, 组成签名。"""
    if num_perm < 1:
        raise ValueError("num_perm 必须 >= 1")
    items = list(tokens)
    signature: list[int] = []
    for salt in range(num_perm):
        best = None
        for token in items:
            value = _hash64(token, salt)
            if best is None or value < best:
                best = value
        signature.append(0 if best is None else best)
    return tuple(signature)


def minhash_similarity(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    """签名逐位相等的比例, 即 Jaccard 的估计值。"""
    if len(left) != len(right):
        raise ValueError("两个签名长度必须相同")
    if not left:
        return 1.0
    same = sum(1 for a, b in zip(left, right) if a == b)
    return same / len(left)
