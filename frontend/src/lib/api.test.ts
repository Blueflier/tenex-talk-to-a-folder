import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// Mock import.meta.env before importing module
vi.stubEnv("VITE_API_URL", "http://localhost:8000");

const { apiFetch } = await import("./api");

describe("apiFetch", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    sessionStorage.clear();
  });

  it("attaches Authorization: Bearer {token} header from sessionStorage", async () => {
    sessionStorage.setItem("google_access_token", "test-token-123");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: "ok" }),
    });

    await apiFetch("/health");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/health",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token-123",
          "Content-Type": "application/json",
        }),
      })
    );
  });

  it('throws "NO_TOKEN" error when sessionStorage has no token', async () => {
    await expect(apiFetch("/health")).rejects.toThrow("NO_TOKEN");
  });

  it('throws "TOKEN_EXPIRED" and clears sessionStorage on 401 response', async () => {
    sessionStorage.setItem("google_access_token", "expired-token");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
    });

    await expect(apiFetch("/health")).rejects.toThrow("TOKEN_EXPIRED");
    expect(sessionStorage.getItem("google_access_token")).toBeNull();
  });

  it('throws "TOKEN_EXPIRED" and clears sessionStorage on 403 response', async () => {
    sessionStorage.setItem("google_access_token", "forbidden-token");

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
    });

    await expect(apiFetch("/health")).rejects.toThrow("TOKEN_EXPIRED");
    expect(sessionStorage.getItem("google_access_token")).toBeNull();
  });
});
