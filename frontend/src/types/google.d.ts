declare namespace google.accounts.oauth2 {
  interface TokenClient {
    requestAccessToken(overridableClientConfig?: { prompt?: string }): void;
  }

  interface TokenResponse {
    access_token: string;
    error?: string;
    error_description?: string;
    error_uri?: string;
    expires_in: number;
    scope: string;
    token_type: string;
  }

  interface ErrorResponse {
    type: string;
    message?: string;
  }

  interface TokenClientConfig {
    client_id: string;
    scope: string;
    callback: (response: TokenResponse) => void;
    error_callback?: (error: ErrorResponse) => void;
    prompt?: string;
  }

  function initTokenClient(config: TokenClientConfig): TokenClient;
}
