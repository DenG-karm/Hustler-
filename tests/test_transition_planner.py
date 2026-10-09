"""TransitionPlanner: xfade ofsetleri ve graf metni harf harf."""

import pytest

from services.core.hustler.domain.models.profile import RenderProfile
from services.core.hustler.generators.graph_validator import GraphValidator
from services.core.hustler.generators.transition_planner import TransitionPlanner


def test_offsets_overlap_each_transition() -> None:
    assert TransitionPlanner.calculate_offsets([5.0, 5.0, 5.0], 1.0) == [4.0, 8.0]


@pytest.mark.parametrize("durations", [[], [3.0]])
def test_fewer_than_two_clips_have_no_offsets(durations: list[float]) -> None:
    assert TransitionPlanner.calculate_offsets(durations, 1.0) == []


def test_final_graph_chains_xfades_exactly() -> None:
    lines, out = TransitionPlanner.build_graph(["a", "b", "c"], [5.0, 5.0, 5.0], 1.0)

    assert lines == [
        "[a][b]xfade=transition=fade:duration=1.0:offset=4.000[xfade0]",
        "[xfade0][c]xfade=transition=fade:duration=1.0:offset=8.000[xfade1]",
    ]
    assert out == "xfade1"
    GraphValidator.validate_graph(lines, [f"[{out}]"])


def test_draft_profile_uses_single_concat() -> None:
    lines, out = TransitionPlanner.build_graph(
        ["a", "b", "c"], [5.0, 5.0, 5.0], 1.0, RenderProfile.DRAFT
    )

    assert lines == ["[a][b][c]concat=n=3:v=1:a=0[concat_v]"]
    assert out == "concat_v"


def test_single_clip_passes_through_without_filters() -> None:
    assert TransitionPlanner.build_graph(["only"], [4.0], 1.0) == ([], "only")


@pytest.mark.parametrize(
    ("labels", "durations"),
    [([], []), (["a"], []), (["a", "b"], [1.0]), ([], [1.0])],
)
def test_mismatched_labels_and_durations_raise(
    labels: list[str], durations: list[float]
) -> None:
    with pytest.raises(ValueError, match="eşleşmelidir"):
        TransitionPlanner.build_graph(labels, durations, 1.0)


@pytest.mark.parametrize("transition", [0.0, 0.5, 2.5])
def test_offset_is_always_before_clip_end(transition: float) -> None:
    durations = [6.0, 6.0, 6.0, 6.0]
    offsets = TransitionPlanner.calculate_offsets(durations, transition)

    assert len(offsets) == len(durations) - 1
    assert offsets == sorted(offsets)
    assert all(o >= 0 for o in offsets)
