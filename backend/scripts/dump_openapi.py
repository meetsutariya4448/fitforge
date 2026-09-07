"""Write the FastAPI OpenAPI document to a file.

Used by CI to give the frontend contract check the backend's own account of its
response shapes, rather than a second hand-maintained copy of them.

Usage:  python scripts/dump_openapi.py openapi.json
"""

import json
import sys
from pathlib import Path

# Importing the app is enough — app.openapi() builds the document from the
# Pydantic models and never touches the database.
from app.main import app


def main() -> None:
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    destination.write_text(json.dumps(app.openapi(), indent=2))
    schema_count = len(app.openapi().get("components", {}).get("schemas", {}))
    print(f"Wrote {destination} ({schema_count} component schemas)")


if __name__ == "__main__":
    main()
