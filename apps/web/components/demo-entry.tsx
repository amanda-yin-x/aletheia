"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Check, ShieldCheck, Sparkles } from "lucide-react";
import { api, RequestError } from "@/lib/api";
import type { BootstrapResult, Project } from "@/lib/types";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type { SupabasePublicConfig } from "@/lib/supabase/config";
import { TurnstileWidget } from "@/components/turnstile-widget";
import { ErrorState, PageLoading } from "@/components/ui";
import { BrandLockup } from "@/components/brand-lockup";

type BootstrapCompatibility = BootstrapResult | Project | { project?: Project; project_id?: string };

function projectIdFromBootstrap(value: BootstrapCompatibility): string | null {
  if ("project" in value && value.project?.id) return value.project.id;
  if ("project_id" in value && value.project_id) return value.project_id;
  if ("slug" in value && value.id) return value.id;
  return null;
}

export function DemoEntry({ config, initialHasSession }: { config: SupabasePublicConfig | null; initialHasSession: boolean }) {
  const router = useRouter();
  const supabase = useMemo(() => config ? createSupabaseBrowserClient(config) : null, [config]);
  const started = useRef(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [sessionReady, setSessionReady] = useState(initialHasSession);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaVersion, setCaptchaVersion] = useState(0);
  const [guestPending, setGuestPending] = useState(false);
  const [guestError, setGuestError] = useState<string | null>(null);
  const [waking, setWaking] = useState(false);
  const onTurnstileToken = useCallback((token: string | null) => setCaptchaToken(token), []);
  const bootstrap = useMutation({
    mutationFn: async () => {
      const value = await api<BootstrapCompatibility>("/api/v1/workspaces/bootstrap", {
        method: "POST",
        body: JSON.stringify({ name: "My workspace" }),
        retryMutation: true,
        coldStartRetries: 20,
        coldStartTimeoutMs: 85_000,
        onRetry: () => setWaking(true),
        idempotencyKey: idempotencyKey.current,
      });
      const projectId = projectIdFromBootstrap(value);
      if (!projectId) throw new Error("The workspace opened without a project identifier.");
      return projectId;
    },
    onMutate: () => setWaking(false),
    onSuccess: (projectId) => router.replace(`/projects/${projectId}/overview`),
    onError: (error) => {
      if (error instanceof RequestError && error.status === 401) {
        void supabase?.auth.signOut({ scope: "local" });
        started.current = false;
        setSessionReady(false);
        setGuestError("Your guest session ended. Verify once more to open a fresh workspace.");
      }
    },
  });

  useEffect(() => {
    if (!sessionReady || started.current) return;
    started.current = true;
    bootstrap.mutate();
  }, [bootstrap, sessionReady]);

  async function startGuestDemo() {
    if (!supabase) {
      setGuestError("The hosted guest workspace is not configured yet. Please try again shortly.");
      return;
    }
    if (config?.turnstileSiteKey && !captchaToken) {
      setGuestError("Complete the verification before opening the demo.");
      return;
    }

    setGuestPending(true);
    setGuestError(null);
    try {
      const { data, error } = await supabase.auth.signInAnonymously({
        options: captchaToken ? { captchaToken } : undefined,
      });
      if (error) throw error;
      if (!data.session) throw new Error("The guest session could not be created.");
      idempotencyKey.current = crypto.randomUUID();
      bootstrap.reset();
      started.current = false;
      setSessionReady(true);
    } catch (error) {
      setGuestError(error instanceof Error ? error.message : "The guest workspace could not be opened. Please try again.");
    } finally {
      // CAPTCHA responses are single-use, including rejected sign-in attempts.
      setCaptchaToken(null);
      setCaptchaVersion((value) => value + 1);
      setGuestPending(false);
    }
  }

  if (!sessionReady) {
    return (
      <main className="guest-demo-page">
        <section className="guest-demo-gate" aria-labelledby="guest-demo-title">
          <BrandLockup className="guest-demo-brand" size="large" />
          <div className="guest-demo-badge"><Sparkles size={15} aria-hidden="true" /> No account needed</div>
          <p className="eyebrow">Interactive Northstar workspace</p>
          <h1 id="guest-demo-title">Run the complete policy release path.</h1>
          <p>Open a temporary private workspace with the source review, conflict resolution, compiled guards, 16-case comparison run, traces, and evidence report ready to inspect.</p>
          <ul className="guest-demo-facts" aria-label="Guest demo details">
            <li><Check size={16} aria-hidden="true" /> Isolated guest workspace</li>
            <li><Check size={16} aria-hidden="true" /> No customer data</li>
            <li><Check size={16} aria-hidden="true" /> No signup or password</li>
          </ul>
          {config?.turnstileSiteKey && (
            <TurnstileWidget key={captchaVersion} siteKey={config.turnstileSiteKey} action="guest_demo" onToken={onTurnstileToken} />
          )}
          <button
            className="button button-primary guest-demo-start"
            type="button"
            onClick={startGuestDemo}
            disabled={guestPending || Boolean(config?.turnstileSiteKey && !captchaToken)}
          >
            {guestPending ? "Opening workspace…" : "Open guest workspace"} <ArrowRight size={16} aria-hidden="true" />
          </button>
          {guestError && <p className="guest-demo-error" role="alert">{guestError}</p>}
          <p className="guest-demo-privacy"><ShieldCheck size={14} aria-hidden="true" /> Verification limits automated abuse. The guest identity is temporary and is not a marketing signup.</p>
          <Link className="guest-demo-login" href="/login?next=%2Fdemo">Want a persistent personal Northstar workspace? Sign in instead.</Link>
        </section>
      </main>
    );
  }

  if (bootstrap.error) {
    return <main className="landing"><ErrorState error={bootstrap.error} onRetry={() => { setWaking(false); idempotencyKey.current = crypto.randomUUID(); bootstrap.reset(); bootstrap.mutate(); }} /></main>;
  }
  return <main className="landing"><PageLoading
    label={waking ? "Waking your workspace…" : "Preparing your Northstar policy workspace"}
    detail={waking ? "The hosted API is starting. Preview wake-up can take about a minute." : "Creating or reopening your isolated workspace…"}
  /></main>;
}
