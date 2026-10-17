import re
from typing import List


class GraphValidator:
    """
    M6 K-606: Topolojik Doğrulama (GraphValidator)
    FFmpeg AST (FilterGraph) içinde kopuk etiket (tüketilmeyen çıktı)
    veya çoklu tüketilen etiket hatalarını işlem motoruna (FFmpeg)
    gitmeden önce yakalar.
    """
    @staticmethod
    def _extract_line_labels(line: str, produced_labels: set[str], consumed_labels: list[str]) -> None:
        """Tek bir graf satırındaki girdi ve çıktı etiketlerini ayıklar."""
        match_in = re.match(r'^(\[[a-zA-Z0-9_:]+\])+', line)
        if match_in:
            consumed_labels.extend(re.findall(r'\[([a-zA-Z0-9_:]+)\]', match_in.group(0)))

        match_out = re.search(r'(\[[a-zA-Z0-9_:]+\])+$', line)
        if match_out:
            for out in re.findall(r'\[([a-zA-Z0-9_:]+)\]', match_out.group(0)):
                if out in produced_labels:
                    raise ValueError(f"Çıktı etiketi '{out}' graf içinde birden fazla kez üretilmiş!")
                produced_labels.add(out)

    @staticmethod
    def _collect_map_consumers(map_args: List[str]) -> list[str]:
        """-map argümanlarındaki tüketici etiketleri ayıklar."""
        consumers: list[str] = []
        for m in map_args:
            match = re.match(r'^\[([a-zA-Z0-9_:]+)\]$', m)
            consumers.append(match.group(1) if match else m)
        return consumers

    @staticmethod
    def _check_topology(produced_labels: set[str], consumption_count: dict[str, int]) -> None:
        """Üretilen etiketlerin tam olarak 1 kez tüketildiğini denetler."""
        for label in produced_labels:
            count = consumption_count.get(label, 0)
            if count == 0:
                raise ValueError(f"Kopuk etiket: '{label}' üretildi ancak hiçbir filtre veya -map tarafından tüketilmedi.")
            if count > 1:
                raise ValueError(f"Çoklu tüketim: '{label}' etiketi {count} kez tüketildi, FFmpeg bunu desteklemez (split/asplit kullanın).")

    @staticmethod
    def validate_graph(graph_lines: List[str], map_args: List[str]) -> None:
        produced_labels: set[str] = set()
        consumed_labels: list[str] = []

        for line in graph_lines:
            GraphValidator._extract_line_labels(line, produced_labels, consumed_labels)

        consumed_labels.extend(GraphValidator._collect_map_consumers(map_args))

        consumption_count: dict[str, int] = {}
        for label in consumed_labels:
            consumption_count[label] = consumption_count.get(label, 0) + 1

        GraphValidator._check_topology(produced_labels, consumption_count)
