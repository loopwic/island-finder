# PABotBase2 ESP32-S3 board LED-off bootloader

This project builds only a replacement ESP-IDF second-stage bootloader. It
sends one all-black addressable-LED frame on GPIO 48 during boot, then starts
the unmodified official PABotBase2 application at `0x10000`.

The production application, partition table, NVS, and PHY data are not part of
this build and must not be replaced by its placeholder application.

Build with ESP-IDF v6.0.2:

```sh
idf.py set-target esp32s3
idf.py bootloader
```

Flash only the generated bootloader:

```sh
esptool.py --chip esp32s3 --port /dev/cu.usbmodemEXAMPLE \
  write_flash 0x0 build/bootloader/bootloader.bin
```

Back up the complete original flash to a private location before modifying the
bootloader. Firmware backups may contain device-specific data and must not be
committed to this repository.
