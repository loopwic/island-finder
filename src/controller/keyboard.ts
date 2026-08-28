import type { ControllerCommand } from '../domain/types';

type KeyNode = { key: string; x: number; y: number };

const ENGLISH_KEYBOARD: KeyNode[] = [
  ...'qwertyuiop'.split('').map((key, x) => ({ key, x, y: 0 })),
  ...'asdfghjkl'.split('').map((key, x) => ({ key, x: x + 0.5, y: 1 })),
  ...'zxcvbnm'.split('').map((key, x) => ({ key, x: x + 1.5, y: 2 })),
  { key: ' ', x: 4.5, y: 3 },
];

const PINYIN_KEYBOARD: KeyNode[] = [
  ...'1234567890-'.split('').map((key, x) => ({ key, x, y: 0 })),
  ...'qwertyuiop/'.split('').map((key, x) => ({ key, x, y: 1 })),
  ...'asdfghjkl:\\'.split('').map((key, x) => ({ key, x, y: 2 })),
  ...'zxcvbnm,.?!'.split('').map((key, x) => ({ key, x, y: 3 })),
];

function neighbors(
  keyboard: KeyNode[],
  node: KeyNode,
): Array<{ node: KeyNode; button: ControllerCommand['button'] }> {
  const horizontal = keyboard.filter((candidate) => candidate.y === node.y).sort((a, b) => a.x - b.x);
  const index = horizontal.findIndex((candidate) => candidate.key === node.key);
  const result: Array<{ node: KeyNode; button: ControllerCommand['button'] }> = [];
  if (index > 0) result.push({ node: horizontal[index - 1], button: 'LEFT' });
  if (index < horizontal.length - 1) result.push({ node: horizontal[index + 1], button: 'RIGHT' });
  for (const [dy, button] of [
    [-1, 'UP'],
    [1, 'DOWN'],
  ] as const) {
    const row = keyboard.filter((candidate) => candidate.y === node.y + dy);
    if (row.length > 0) {
      const closest = row.reduce((best, candidate) =>
        Math.abs(candidate.x - node.x) < Math.abs(best.x - node.x) ? candidate : best,
      );
      result.push({ node: closest, button });
    }
  }
  return result;
}

function pathBetween(
  keyboard: KeyNode[],
  from: string,
  to: string,
): ControllerCommand['button'][] {
  if (from === to) return [];
  const queue: Array<{ key: string; path: ControllerCommand['button'][] }> = [{ key: from, path: [] }];
  const visited = new Set([from]);
  while (queue.length > 0) {
    const current = queue.shift()!;
    const node = keyboard.find((candidate) => candidate.key === current.key);
    if (!node) throw new Error(`键盘上找不到字符：${current.key}`);
    for (const next of neighbors(keyboard, node)) {
      if (visited.has(next.node.key)) continue;
      const path = [...current.path, next.button];
      if (next.node.key === to) return path;
      visited.add(next.node.key);
      queue.push({ key: next.node.key, path });
    }
  }
  throw new Error(`键盘上找不到字符：${to}`);
}

export type PinyinPathStep = {
  button: ControllerCommand['button'];
  key: string;
};

export function pinyinPathSteps(from: string, to: string): PinyinPathStep[] {
  if (from === to) return [];
  const buttons = pathBetween(PINYIN_KEYBOARD, from, to);
  const steps: PinyinPathStep[] = [];
  const start = PINYIN_KEYBOARD.find((node) => node.key === from);
  if (!start) throw new Error(`键盘上找不到字符：${from}`);
  let current: KeyNode = start;
  for (const button of buttons) {
    const next: { node: KeyNode; button: ControllerCommand['button'] } | undefined = neighbors(
      PINYIN_KEYBOARD,
      current,
    ).find((candidate) => candidate.button === button);
    if (!next) throw new Error(`无法验证从“${current.key}”开始的键盘路径`);
    steps.push({ button, key: next.node.key });
    current = next.node;
  }
  return steps;
}

function press(button: ControllerCommand['button'], afterMs = 55): ControllerCommand {
  return { type: 'press', button, holdMs: 45, afterMs };
}

