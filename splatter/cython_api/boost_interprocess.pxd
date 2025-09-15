cdef extern from "<boost/interprocess/managed_shared_memory.hpp>" namespace "boost::interprocess":
    cdef cppclass managed_shared_memory:
        managed_shared_memory(create_only_t, const char*, size_t) except +
        managed_shared_memory(open_only_t, const char*) except +
        void* allocate(size_t) except +
        void deallocate(void*) except +
        void destroy[T](const char*) except +

cdef extern from "<boost/interprocess/creation_tags.hpp>" namespace "boost::interprocess":
    cdef cppclass create_only_t:
        create_only_t()
    cdef create_only_t create_only

    cdef cppclass open_only_t:
        open_only_t()
    cdef open_only_t open_only
