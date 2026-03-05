import { StalenessBanner, type StalenessInfo } from "./StalenessBanner";

interface StalenessBannerListProps {
  staleFiles: StalenessInfo[];
  sessionId: string;
  renderReindexButton?: (info: StalenessInfo) => React.ReactNode;
}

export function StalenessBannerList({
  staleFiles,
  sessionId,
  renderReindexButton,
}: StalenessBannerListProps) {
  if (staleFiles.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 mb-2">
      {staleFiles.map((info) => (
        <StalenessBanner
          key={info.file_id}
          info={info}
          sessionId={sessionId}
          reindexSlot={renderReindexButton?.(info)}
        />
      ))}
    </div>
  );
}
