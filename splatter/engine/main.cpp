#include <iostream>
int main(int argc, char** argv) {
    std::cout << "Splatter engine standalone stub. Args: ";
    for(int i=0;i<argc;++i) std::cout << argv[i] << ' ';
    std::cout << std::endl;
    // TODO: initialize engine core, start IPC loop
    return 0;
}