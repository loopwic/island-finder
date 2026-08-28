import { describe, expect, it } from 'vitest';
import contractCases from '../../contracts/name-input-cases.json';
import { detectNameInputMode, normalizePinyin, validateName } from './name-input';

describe('name input contract', () => {
  it.each(contractCases)('$name resolves to $mode and valid=$valid', ({ name, pinyin, mode, valid }) => {
    expect(detectNameInputMode(name)).toBe(mode);
    const validate = () => validateName(name, pinyin);
    if (valid) expect(validate).not.toThrow();
    else expect(validate).toThrow();
  });

  it('normalizes tones and umlaut pinyin without changing the contract data', () => {
    expect(normalizePinyin(' Huì4 ')).toBe('hui');
    expect(normalizePinyin('lǜ')).toBe('lv');
  });
});
