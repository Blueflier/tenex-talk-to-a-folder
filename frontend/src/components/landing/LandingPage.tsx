import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FolderOpen, AlertCircle } from "lucide-react";

interface LandingPageProps {
  onSignIn: () => void;
  authError?: string;
  loading?: boolean;
}

export function LandingPage({ onSignIn, authError, loading }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <FolderOpen className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">Talk to a Folder</CardTitle>
          <CardDescription>
            Ask questions about your Google Drive files and get cited answers.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground text-center">
            Your files stay in Google Drive. We only read them to answer your
            questions.
          </p>

          {authError && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                <p>{authError}</p>
                <p className="mt-1 text-muted-foreground">
                  Drive access is needed so we can read your files and answer
                  questions about them.
                </p>
              </div>
            </div>
          )}

          <Button
            size="lg"
            className="w-full"
            onClick={onSignIn}
            disabled={loading}
          >
            {loading ? "Signing in..." : "Sign in with Google"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
