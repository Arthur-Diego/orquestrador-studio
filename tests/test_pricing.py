"""Catálogo de custo `[extensão]` (ADR-016): tabela medida e normalização de variação."""
from __future__ import annotations

from studio.common import pricing


def test_measured_costs_match_the_product_owner_table():
    assert pricing.estimate("nano_banana_2", {"resolution": "1k"})["credits"] == 2
    assert pricing.estimate("nano_banana_2", {"resolution": "2k"})["credits"] == 2
    assert pricing.estimate("nano_banana_2", {"resolution": "4k"})["credits"] == 4
    assert pricing.estimate("bytedance_image_upscale", {})["credits"] == 2
    assert pricing.estimate("gpt_image_2", {})["credits"] == 8.5
    assert pricing.estimate("kling3_0", {"duration": "5s"})["credits"] == 10
    assert pricing.estimate("kling3_0", {"duration": "10s"})["credits"] == 20
    assert pricing.estimate("seedance_2_0", {})["credits"] == 22.5
    assert pricing.estimate("veo3_1_lite", {"duration": "8s"})["credits"] == 8
    assert pricing.estimate("sonilo_music", {})["credits"] == 0.94


def test_variant_normalization_accepts_loose_inputs():
    assert pricing.estimate("kling3_0", {"duration": 5})["credits"] == 10
    assert pricing.estimate("kling3_0", {"duration": "10"})["credits"] == 20
    assert pricing.estimate("nano_banana_2", {"resolution": "4096"})["credits"] == 4
    # sem variação, cai no default do modelo
    assert pricing.estimate("nano_banana_2", None)["variant"] == "2k"
    assert pricing.estimate("kling3_0", {})["variant"] == "5s"


def test_unknown_model_is_marked_not_measured():
    e = pricing.estimate("does_not_exist", {})
    assert e["credits"] is None and e["source"] == "unknown"
    assert not pricing.known("does_not_exist")


def test_list_models_is_grouped_and_complete():
    models = pricing.list_models()
    ids = {m["id"] for m in models}
    assert {"nano_banana_2", "kling3_0", "sonilo_music", "bytedance_image_upscale"} <= ids
    # cada modelo traz linhas de custo por variação
    nb = next(m for m in models if m["id"] == "nano_banana_2")
    assert {r["variant"] for r in nb["rows"]} == {"1k", "2k", "4k"}
