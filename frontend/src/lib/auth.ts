let tokenClient: google.accounts.oauth2.TokenClient;

export function initAuth(
  onSuccess: (token: string) => void,
  onError: (err: string) => void
): void {
  if (!window.google?.accounts?.oauth2) {
    throw new Error(
      "Google Identity Services not loaded. Ensure the GIS script is in index.html."
    );
  }

  tokenClient = google.accounts.oauth2.initTokenClient({
    client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
    scope: "https://www.googleapis.com/auth/drive.readonly",
    callback: (response) => {
      if (response.error) {
        onError(response.error);
        return;
      }
      if (response.access_token) {
        sessionStorage.setItem("google_access_token", response.access_token);
        onSuccess(response.access_token);
      }
    },
    error_callback: (err) => {
      onError(err.type);
    },
  });
}

export function requestToken(): void {
  tokenClient.requestAccessToken();
}
