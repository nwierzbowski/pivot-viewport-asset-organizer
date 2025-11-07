include "edition_flags.pxi" # type: ignore this exists in a generated file

# Expose edition flags as importable variables
cdef public int pivot_pro = PIVOT_EDITION_PRO # type: ignore this exists in a generated file
cdef public int pivot_standard = PIVOT_EDITION_STANDARD # type: ignore this exists in a generated file

def is_pro_edition() -> bool:
    return bool(PIVOT_EDITION_PRO)

def is_standard_edition() -> bool:
    return bool(PIVOT_EDITION_STANDARD)

def print_edition() -> None:
    """Print the edition this Cython module was compiled for (testing helper)."""
    if pivot_pro:
        print("[Pivot][Cython] Compile-time branch: PRO edition")
    elif pivot_standard:
        print("[Pivot][Cython] Compile-time branch: STANDARD edition")
    else:
        print("[Pivot][Cython] Compile-time branch: UNKNOWN edition")