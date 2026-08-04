"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";

const TURNSTILE_SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

declare global {
  interface Window {
    turnstile?: {
      ready: (callback: () => void) => void;
      render: (element: HTMLElement, options: Record<string, unknown>) => string;
      remove: (widgetId: string) => void;
      reset: (widgetId: string) => void;
    };
  }
}

export function TurnstileWidget({ siteKey, action, onToken }: { siteKey: string; action: string; onToken: (token: string | null) => void }) {
  const elementRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<string | null>(null);
  const readyQueuedRef = useRef(false);
  const mountedRef = useRef(false);
  const generationRef = useRef(0);
  const [status, setStatus] = useState<"loading" | "waiting" | "verified" | "expired" | "timeout" | "error">("loading");
  const [renderAttempt, setRenderAttempt] = useState(0);
  const [scriptAttempt, setScriptAttempt] = useState(0);

  const disposeWidget = useCallback(() => {
    readyQueuedRef.current = false;
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

  const reportFailure = useCallback((nextStatus: "expired" | "timeout" | "error") => {
    setStatus(nextStatus);
    onToken(null);
  }, [onToken]);

  const renderWidget = useCallback(() => {
    if (!mountedRef.current || !elementRef.current || !window.turnstile || widgetRef.current) return;
    try {
      widgetRef.current = window.turnstile.render(elementRef.current, {
        sitekey: siteKey,
        action,
        theme: "light",
        size: "flexible",
        appearance: "always",
        callback: (token: string) => {
          setStatus("verified");
          onToken(token);
        },
        "expired-callback": () => reportFailure("expired"),
        "timeout-callback": () => reportFailure("timeout"),
        "error-callback": () => reportFailure("error"),
      });
      setStatus("waiting");
    } catch {
      reportFailure("error");
    }
  }, [action, onToken, reportFailure, siteKey]);

  const queueRender = useCallback(() => {
    if (!mountedRef.current || !window.turnstile || widgetRef.current || readyQueuedRef.current) return;
    const generation = generationRef.current;
    readyQueuedRef.current = true;
    try {
      window.turnstile.ready(() => {
        if (!mountedRef.current || generation !== generationRef.current) return;
        readyQueuedRef.current = false;
        renderWidget();
      });
    } catch {
      readyQueuedRef.current = false;
      reportFailure("error");
    }
  }, [renderWidget, reportFailure]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      generationRef.current += 1;
      readyQueuedRef.current = false;
      disposeWidget();
    };
  }, [disposeWidget]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(queueRender);
    return () => window.cancelAnimationFrame(frame);
  }, [queueRender, renderAttempt]);

  const retryVerification = useCallback(() => {
    const apiLoaded = Boolean(window.turnstile);
    generationRef.current += 1;
    disposeWidget();
    onToken(null);
    setStatus("loading");
    setRenderAttempt((value) => value + 1);
    if (!apiLoaded) setScriptAttempt((value) => value + 1);
  }, [disposeWidget, onToken]);

  const statusMessage = {
    loading: "Loading verification…",
    waiting: "Complete the verification to continue.",
    verified: "Verification complete.",
    expired: "Verification expired. Try again.",
    timeout: "Verification timed out. Try again.",
    error: "Verification could not load. Check your connection and try again.",
  }[status];
  const isError = status === "expired" || status === "timeout" || status === "error";
  const scriptUrl = scriptAttempt === 0 ? TURNSTILE_SCRIPT_URL : `${TURNSTILE_SCRIPT_URL}&retry=${scriptAttempt}`;

  return (
    <div className="turnstile-wrap" data-state={status}>
      <Script
        key={scriptAttempt}
        src={scriptUrl}
        strategy="afterInteractive"
        onLoad={queueRender}
        onReady={queueRender}
        onError={() => reportFailure("error")}
      />
      <div ref={elementRef} aria-label="Bot verification" />
      <p className="turnstile-status" role={isError ? "alert" : "status"} aria-live="polite">{statusMessage}</p>
      {isError && <button className="button button-secondary" type="button" onClick={retryVerification}>Retry verification</button>}
    </div>
  );
}
