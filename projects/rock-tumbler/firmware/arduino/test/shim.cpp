/* Stub definitions so the compile-check links. No behaviour. */
#include "Arduino.h"
void pinMode(uint8_t, uint8_t) {}
void digitalWrite(uint8_t, uint8_t) {}
int  digitalRead(uint8_t) { return 0; }
uint32_t millis(void) { return 0; }
void delay(uint32_t) {}
void delayMicroseconds(uint32_t) {}
void attachInterrupt(uint8_t, void (*)(void), int) {}
uint8_t digitalPinToInterrupt(uint8_t p) { return p; }
void SerialShim::begin(long) {}
void SerialShim::print(const char*) {}
void SerialShim::print(char) {}
void SerialShim::print(uint8_t) {}
void SerialShim::print(uint16_t) {}
void SerialShim::print(uint32_t) {}
void SerialShim::print(int) {}
void SerialShim::print(float) {}
void SerialShim::println(const char*) {}
void SerialShim::println(char) {}
void SerialShim::println(uint32_t) {}
void SerialShim::println(float) {}
void SerialShim::println(void) {}
SerialShim Serial;
int main(void) { setup(); for(;;) loop(); }
