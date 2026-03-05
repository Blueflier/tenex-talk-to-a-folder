import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LandingPage } from "./LandingPage";

vi.mock("@/lib/auth", () => ({
  initAuth: vi.fn(),
  requestToken: vi.fn(),
}));

describe("LandingPage", () => {
  it("renders sign-in button", () => {
    render(<LandingPage onSignIn={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: /sign in with google/i })
    ).toBeDefined();
  });

  it('renders privacy messaging containing "Google Drive"', () => {
    render(<LandingPage onSignIn={vi.fn()} />);
    expect(screen.getByText(/google drive/i)).toBeDefined();
  });

  it("renders error message when authError prop is set", () => {
    render(
      <LandingPage onSignIn={vi.fn()} authError="Permission denied" />
    );
    expect(screen.getByText(/permission denied/i)).toBeDefined();
  });

  it("calls onSignIn callback when sign-in button clicked", () => {
    const onSignIn = vi.fn();
    render(<LandingPage onSignIn={onSignIn} />);
    fireEvent.click(
      screen.getByRole("button", { name: /sign in with google/i })
    );
    expect(onSignIn).toHaveBeenCalledTimes(1);
  });
});
