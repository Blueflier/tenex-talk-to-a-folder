import { useState } from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { formatCitationLabel, type Citation } from "@/lib/citations";

const TRUNCATE_LENGTH = 200;

interface CitationPopoverProps {
  citation: Citation | null;
  anchorEl: HTMLElement | null;
  onClose: () => void;
}

export function CitationPopover({
  citation,
  anchorEl,
  onClose,
}: CitationPopoverProps) {
  const [expanded, setExpanded] = useState(false);

  if (!citation || !anchorEl) return null;

  const needsTruncation = citation.chunk_text.length > TRUNCATE_LENGTH;
  const displayText =
    !expanded && needsTruncation
      ? citation.chunk_text.slice(0, TRUNCATE_LENGTH) + "..."
      : citation.chunk_text;

  return (
    <Popover
      open={true}
      onOpenChange={(open) => {
        if (!open) {
          setExpanded(false);
          onClose();
        }
      }}
    >
      <PopoverTrigger asChild>
        <span
          ref={(node) => {
            // Anchor the popover to the badge element position
            if (node) {
              const rect = anchorEl.getBoundingClientRect();
              node.style.position = "fixed";
              node.style.left = `${rect.left + rect.width / 2}px`;
              node.style.top = `${rect.top}px`;
              node.style.width = "0";
              node.style.height = "0";
            }
          }}
        />
      </PopoverTrigger>
      <PopoverContent className="w-80 text-sm" side="top" align="center">
        <div className="space-y-2">
          <p className="font-medium text-foreground">
            [{citation.index}] {formatCitationLabel(citation)}
          </p>
          <p className="text-muted-foreground whitespace-pre-wrap leading-relaxed">
            {displayText}
          </p>
          {needsTruncation && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-blue-600 hover:underline"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
