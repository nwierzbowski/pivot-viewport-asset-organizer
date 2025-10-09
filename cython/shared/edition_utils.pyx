include "edition_flags.pxi" # type: ignore this exists in a generated file

# Expose edition flags as importable variables
cdef public bint splatter_edition_pro = SPLATTER_EDITION_PRO # type: ignore this exists in a generated file
cdef public bint splatter_edition_standard = SPLATTER_EDITION_STANDARD # type: ignore this exists in a generated file

def print_edition() -> None:
    """Print the edition this Cython module was compiled for (testing helper)."""
    if splatter_edition_pro:
        print("[Splatter][Cython] Compile-time branch: PRO edition")
    elif splatter_edition_standard:
        print("[Splatter][Cython] Compile-time branch: STANDARD edition")
    else:
        print("[Splatter][Cython] Compile-time branch: UNKNOWN edition")