"""Ortak fixture'lar. Yalnızca dış dünya sınırı (ağ, LLM HTTP, bekleme) sahtelenir."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from services.core.hustler.db import Database
from services.core.hustler.domain.models.template import (
    RenderConfig,
    SafeZone,
    TemplateSpec,
)
from services.core.hustler.infrastructure.llm_port import LLMPort, LLMResponse


@dataclass
class LLMHarness:
    port: LLMPort
    prompts: list[str]


LLMFactory = Callable[[list[str | Exception]], LLMHarness]


@pytest.fixture
async def llm_factory(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[LLMFactory]:
    """Gerçek LLMPort (bütçe defteri dahil); yalnızca HTTP çağrısı senaryolu sahte."""
    created: list[LLMPort] = []

    def make(script: list[str | Exception]) -> LLMHarness:
        port = LLMPort(api_key="fake", max_tokens=1_000_000)
        queue = list(script)
        prompts: list[str] = []

        async def fake(prompt: str) -> LLMResponse:
            prompts.append(prompt)
            item = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(item, Exception):
                raise item
            return LLMResponse(item, 1, 1, 2)

        monkeypatch.setattr(port, "_execute_network_request", fake)
        created.append(port)
        return LLMHarness(port, prompts)

    yield make
    for p in created:
        await p.close()


@pytest.fixture
def fast_retry(monkeypatch: pytest.MonkeyPatch) -> Callable[[object], None]:
    """tenacity bekleme sürelerini atlar; deneme sayısı davranışı aynı kalır."""

    async def no_sleep(_: float) -> None:
        return None

    def patch(fn: object) -> None:
        monkeypatch.setattr(getattr(fn, "retry"), "sleep", no_sleep)

    return patch


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(tmp_path / "test.db")
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def template() -> TemplateSpec:
    zone = SafeZone(margin_top=10, margin_bottom=10, margin_left=10, margin_right=10)
    return TemplateSpec(
        name="Test",
        target_duration_sec=30,
        max_scenes=3,
        allowed_tones=["ciddi"],
        render_config=RenderConfig(
            width=1080, height=1920, fps=30, bg_color="#000", safe_zone=zone
        ),
    )
