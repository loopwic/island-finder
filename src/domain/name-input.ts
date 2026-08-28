export type NameInputMode = 'empty' | 'chinese' | 'english' | 'unsupported';

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

export function detectNameInputMode(name: string): NameInputMode {
  const normalized = name.trim();
  if (!normalized) return 'empty';
  const characters = Array.from(normalized);
  if (characters.length > 10) return 'unsupported';
  if (characters.every(isHanCharacter)) return 'chinese';
  if (/^[a-z]+$/i.test(normalized)) return 'english';
  return 'unsupported';
}

export function validateName(name: string, pinyinByCharacter: string[]): void {
  const characters = Array.from(name.trim());
  if (characters.length < 1 || characters.length > 10) throw new Error('名字需要 1–10 个字符');
  const mode = detectNameInputMode(name);
  if (mode === 'english') return;
  if (mode !== 'chinese') {
    throw new Error('名字仅支持全中文或纯英文字母，不支持中英混输、数字和符号');
  }
  characters.forEach((character, index) => {
    const pinyin = normalizePinyin(pinyinByCharacter[index] ?? '');
    if (!/^[a-zv]{1,6}$/.test(pinyin)) {
      throw new Error(`请填写“${character}”的拼音（不带声调）`);
    }
  });
}
