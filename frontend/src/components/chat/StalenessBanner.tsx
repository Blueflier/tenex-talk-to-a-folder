import { AlertTriangle, XCircle, ShieldAlert } from "lucide-react";

export interface StalenessInfo {
  file_name: string;
  file_id: string;
  error?: "not_found" | "access_denied" | null;
}

interface StalenessBannerProps {
  info: StalenessInfo;
  sessionId: string;
  onReindexComplete?: (fileId: string, indexedAt: string) => void;
  reindexSlot?: React.ReactNode;
  noMatches?: boolean;
}

export function StalenessBanner({
  info,
  noMatches,
  reindexSlot,
}: StalenessBannerProps) {
  if (info.error === "not_found") {
    return (
      <div
        data-testid="staleness-banner"
        className="flex items-start gap-2 rounded-lg border bg-red-50 border-red-200 text-red-800 px-3 py-2 text-sm"
      >
        <XCircle className="h-4 w-4 mt-0.5 shrink-0" />
        <span>
          This file no longer exists in Google Drive. Old answers from this file
          may be outdated.
        </span>
      </div>
    );
  }

  if (info.error === "access_denied") {
    return (
      <div
        data-testid="staleness-banner"
        className="flex items-start gap-2 rounded-lg border bg-amber-50 border-amber-200 text-amber-800 px-3 py-2 text-sm"
      >
        <ShieldAlert className="h-4 w-4 mt-0.5 shrink-0" />
        <span className="flex-1">
          Access to {info.file_name} was revoked. Check your Google Drive
          permissions.
        </span>
        <button
          className="shrink-0 rounded bg-amber-200 px-2 py-0.5 text-xs font-medium hover:bg-amber-300"
          onClick={() => {
            // Re-auth flow placeholder (Phase 1 auth)
            const event = new CustomEvent("reauth-requested");
            window.dispatchEvent(event);
          }}
        >
          Re-authenticate
        </button>
      </div>
    );
  }

  // Default: stale (yellow)
  return (
    <div
      data-testid="staleness-banner"
      className="flex items-start gap-2 rounded-lg border bg-yellow-50 border-yellow-200 text-yellow-800 px-3 py-2 text-sm"
    >
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
      <span className="flex-1">
        <span className="font-medium">{info.file_name}</span> was modified after
        indexing -- showing live search results for this file.
        {noMatches && (
          <>
            <br />
            No matches found -- re-index for best results.
          </>
        )}
      </span>
      {reindexSlot}
    </div>
  );
}
