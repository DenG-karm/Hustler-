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
    def validate_graph(graph_lines: List[str], map_args: List[str]) -> None:
        produced_labels = set()
        consumed_labels = []
        
        for line in graph_lines:
            # Girdileri bul (Satırın en başındaki [etiket] blokları)
            match_in = re.match(r'^(\[[a-zA-Z0-9_:]+\])+', line)
            if match_in:
                inputs_str = match_in.group(0)
                inputs = re.findall(r'\[([a-zA-Z0-9_:]+)\]', inputs_str)
                consumed_labels.extend(inputs)
                
            # Çıktıları bul (Satırın en sonundaki [etiket] blokları)
            match_out = re.search(r'(\[[a-zA-Z0-9_:]+\])+$', line)
            if match_out:
                outputs_str = match_out.group(0)
                outputs = re.findall(r'\[([a-zA-Z0-9_:]+)\]', outputs_str)
                for out in outputs:
                    if out in produced_labels:
                        raise ValueError(f"Çıktı etiketi '{out}' graf içinde birden fazla kez üretilmiş!")
                    produced_labels.add(out)
                    
        # Map argümanlarını tüketici olarak ekle
        for m in map_args:
            match = re.match(r'^\[([a-zA-Z0-9_:]+)\]$', m)
            if match:
                consumed_labels.append(match.group(1))
            else:
                consumed_labels.append(m)
                
        # Tüketim frekanslarını say
        consumption_count: dict[str, int] = {}
        for label in consumed_labels:
            consumption_count[label] = consumption_count.get(label, 0) + 1
            
        # Topolojik kuralları doğrula
        for label in produced_labels:
            count = consumption_count.get(label, 0)
            if count == 0:
                raise ValueError(f"Kopuk etiket: '{label}' üretildi ancak hiçbir filtre veya -map tarafından tüketilmedi.")
            if count > 1:
                raise ValueError(f"Çoklu tüketim: '{label}' etiketi {count} kez tüketildi, FFmpeg bunu desteklemez (split/asplit kullanın).")
