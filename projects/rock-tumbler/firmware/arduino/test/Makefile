# Compile-check the sketch against real ATmega328P headers.
#   make        -- build and report flash/RAM usage
#   make clean
MCU    = atmega328p
F_CPU  = 16000000UL
CXX    = avr-g++
FLAGS  = -mmcu=$(MCU) -DF_CPU=$(F_CPU) -Os -Wall -Wextra -std=gnu++11 -I.

all: check-toolchain tumbler.elf
	@echo "--- size ---"
	@avr-size tumbler.elf

# Fail with instructions rather than "avr-g++: No such file or directory".
check-toolchain:
	@command -v $(CXX) >/dev/null || { \
	  echo "$(CXX) not found."; \
	  echo "  macOS: brew tap osx-cross/avr && brew install avr-gcc"; \
	  echo "  Debian/Ubuntu: apt-get install gcc-avr avr-libc"; \
	  exit 1; }

tumbler.elf: sketch.cpp shim.cpp
	$(CXX) $(FLAGS) -o $@ sketch.cpp shim.cpp

# The .ino is valid C++ apart from the implicit Arduino.h and prototypes.
sketch.cpp: ../tumbler_uno/tumbler_uno.ino
	@printf '#include "Arduino.h"\nvoid setup(void);\nvoid loop(void);\n' > $@
	@cat $< >> $@

.PHONY: all check-toolchain clean

clean:
	rm -f tumbler.elf sketch.cpp
