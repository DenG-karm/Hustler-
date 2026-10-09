from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Filter:
    """
    FFmpeg filtrelerini (örn: scale, crop) temsil eden soyut (AST) sınıfı.
    """
    name: str
    args: List[str]
    kwargs: Dict[str, str]

    def to_string(self) -> str:
        parts = []
        if self.args:
            parts.extend(self.args)
        if self.kwargs:
            for k, v in self.kwargs.items():
                parts.append(f"{k}={v}")
        if not parts:
            return self.name
        return f"{self.name}=" + ":".join(parts)

@dataclass
class FilterChain:
    """
    Sıralı FFmpeg filtre zincirini temsil eder. (örn: scale,crop,setsar)
    """
    filters: List[Filter]
    
    def to_string(self) -> str:
        return ",".join(f.to_string() for f in self.filters)
