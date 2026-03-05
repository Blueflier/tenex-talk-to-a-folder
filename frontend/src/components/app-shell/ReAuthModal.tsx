import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ReAuthModalProps {
  open: boolean;
  onReAuth: () => void;
}

export function ReAuthModal({ open, onReAuth }: ReAuthModalProps) {
  return (
    <Dialog open={open}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Your session has expired</DialogTitle>
          <DialogDescription>
            Please sign in again to continue using Talk to a Folder. Your chat
            history is still available.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={onReAuth} className="w-full sm:w-auto">
            Sign in with Google
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
