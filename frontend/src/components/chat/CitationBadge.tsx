import { useCallback, type MouseEvent } from "react";

interface CitationBadgeProps {
  index: number;
  onClick: (index: number, anchorEl: HTMLElement) => void;
}

export function CitationBadge({ index, onClick }: CitationBadgeProps) {
  const handleClick = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      onClick(index, e.currentTarget);
    },
    [index, onClick]
  );

  return (
    <button
      type="button"
      onClick={handleClick}
      className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 mx-0.5 text-xs font-medium text-blue-600 bg-blue-50 rounded-full hover:underline hover:bg-blue-100 cursor-pointer align-baseline transition-colors"
      aria-label={`Citation ${index}`}
    >
      {index}
    </button>
  );
}
