import sys
from typing import Any


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr, flush=True)
