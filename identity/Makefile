CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra -Werror -fPIC
.PHONY: all clean
all: libpulse_pace_identity.so
libpulse_pace_identity.so: pulse_pace_uname.c
	$(CC) $(CFLAGS) -shared -Wl,-z,relro,-z,now -o $@ $<
clean:
	rm -f libpulse_pace_identity.so