export function commandsForName(name: string): ControllerCommand[] {
  const normalized = name.toLowerCase();
  if (!/^[a-z ]{1,10}$/.test(normalized)) {
    throw new Error('当前键盘方案仅支持 1–10 位英文字母或空格');
  }
  const commands: ControllerCommand[] = [];
  let cursor = 'q';
  for (const character of normalized) {
    for (const button of pathBetween(ENGLISH_KEYBOARD, cursor, character)) commands.push(press(button));
    commands.push(press('A', 80));
    cursor = character;
  }
  commands.push(press('PLUS', 500));
  return commands;
}

export type PinyinTypingPlan = {
  commands: ControllerCommand[];
  lastKey: string;
};

export function commandsToClearKeyboard(maxCharacters = 10): ControllerCommand[] {
  if (!Number.isInteger(maxCharacters) || maxCharacters < 1) {
    throw new Error('键盘清空长度无效');
  }
  // On the Switch keyboard B is the dedicated backspace action. A few stale
  // dialogue confirmations can arrive during the page transition; clearing
  // before typing makes that transition harmless and does not move the cursor.
  return Array.from({ length: maxCharacters }, () => press('B', 45));
}

export function normalizePinyin(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[üǖǘǚǜ]/g, 'v')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/[1-5]/g, '');
}

export function isHanCharacter(value: string): boolean {
  return /^\p{Script=Han}$/u.test(value);
}

export function validateChineseName(name: string, pinyinByCharacter: string[]): void {
  const characters = Array.from(name.trim());
  if (characters.length < 1 || characters.length > 10) throw new Error('名字需要 1–10 个汉字');
  if (!characters.every(isHanCharacter)) throw new Error('中文自动输入目前只支持汉字名字');
  characters.forEach((character, index) => {
    const pinyin = normalizePinyin(pinyinByCharacter[index] ?? '');
    if (!/^[a-zv]{1,6}$/.test(pinyin)) {
      throw new Error(`请填写“${character}”的拼音（不带声调）`);
    }
  });
}

export function commandsForPinyin(
  value: string,
  cursor = '1',
): PinyinTypingPlan {
  const pinyin = normalizePinyin(value);
  if (!/^[a-zv]{1,6}$/.test(pinyin)) throw new Error('拼音需要使用 1–6 位英文字母');
  const commands: ControllerCommand[] = [];
  let current = cursor;
  for (const character of pinyin) {
    for (const button of pathBetween(PINYIN_KEYBOARD, current, character)) {
      commands.push(press(button, 72));
    }
    commands.push(press('A', 105));
    current = character;
  }
  // Wait for the Switch IME to finish populating the candidate row.
  commands[commands.length - 1] = press('A', 420);
  return { commands, lastKey: current };
}

export function commandsToCandidateRow(lastKey: string): ControllerCommand[] {
  const key = PINYIN_KEYBOARD.find((candidate) => candidate.key === lastKey);
  if (!key || key.y === 0) throw new Error('无法从当前拼音按键进入候选栏');
  return Array.from({ length: key.y + 1 }, () => press('UP', 55));
}

export function commandsForCandidateMove(
  fromIndex: number,
  toIndex: number,
): ControllerCommand[] {
  if (!Number.isInteger(fromIndex) || !Number.isInteger(toIndex) || fromIndex < 0 || toIndex < 0) {
    throw new Error('候选栏位置无效');
  }
  const delta = toIndex - fromIndex;
  const button: ControllerCommand['button'] = delta >= 0 ? 'RIGHT' : 'LEFT';
  return Array.from({ length: Math.abs(delta) }, () => press(button, 55));
}

function monotonicSelectorMoves(from: number, to: number): ControllerCommand[] {
  const button: ControllerCommand['button'] = to >= from ? 'UP' : 'DOWN';
  const count = Math.abs(to - from);
  return Array.from({ length: count }, () => press(button));
}

export function commandsForBirthday(
  month: number,
  day: number,
  originMonth = 1,
  originDay = 1,
): ControllerCommand[] {
  if (!Number.isInteger(month) || month < 1 || month > 12) throw new Error('出生月份无效');
  if (!Number.isInteger(day) || day < 1 || day > 31) throw new Error('出生日期无效');
  return [
    ...monotonicSelectorMoves(originMonth, month),
    press('RIGHT', 120),
    ...monotonicSelectorMoves(originDay, day),
  ];
}
