export function bionicText(text: string) {
  return text.split(/\s+/).map((word, i) => {
    const mid = Math.max(1, Math.ceil(word.length * 0.55));
    return (
      <span key={i}>
        <b className="font-bold text-slate-900 dark:text-white">{word.slice(0, mid)}</b>
        {word.slice(mid)}{' '}
      </span>
    );
  });
}
