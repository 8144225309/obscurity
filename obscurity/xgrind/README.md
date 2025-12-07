# xgrind
CUDA accelerated arbitrary data embed method via key grinding on the secp256k1 curve

## Build instructions
```
$ nvcc -O3 -std=c++14 -I./GPU \
  gpu_grind.cu -c -o gpu_grind.o
```

```
$ g++ -O3 -std=c++14 \
  xgrind_gpu.c \
  gtable_cpu.cpp \
  CPU/Int.cpp CPU/IntMod.cpp CPU/Point.cpp CPU/SECP256K1.cpp \
  gpu_grind.o \
  -I./GPU -I./CPU -I/usr/local/cuda/include \
  -L/usr/local/cuda/lib64 \
  -lcudart -lcurand \
  -o xgrind_gpu
```

Prefix length is currently hardcoded to 32 bits.

## Usage
```
Usage:
  ./xgrind_gpu encode <file>
  ./xgrind_gpu decode <base_file>
```

An example grind output has been uploaded here: https://github.com/djkazic/xgrind/releases/tag/delcin-small

You can reconstruct the image by unzipping the file and then running `./xgrind_gpu decode delcin-small.jpg`.
