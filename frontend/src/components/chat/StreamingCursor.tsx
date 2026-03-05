export function StreamingCursor({ visible }: { visible: boolean }) {
  if (!visible) return null;

  return (
    <span
      className="inline-block w-[2px] h-[1.1em] bg-current align-text-bottom animate-blink"
      aria-hidden="true"
    />
  );
}
