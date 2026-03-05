import { useCallback, useEffect, useState } from "react";
import { initAuth, requestToken } from "@/lib/auth";
import { LandingPage } from "@/components/landing/LandingPage";
import { AppShell } from "@/components/app-shell/AppShell";
import { ReAuthModal } from "@/components/app-shell/ReAuthModal";

function App() {
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem("google_access_token")
  );
  const [authError, setAuthError] = useState<string>();
  const [showReAuth, setShowReAuth] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [gisReady, setGisReady] = useState(false);

  useEffect(() => {
    const tryInit = () => {
      if (window.google?.accounts?.oauth2) {
        initAuth(
          (newToken) => {
            setToken(newToken);
            setAuthError(undefined);
            setShowReAuth(false);
            setAuthLoading(false);
          },
          (err) => {
            setAuthLoading(false);
            if (err === "access_denied") {
              setAuthError(
                "You denied access to Google Drive. Drive access is required to read your files."
              );
            } else if (err === "popup_closed") {
              setAuthError("Sign-in popup was closed. Please try again.");
            } else {
              setAuthError(`Authentication error: ${err}`);
            }
          }
        );
        setGisReady(true);
        return true;
      }
      return false;
    };

    if (!tryInit()) {
      // GIS script may still be loading -- poll briefly
      const interval = setInterval(() => {
        if (tryInit()) clearInterval(interval);
      }, 200);
      // Stop polling after 10s
      const timeout = setTimeout(() => clearInterval(interval), 10_000);
      return () => {
        clearInterval(interval);
        clearTimeout(timeout);
      };
    }
  }, []);

  const handleSignIn = useCallback(() => {
    if (!gisReady) {
      setAuthError("Google sign-in is still loading. Please wait a moment.");
      return;
    }
    setAuthLoading(true);
    setAuthError(undefined);
    requestToken();
  }, [gisReady]);

  const handleReAuth = useCallback(() => {
    setAuthLoading(true);
    requestToken();
  }, []);

  // Listen for TOKEN_EXPIRED errors from API calls
  useEffect(() => {
    const handler = (event: PromiseRejectionEvent) => {
      if (event.reason?.message === "TOKEN_EXPIRED") {
        setToken(null);
        setShowReAuth(true);
        event.preventDefault();
      }
    };
    window.addEventListener("unhandledrejection", handler);
    return () => window.removeEventListener("unhandledrejection", handler);
  }, []);

  if (!token) {
    return (
      <LandingPage
        onSignIn={handleSignIn}
        authError={authError}
        loading={authLoading}
      />
    );
  }

  return (
    <>
      <AppShell />
      <ReAuthModal open={showReAuth} onReAuth={handleReAuth} />
    </>
  );
}

export default App;
