from __future__ import annotations

import re
import unicodedata
from collections import deque
from typing import Any


PINYIN_ROWS = (
    "1234567890-",
    "qwertyuiop/",
    "asdfghjkl:\\",
    "zxcvbnm,.?!",
)


def normalize_pinyin(value: str) -> str:
    normalized = value.strip().lower()
    for source in "üǖǘǚǜ":
        normalized = normalized.replace(source, "v")
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFD", normalized)
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[1-5]", "", normalized)


def _is_han(character: str) -> bool:
    name = unicodedata.name(character, "")
    return "CJK UNIFIED IDEOGRAPH" in name or "CJK COMPATIBILITY IDEOGRAPH" in name


def name_input_mode(identity: dict[str, Any]) -> str:
    characters = list(str(identity.get("name", "")).strip())
    if not characters:
        return "empty"
    if len(characters) > 10:
        return "unsupported"
    if all(_is_han(character) for character in characters):
        return "chinese"
    if re.fullmatch(r"[A-Za-z]+", "".join(characters)):
        return "english"
    return "unsupported"


def validate_name(identity: dict[str, Any]) -> str:
    characters = list(str(identity.get("name", "")).strip())
    if not 1 <= len(characters) <= 10:
        raise ValueError("名字需要 1–10 个字符")
    mode = name_input_mode(identity)
    if mode == "english":
        return mode
    if mode != "chinese":
        raise ValueError("名字仅支持全中文或纯英文字母，不支持中英混输、数字和符号")
    pinyin = identity.get("namePinyin", [])
    for index, character in enumerate(characters):
        value = normalize_pinyin(str(pinyin[index] if index < len(pinyin) else ""))
        if not re.fullmatch(r"[a-zv]{1,6}", value):
            raise ValueError(f"请填写“{character}”的拼音（不带声调）")
    return mode


def press(button: str, hold_ms: int = 80, after_ms: int = 160) -> dict[str, Any]:
    return {"type": "press", "button": button, "holdMs": hold_ms, "afterMs": after_ms}


RESTART_COMMANDS = [
    press("HOME", 100, 1100),
    press("X", 80, 350),
    press("A", 80, 1500),
    press("A", 80, 1600),
    press("A", 220, 1500),
]


def _keyboard_nodes() -> list[tuple[str, float, int]]:
    return [
        (key, float(column), row)
        for row, keys in enumerate(PINYIN_ROWS)
        for column, key in enumerate(keys)
    ]


PINYIN_NODES = _keyboard_nodes()


def _neighbors(node: tuple[str, float, int]) -> list[tuple[tuple[str, float, int], str]]:
    key, x, y = node
    horizontal = sorted((item for item in PINYIN_NODES if item[2] == y), key=lambda item: item[1])
    index = next(position for position, item in enumerate(horizontal) if item[0] == key)
    result: list[tuple[tuple[str, float, int], str]] = []
    if index > 0:
        result.append((horizontal[index - 1], "LEFT"))
    if index < len(horizontal) - 1:
        result.append((horizontal[index + 1], "RIGHT"))
    for dy, button in ((-1, "UP"), (1, "DOWN")):
        row = [item for item in PINYIN_NODES if item[2] == y + dy]
        if row:
            result.append((min(row, key=lambda item: abs(item[1] - x)), button))
    return result


def _path_between(source: str, target: str) -> list[str]:
    if source == target:
        return []
    nodes = {item[0]: item for item in PINYIN_NODES}
    if source not in nodes or target not in nodes:
        raise ValueError(f"键盘上找不到字符：{source if source not in nodes else target}")
    queue: deque[tuple[str, list[str]]] = deque([(source, [])])
    visited = {source}
    while queue:
        key, path = queue.popleft()
        for node, button in _neighbors(nodes[key]):
            if node[0] in visited:
                continue
            next_path = [*path, button]
            if node[0] == target:
                return next_path
            visited.add(node[0])
            queue.append((node[0], next_path))
    raise ValueError(f"键盘上找不到字符：{target}")


def commands_for_pinyin(value: str, cursor: str = "1") -> tuple[list[dict[str, Any]], str]:
    pinyin = normalize_pinyin(value)
    if not re.fullmatch(r"[a-zv]{1,6}", pinyin):
        raise ValueError("拼音需要使用 1–6 位英文字母")
    commands: list[dict[str, Any]] = []
    current = cursor
    for character in pinyin:
        commands.extend(press(button, 45, 72) for button in _path_between(current, character))
        commands.append(press("A", 45, 105))
        current = character
    commands[-1] = press("A", 45, 420)
    return commands, current


def commands_for_english_character(character: str, cursor: str) -> tuple[list[dict[str, Any]], str]:
    normalized = character.lower()
    if not re.fullmatch(r"[a-z]", normalized):
        raise ValueError("英文名字只能输入英文字母")
    commands = [press(button, 45, 72) for button in _path_between(cursor, normalized)]
    commands.append(press("A", 45, 260))
    return commands, normalized


def commands_to_candidate_row(last_key: str) -> list[dict[str, Any]]:
    node = next((item for item in PINYIN_NODES if item[0] == last_key), None)
    if node is None or node[2] == 0:
        raise ValueError("无法从当前拼音按键进入候选栏")
    return [press("UP", 45, 55) for _ in range(node[2] + 1)]


def commands_for_candidate_move(source: int, target: int) -> list[dict[str, Any]]:
    if source < 0 or target < 0:
        raise ValueError("候选栏位置无效")
    delta = target - source
    button = "RIGHT" if delta >= 0 else "LEFT"
    return [press(button, 45, 55) for _ in range(abs(delta))]


def commands_for_birthday(month: int, day: int, origin_month: int, origin_day: int) -> list[dict[str, Any]]:
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise ValueError("生日配置无效")
    commands = [press("UP" if month >= origin_month else "DOWN") for _ in range(abs(month - origin_month))]
    commands.append(press("RIGHT", 80, 120))
    commands.extend(press("UP" if day >= origin_day else "DOWN") for _ in range(abs(day - origin_day)))
    return commands
