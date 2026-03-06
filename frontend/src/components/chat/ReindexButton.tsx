import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ReindexButtonProps {
  fileId: string;
  isReindexing: boolean;
  onReindex: () => void;
}

export function ReindexButton({
  isReindexing,
  onReindex,
}: ReindexButtonProps) {
  return (
    <Button
      variant="outline"
      size="sm"
      disabled={isReindexing}
      onClick={onReindex}
      className="shrink-0 gap-1.5"
    >
      {isReindexing ? (
        <>
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Re-indexing...
        </>
      ) : (
        <>
          <RefreshCw className="h-3.5 w-3.5" />
          Re-index this file
        </>
      )}
    </Button>
  );
}
