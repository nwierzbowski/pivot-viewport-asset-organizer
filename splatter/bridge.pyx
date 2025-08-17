from splatter.cython_api.chull cimport say_hello_from_cpp


def say_hello():
    """Calls the C++ function and prints a message from C++."""
    with nogil:
        say_hello_from_cpp()