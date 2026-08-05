#pragma once

#if defined(__INTELLISENSE__)
#include <stdint.h>
#include <stddef.h>

using byte = uint8_t;

class IntelliSenseSerialStub {
public:
  template <typename T>
  void begin(T) {}
  int available() { return 0; }
  int read() { return 0; }
  size_t write(const byte *, size_t) { return 0; }
  size_t write(const char *, size_t) { return 0; }
  void flush() {}
  void print(const char *) {}
  void print(char) {}
  void print(int) {}
  void print(unsigned int) {}
  void print(long) {}
  void print(unsigned long) {}
  void print(float, int = 2) {}
  void println(const char *) {}
  void println() {}
};

extern IntelliSenseSerialStub Serial;
extern IntelliSenseSerialStub Serial1;

inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
inline void delay(unsigned long) {}
inline unsigned long millis() { return 0; }

#ifndef HIGH
#define HIGH 1
#endif
#ifndef LOW
#define LOW 0
#endif
#ifndef OUTPUT
#define OUTPUT 1
#endif
#endif
