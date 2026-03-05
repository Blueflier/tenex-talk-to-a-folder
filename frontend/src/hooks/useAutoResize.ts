import { useCallback, type RefObject } from "react";

const MAX_HEIGHT = 200;

export function useAutoResize(ref: RefObject<HTMLTextAreaElement | null>) {
  const resize = useCallback(() => {
    const el = ref.current;
    if (!el) return;

    // Reset to auto so shrinking works
    el.style.height = "auto";

    const next = Math.min(el.scrollHeight, MAX_HEIGHT);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  }, [ref]);

  return resize;
}
