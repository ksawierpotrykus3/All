"""Ultraszybkie operacje JSON oparte o orjson (Rust) z fallbackiem do stdlib json."""
from typing import Any

try:
    import orjson

    def json_loads(data: str | bytes | bytearray | memoryview) -> Any:
        """Parsuje dane JSON z bajtów lub ciągu znaków z maksymalną prędkością."""
        if isinstance(data, str):
            return orjson.loads(data.encode("utf-8"))
        return orjson.loads(data)

    def json_dumps(obj: Any) -> str:
        """Serializuje obiekt Python do stringa JSON."""
        return orjson.dumps(obj).decode("utf-8")

    def json_dumps_bytes(obj: Any) -> bytes:
        """Serializuje obiekt Python bezpośrednio do bajtów JSON."""
        return orjson.dumps(obj)

except ImportError:
    import json

    def json_loads(data: str | bytes | bytearray | memoryview) -> Any:
        return json.loads(data)

    def json_dumps(obj: Any) -> str:
        return json.dumps(obj)

    def json_dumps_bytes(obj: Any) -> bytes:
        return json.dumps(obj).encode("utf-8")
