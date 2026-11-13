"""主题注册表。加新主题: 在 topics/ 下建模块并在此登记。"""
from __future__ import annotations

from .topics import (
    algo_base_convert,
    cnnum,
    comfy_graph,
    crawler_kit,
    fastapi_kv,
    isoweek,
    llm_client_min,
    mojibake,
    pandas_etl,
    queue_pool,
    rpa_taskflow,
    sd_prompt,
    sheetref,
    watch_value,
    widegrid,
    yolo_labels,
    xlsafe,
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
    sheetref,
    widegrid,
    xlsafe,
    mojibake,
    isoweek,
    cnnum,
]


def load_specs() -> list:
    return list(ALL_MODULES)


def by_slug(slug: str):
    for spec in ALL_MODULES:
        if spec.SLUG == slug:
            return spec
    raise KeyError(f"未知主题: {slug}")
