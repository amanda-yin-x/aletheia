"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";

const TURNSTILE_SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

declare global {
  interface Window {
    turnstile?: {
      render: (element: HTMLElement, options: Record<string, unknown>) => string;
      remove: (widgetId: string) => void;
      reset: (widgetId: string) => void;
    };
  }
}

export function TurnstileWidget({ siteKey, action, onToken }: { siteKey: string; action: string; onToken: (token: string | null) => void }) {
  const elementRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<string | null>(null);
  const mountedRef = useRef(false);
  const generationRef = useRef(0);
  const [status, setStatus] = useState<"loading" | "waiting" | "verified" | "expired" | "timeout" | "error">("loading");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [renderAttempt, setRenderAttempt] = useState(0);
  const [scriptAttempt, setScriptAttempt] = useState(0);

  const disposeWidget = useCallback(() => {
    const widgetId = widgetRef.current;
    widgetRef.current = null;
    if (!widgetId || !window.turnstile) return;
    try {
      window.turnstile.reset(widgetId);
    } catch {
      // The challenge may already have been invalidated by the provider.
    }
    try {
      window.turnstile.remove(widgetId);
    } catch {
      // Removal is best-effort during retry and React unmount.
    }
  }, []);

  const reportFailure = useCallback((nextStatus: "expired" | "timeout" | "error", code?: string) => {
    setStatus(nextStatus);
    setErrorCode(code || null);
    onToken(null);
  }, [onToken]);

  const renderWidget = useCallback(() => {
    if (!mountedRef.current || !elementRef.current || !window.turnstile || widgetRef.current) return;
    const generation = generationRef.current;
    try {
      widgetRef.current = window.turnstile.render(elementRef.current, {
        sitekey: siteKey,
        action,
        theme: "light",
        size: "flexible",
        appearance: "always",
        callback: (token: string) => {
          if (!mountedRef.current || generation !== generationRef.current) return;
          setStatus("verified");
          setErrorCode(null);
          onToken(token);
        },
        "expired-callback": () => {
          if (mountedRef.current && generation === generationRef.current) reportFailure("expired");
        },
        "timeout-callback": () => {
          if (mountedRef.current && generation === generationRef.current) reportFailure("timeout");
        },
        "error-callback": (code?: string) => {
          if (mountedRef.current && generation === generationRef.current) reportFailure("error", code);
          return true;
        },
      });
      setStatus("waiting");
      setErrorCode(null);
    } catch (error) {
      console.warn(
        "[Aletheia Turnstile] Widget render failed:",
        error instanceof Error ? error.message : "unknown error",
      );
      reportFailure("error");
    }
  }, [action, onToken, reportFailure, siteKey]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
      disposeWidget();
    };
  }, [disposeWidget]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(renderWidget);
    return () => window.cancelAnimationFrame(frame);
  }, [renderAttempt, renderWidget]);

  const retryVerification = useCallback(() => {
    const apiLoaded = Boolean(window.turnstile);
    generationRef.current += 1;
    disposeWidget();
    onToken(null);
    setStatus("loading");
    setErrorCode(null);
    setRenderAttempt((value) => value + 1);
    if (!apiLoaded) setScriptAttempt((value) => value + 1);
  }, [disposeWidget, onToken]);

  const errorMessage = errorCode?.startsWith("110")
    ? "Verification is temporarily misconfigured. Please try again shortly."
    : errorCode?.startsWith("200")
      ? "Verification was blocked by this browser or network. Check content blockers and try again."
      : errorCode && (/^(300|600)/).test(errorCode)
        ? "This browser could not complete the security check. Refresh or try a private window."
        : "Verification could not load. Check your connection and try again.";
  const statusMessage = {
    loading: "Loading verification…",
    waiting: "Complete the verification to continue.",
    verified: "Verification complete.",
    expired: "Verification expired. Try again.",
    timeout: "Verification timed out. Try again.",
    error: errorMessage,
  }[status];
  const isError = status === "expired" || status === "timeout" || status === "error";
  const scriptUrl = scriptAttempt === 0 ? TURNSTILE_SCRIPT_URL : `${TURNSTILE_SCRIPT_URL}&retry=${scriptAttempt}`;

  return (
    <div className="turnstile-wrap" data-state={status}>
      <Script
        key={scriptAttempt}
        src={scriptUrl}
        strategy="afterInteractive"
        onLoad={renderWidget}
        onReady={renderWidget}
        onError={() => reportFailure("error")}
      />
      <div ref={elementRef} aria-label="Bot verification" />
      <p className="turnstile-status" role={isError ? "alert" : "status"} aria-live="polite">{statusMessage}</p>
      {isError && <button className="button button-secondary" type="button" onClick={retryVerification}>Retry verification</button>}
    </div>
  );
}
