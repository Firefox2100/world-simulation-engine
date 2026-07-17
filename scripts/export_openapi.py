import json
from pathlib import Path

from world_simulation_engine.app import app


def main():
    output = Path("frontend/openapi.json")

    schema = app.openapi()
    output.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
