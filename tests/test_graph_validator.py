"""GraphValidator: kopuk, çoklu tüketilen ve tekrar üretilen etiketler."""

import pytest

from services.core.hustler.generators.graph_validator import GraphValidator


def test_valid_chain_passes() -> None:
    lines = ["[0:v]scale=10:10[a]", "[a]fps=30[b]"]

    assert GraphValidator.validate_graph(lines, ["[b]"]) is None


def test_label_consumed_only_by_map_passes() -> None:
    GraphValidator.validate_graph(["[0:v]null[out]"], ["[out]"])


def test_dangling_label_raises() -> None:
    with pytest.raises(ValueError, match="Kopuk etiket: 'a'"):
        GraphValidator.validate_graph(["[0:v]null[a]"], ["0:a"])


def test_label_consumed_twice_raises_and_names_count() -> None:
    lines = ["[0:v]null[a]", "[a]null[b]", "[a]null[c]"]

    with pytest.raises(ValueError, match="'a' etiketi 2 kez"):
        GraphValidator.validate_graph(lines, ["[b]", "[c]"])


def test_label_consumed_by_filter_and_map_raises() -> None:
    with pytest.raises(ValueError, match="Çoklu tüketim"):
        GraphValidator.validate_graph(["[0:v]null[a]", "[a]null[b]"], ["[a]", "[b]"])


def test_duplicate_output_label_raises() -> None:
    with pytest.raises(ValueError, match="birden fazla kez üretilmiş"):
        GraphValidator.validate_graph(["[0:v]null[a]", "[1:v]null[a]"], ["[a]"])


@pytest.mark.parametrize(
    ("lines", "maps"),
    [([], []), ([], ["0:v"]), (["not a filter line"], [])],
)
def test_degenerate_inputs_do_not_crash(lines: list[str], maps: list[str]) -> None:
    GraphValidator.validate_graph(lines, maps)


def test_multi_input_filter_consumes_every_label() -> None:
    lines = ["[0:v]null[a]", "[1:v]null[b]", "[a][b]hstack[c]"]

    GraphValidator.validate_graph(lines, ["[c]"])
