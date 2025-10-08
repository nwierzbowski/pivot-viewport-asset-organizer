include "edition_flags.pxi" # type: ignore this exists in a generated file

def print_edition() -> None:
    """Print the edition this Cython module was compiled for (testing helper)."""
    if SPLATTER_EDITION_PRO: # type: ignore this exists in a generated file
        print("[Splatter][Cython] Compile-time branch: PRO edition")
    elif SPLATTER_EDITION_STANDARD: # type: ignore this exists in a generated file
        print("[Splatter][Cython] Compile-time branch: STANDARD edition")
    else:
        print("[Splatter][Cython] Compile-time branch: UNKNOWN edition")