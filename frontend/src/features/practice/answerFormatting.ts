import type { AnswerCharPart, AnswerCharState, AnswerTypo } from '@/shared/practice';

export function buildAnswerParts(text: string, typo: AnswerTypo | null, line: string): AnswerCharPart[] {
  const chars = Array.from(text);
  const parts = chars.map((value, index) => ({
    key: `${line}-${index}-${value}`,
    value,
    state: 'normal' as AnswerCharState,
  }));

  if (!typo) {
    return parts;
  }

  const index = Math.max(0, Math.min(typo.index, chars.length));

  if (typo.type === 'missing') {
    if (line === 'submitted') {
      parts.splice(index, 0, {
        key: `${line}-missing-${index}`,
        value: typo.expected ?? '',
        state: 'missing',
      });
    } else if (parts[index]) {
      parts[index].state = 'expected';
    }

    return parts;
  }

  if (typo.type === 'extra') {
    if (line === 'submitted' && parts[index]) {
      parts[index].state = 'extra';
    }

    return parts;
  }

  if (line === 'submitted' && parts[index]) {
    parts[index].state = 'replace';
  }

  if (line === 'correct' && parts[index]) {
    parts[index].state = 'expected';
  }

  return parts;
}
