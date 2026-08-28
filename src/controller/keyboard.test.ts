import { describe, expect, it } from 'vitest';
import {
  commandsForBirthday,
  commandsForCandidateMove,
  commandsForName,
  commandsForPinyin,
  commandsToClearKeyboard,
  commandsToCandidateRow,
  normalizePinyin,
  pinyinPathSteps,
  validateChineseName,
} from './keyboard';

describe('controller input planning', () => {
  it('types every name character once and submits with PLUS', () => {
    const commands = commandsForName('Nook');
    expect(commands.filter((command) => command.button === 'A')).toHaveLength(4);
    expect(commands.at(-1)?.button).toBe('PLUS');
  });

  it('rejects names that the calibrated keyboard cannot enter safely', () => {
    expect(() => commandsForName('小狸')).toThrow(/英文字母/);
    expect(() => commandsForName('morethanten!')).toThrow(/英文字母/);
  });

  it('moves monotonically from 1/1 to 10/29 without submitting blindly', () => {
    const commands = commandsForBirthday(10, 29);
    expect(commands.filter((command) => command.button === 'UP')).toHaveLength(37);
    expect(commands.filter((command) => command.button === 'DOWN')).toHaveLength(0);
    expect(commands.at(-1)?.button).toBe('UP');
    expect(commands.some((command) => command.button === 'PLUS')).toBe(false);
    expect(commands.filter((command) => command.button === 'RIGHT')).toHaveLength(1);
  });

  it('normalizes user-supplied pinyin and validates one syllable per Han character', () => {
    expect(normalizePinyin(' Huì4 ')).toBe('hui');
    expect(normalizePinyin('lǜ')).toBe('lv');
    expect(() => validateChineseName('明慧', ['ming', 'hui'])).not.toThrow();
    expect(() => validateChineseName('明慧', ['ming'])).toThrow(/慧/);
  });

  it('types pinyin on the aligned Switch keyboard and restores its digit-column cursor', () => {
    const plan = commandsForPinyin('hui', '5');
    expect(plan.commands.filter((command) => command.button === 'A')).toHaveLength(3);
    expect(plan.lastKey).toBe('i');
    expect(pinyinPathSteps('5', 'h').at(-1)?.key).toBe('h');
  });

  it('clears transition keystrokes before typing a name without moving the cursor', () => {
    const commands = commandsToClearKeyboard();
    expect(commands).toHaveLength(10);
    expect(commands.every((command) => command.button === 'B')).toBe(true);
  });

  it('exposes every expected keyboard cursor state for visual verification', () => {
    const steps = pinyinPathSteps('1', 'g');
    expect(steps.at(-1)?.key).toBe('g');
    expect(steps.every((step) => ['UP', 'DOWN', 'LEFT', 'RIGHT'].includes(step.button))).toBe(true);
  });

  it('batches candidate-row entry and bounded movement after OCR establishes the cursor', () => {
    expect(commandsToCandidateRow('g').map((command) => command.button)).toEqual(['UP', 'UP', 'UP']);
    expect(commandsForCandidateMove(5, 1).map((command) => command.button)).toEqual([
      'LEFT', 'LEFT', 'LEFT', 'LEFT',
    ]);
  });
});
