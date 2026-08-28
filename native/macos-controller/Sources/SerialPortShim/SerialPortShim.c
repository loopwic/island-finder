#include "SerialPortShim.h"

#include <errno.h>
#include <IOKit/serial/ioss.h>
#include <sys/ioctl.h>
#include <termios.h>

int AFConfigureRawSerialPort(int descriptor, unsigned long baudRate) {
    struct termios options;
    if (tcgetattr(descriptor, &options) != 0) {
        return errno;
    }

    cfmakeraw(&options);
    options.c_cflag &= ~(PARENB | CSTOPB | CSIZE);
    options.c_cflag |= CS8 | CLOCAL | CREAD;
    options.c_cc[VMIN] = 0;
    options.c_cc[VTIME] = 0;
    if (cfsetspeed(&options, B115200) != 0) {
        return errno;
    }
    if (tcsetattr(descriptor, TCSANOW, &options) != 0) {
        return errno;
    }

    speed_t speed = (speed_t)baudRate;
    if (ioctl(descriptor, IOSSIOSPEED, &speed) != 0) {
        return errno;
    }

    int modemBits = TIOCM_DTR | TIOCM_RTS;
    (void)ioctl(descriptor, TIOCMBIC, &modemBits);
    (void)tcflush(descriptor, TCIOFLUSH);
    return 0;
}
