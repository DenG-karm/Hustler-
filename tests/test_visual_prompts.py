"""VisualPromptCompiler: LLM çıktısına kod seviyesinde parametre enjeksiyonu."""

import json

import pytest
from pydantic import ValidationError

from services.core.hustler.generators.visual_prompts import VisualPromptCompiler

from tests.conftest import LLMFactory

SUFFIX = " --ar 9:16 --style raw --no text, typography, letters, watermarks, signature, fonts"


async def test_final_prompt_is_exact_concatenation(llm_factory: LLMFactory) -> None:
    body = {
        "prompts": [
            {"scene_index": 0, "raw_prompt": "  a cat on a roof  "},
            {"scene_index": 1, "raw_prompt": "dark alley"},
        ]
    }
    h = llm_factory([json.dumps(body)])

    out = await VisualPromptCompiler(h.port).compile_prompts(["kedi", "sokak"])

    assert out == [
        {
            "scene_index": 0,
            "raw_prompt": "  a cat on a roof  ",
            "final_prompt": "a cat on a roof" + SUFFIX,
        },
        {
            "scene_index": 1,
            "raw_prompt": "dark alley",
            "final_prompt": "dark alley" + SUFFIX,
        },
    ]


async def test_llm_prompt_lists_scenes_and_forbids_params(
    llm_factory: LLMFactory,
) -> None:
    h = llm_factory(['{"prompts": []}'])

    out = await VisualPromptCompiler(h.port).compile_prompts(["a", "b"])

    assert out == []
    assert "Scene 0: a\nScene 1: b" in h.prompts[0]
    assert "Do NOT add aspect ratio" in h.prompts[0]


async def test_markdown_fenced_response_is_parsed(llm_factory: LLMFactory) -> None:
    h = llm_factory(['```json\n{"prompts":[{"scene_index":0,"raw_prompt":"x"}]}\n```'])

    out = await VisualPromptCompiler(h.port).compile_prompts(["s"])

    assert out[0]["final_prompt"] == "x" + SUFFIX


@pytest.mark.parametrize(
    ("raw", "exc"),
    [
        ("{bozuk", json.JSONDecodeError),
        ("", json.JSONDecodeError),
        ('{"prompts": [{"scene_index": "a", "raw_prompt": "x"}]}', ValidationError),
        ('{"prompts": [{"raw_prompt": "x"}]}', ValidationError),
        ("{}", ValidationError),
    ],
)
async def test_bad_llm_output_raises(
    llm_factory: LLMFactory, raw: str, exc: type[Exception]
) -> None:
    h = llm_factory([raw])

    with pytest.raises(exc):
        await VisualPromptCompiler(h.port).compile_prompts(["s"])


async def test_10k_char_scene_is_forwarded(llm_factory: LLMFactory) -> None:
    h = llm_factory(['{"prompts": []}'])
    scene = "k" * 10_000

    await VisualPromptCompiler(h.port).compile_prompts([scene])

    assert f"Scene 0: {scene}" in h.prompts[0]
