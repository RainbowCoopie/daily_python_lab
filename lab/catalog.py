"""主题注册表。加新主题: 在 topics/ 下建模块并在此登记。"""
from __future__ import annotations

from .topics import (
    algo_base_convert,
    comfy_graph,
    crawler_kit,
    fastapi_kv,
    llm_client_min,
    pandas_etl,
    queue_pool,
    rpa_taskflow,
    sd_prompt,
    watch_value,
    yolo_labels,
)

ALL_MODULES = [
    algo_base_convert,
    fastapi_kv,
    pandas_etl,
    crawler_kit,
    rpa_taskflow,
    llm_client_min,
    comfy_graph,
    yolo_labels,
    sd_prompt,
    queue_pool,
    watch_value,
]


def load_specs() -> list:
    return list(ALL_MODULES)


def by_slug(slug: str):
    for spec in ALL_MODULES:
        if spec.SLUG == slug:
            return spec
    raise KeyError(f"未知主题: {slug}")
