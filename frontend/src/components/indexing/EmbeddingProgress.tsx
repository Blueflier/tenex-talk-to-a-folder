import { Progress } from "@/components/ui/progress";

interface EmbeddingProgressProps {
  embedded: number;
  total: number;
}

export function EmbeddingProgress({ embedded, total }: EmbeddingProgressProps) {
  const percentage = total > 0 ? Math.round((embedded / total) * 100) : 0;

  return (
    <div className="space-y-2" data-testid="embedding-progress">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Embedding chunks...</span>
        <span className="font-medium">
          {embedded}/{total} chunks
        </span>
      </div>
      <Progress value={percentage} />
    </div>
  );
}
