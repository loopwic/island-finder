# Notices

Island Finder is an independent interoperability project. It is not affiliated
with, authorized by, or endorsed by Nintendo or the PABotBase2 project.

Nintendo Switch, Animal Crossing, and related names, interface artwork, and
trademarks belong to their respective owners. Small cropped map images under
`vision_service/tests/fixtures/` are retained only as regression evidence for
computer-vision interoperability. Those images are not covered by the MIT
license granted for this repository's source code.

The repository does not include game binaries, decryption keys, user profiles,
console identifiers, captured account screens, production firmware backups, or
private runtime audit data.

## PABotBase2 firmware

`vision_service/firmware_assets/` contains an unmodified PABotBase2 ESP32-S3
binary from Pokémon Automation, pinned to release `2026090200`. Its exact upstream
commit, source URL and SHA-256 are recorded in `manifest.json` in that directory.
The upstream licensing notice is preserved in `UPSTREAM-README.md` and included
in desktop installation resources alongside the binary.

PABotBase is free for non-commercial use only. For all other uses, contact the
Pokémon Automation server admins. This firmware is **not** covered by Island
Finder's MIT license. Upstream notice:
https://github.com/PokemonAutomation/Packages/blob/641ba20b00dadc06e1990cf25dd9a7054b85e28c/Firmware/README.md
