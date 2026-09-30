import sys
from pathlib import Path

# Add core to sys.path so we can import hustler
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir / "services" / "core"))

from hustler.contracts.models import VideoRecord  # noqa: E402

def main():
    contracts_dir = root_dir / "packages" / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    
    schema = VideoRecord.model_json_schema()
    
    ts_content = f"""// AUTO-GENERATED: DO NOT EDIT

export interface {schema['title']} {{
    id: string;
    title: string;
    duration: number;
}}
"""
    with open(contracts_dir / "index.ts", "w", encoding="utf-8") as f:
        f.write(ts_content)
    
    print("Contracts generated successfully at packages/contracts/index.ts")

if __name__ == "__main__":
    main()
