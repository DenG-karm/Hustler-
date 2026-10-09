"""TimeCode/SceneSynchronizer: kare yuvarlama ve artık dağıtımı."""

import pytest

from services.core.hustler.infrastructure.timecode import SceneSynchronizer, TimeCode


@pytest.mark.parametrize(
    ("ms", "frames"),
    [
        (0, 0),
        (16, 0),
        (17, 1),
        (33, 1),
        (500, 15),
        (1000, 30),
        (60_000, 1800),
        (3_600_000, 108_000),
    ],
)
def test_ms_to_frames(ms: int, frames: int) -> None:
    assert TimeCode.ms_to_frames(ms) == frames


@pytest.mark.parametrize(
    ("frames", "ms"), [(0, 0), (1, 33), (15, 500), (30, 1000), (1800, 60_000)]
)
def test_frames_to_ms(frames: int, ms: int) -> None:
    assert TimeCode.frames_to_ms(frames) == ms


@pytest.mark.parametrize("frames", [0, 1, 7, 29, 30, 999, 10_000])
def test_frame_round_trip_is_stable(frames: int) -> None:
    assert TimeCode.ms_to_frames(TimeCode.frames_to_ms(frames)) == frames


def test_sync_distributes_remainder_frames_to_first_scenes() -> None:
    scenes = SceneSynchronizer.sync_scenes(1033, 3)

    assert scenes == [
        {"scene_index": 0, "frames": 11, "start_ms": 0, "duration_ms": 367},
        {"scene_index": 1, "frames": 10, "start_ms": 367, "duration_ms": 333},
        {"scene_index": 2, "frames": 10, "start_ms": 700, "duration_ms": 333},
    ]


@pytest.mark.parametrize("total_ms", [0, 1, 999, 1000, 45_123, 180_000])
@pytest.mark.parametrize("count", [1, 2, 3, 7, 10])
def test_scene_frames_always_sum_to_total_without_drift(
    total_ms: int, count: int
) -> None:
    scenes = SceneSynchronizer.sync_scenes(total_ms, count)

    assert len(scenes) == count
    assert sum(int(s["frames"]) for s in scenes) == TimeCode.ms_to_frames(total_ms)
    starts = [int(s["start_ms"]) for s in scenes]
    assert starts == sorted(starts)


@pytest.mark.parametrize("count", [0, -1, -100])
def test_non_positive_scene_count_returns_empty(count: int) -> None:
    assert SceneSynchronizer.sync_scenes(1000, count) == []
