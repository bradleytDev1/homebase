/* Arduino.h -- minimal shim used ONLY to compile-check tumbler_uno.ino with a
 * bare avr-gcc toolchain (no Arduino IDE present). It declares just enough of
 * the Arduino core for the compiler to typecheck the sketch against the real
 * <avr/io.h> register definitions for the ATmega328P. It is not a runtime
 * implementation and is not used on the device. See Makefile. */
#ifndef ARDUINO_H_SHIM
#define ARDUINO_H_SHIM
#include <stdint.h>
#include <stdbool.h>
#include <avr/io.h>
#include <avr/interrupt.h>

#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
#define FALLING 2
#define RISING 3
#define F(x) (x)

void pinMode(uint8_t, uint8_t);
void digitalWrite(uint8_t, uint8_t);
int  digitalRead(uint8_t);
uint32_t millis(void);
void delay(uint32_t);
void delayMicroseconds(uint32_t);
void attachInterrupt(uint8_t, void (*)(void), int);
uint8_t digitalPinToInterrupt(uint8_t);

/* Serial: only the overloads the sketch actually uses. */
class SerialShim {
public:
  void begin(long);
  void print(const char*);
  void print(char);
  void print(uint8_t);
  void print(uint16_t);
  void print(uint32_t);
  void print(int);
  void print(float);
  void println(const char*);
  void println(char);
  void println(uint32_t);
  void println(float);
  void println(void);
};
extern SerialShim Serial;

/* The sketch defines these; main() in shim.cpp calls them. */
void setup(void);
void loop(void);
#endif
