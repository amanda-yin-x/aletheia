"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";

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
  const [status, setStatus] = useState<"loading" | "waiting" | "verified" | "expired" | "timeout" | "error">("loading");

  const renderWidget = useCallback(() => {
    if (!mountedRef.current || !elementRef.current || !window.turnstile || widgetRef.current) return;
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
      "expired-callback": () => {
        setStatus("expired");
        onToken(null);
      },
      "timeout-callback": () => {
        setStatus("timeout");
        onToken(null);
      },
      "error-callback": () => {
        setStatus("error");
        onToken(null);
      },
    });
    setStatus("waiting");
  }, [action, onToken, siteKey]);

  const queueRender = useCallback(() => {
    if (!mountedRef.current || !window.turnstile || widgetRef.current || readyQueuedRef.current) return;
    readyQueuedRef.current = true;
    window.turnstile.ready(() => {
      readyQueuedRef.current = false;
      renderWidget();
    });
  }, [renderWidget]);

  useEffect(() => {
    mountedRef.current = true;
    queueRender();
    return () => {
      mountedRef.current = false;
      readyQueuedRef.current = false;
      if (widgetRef.current && window.turnstile) {
        try {
          window.turnstile.reset(widgetRef.current);
        } catch {
          // The challenge may already have been invalidated by the provider.
        }
        try {
          window.turnstile.remove(widgetRef.current);
        } catch {
          // Removal is best-effort during React unmount.
        }
      }
      widgetRef.current = null;
    };
  }, [queueRender]);

  const statusMessage = {
    loading: "Loading verification…",
    waiting: "Complete the verification to continue.",
    verified: "Verification complete.",
    expired: "Verification expired. Try again.",
    timeout: "Verification timed out. Try again.",
    error: "Verification could not load. Check your connection and try again.",
  }[status];
  const isError = status === "expired" || status === "timeout" || status === "error";

  return (
    <div className="turnstile-wrap" data-state={status}>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        strategy="afterInteractive"
        onLoad={queueRender}
        onReady={queueRender}
        onError={() => setStatus("error")}
      />
      <div ref={elementRef} aria-label="Bot verification" />
      <p className="turnstile-status" role={isError ? "alert" : "status"} aria-live="polite">{statusMessage}</p>
    </div>
  );
}
