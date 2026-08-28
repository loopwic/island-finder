#ifndef SERIAL_PORT_SHIM_H
#define SERIAL_PORT_SHIM_H

/// Configures a POSIX serial descriptor for raw 8-N-1 traffic at an arbitrary
/// baud rate. Returns zero on success or the errno value from the failed call.
int AFConfigureRawSerialPort(int descriptor, unsigned long baudRate);

#endif
