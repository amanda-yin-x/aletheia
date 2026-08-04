"use client";

import { FormEvent, useCallback, useMemo, useRef, useState } from "react";
import { ArrowRight, Check, Mail, ShieldCheck } from "lucide-react";
import { api, RequestError } from "@/lib/api";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type { SupabasePublicConfig } from "@/lib/supabase/config";
import { TurnstileWidget } from "@/components/turnstile-widget";

interface WaitlistResponse {
  joined: boolean;
}

export function WaitlistForm({ config, initialHasSession }: { config: SupabasePublicConfig | null; initialHasSession: boolean }) {
  const supabase = useMemo(() => config ? createSupabaseBrowserClient(config) : null, [config]);
  const idempotencyKey = useRef(crypto.randomUUID());
  const [hasSession, setHasSession] = useState(initialHasSession);
  const [email, setEmail] = useState("");
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaVersion, setCaptchaVersion] = useState(0);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const onTurnstileToken = useCallback((token: string | null) => setCaptchaToken(token), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasSession && config?.turnstileSiteKey && !captchaToken) {
      setMessage("Complete the verification before joining the preview list.");
      return;
    }
    if (!hasSession && !supabase) {
      setMessage("Preview requests are temporarily unavailable because hosted authentication is not configured.");
      return;
    }

    setPending(true);
    setMessage(null);
    setSuccess(false);
    let consumedCaptcha = false;
    try {
      if (!hasSession && supabase) {
        consumedCaptcha = true;
        const { data, error } = await supabase.auth.signInAnonymously({
          options: captchaToken ? { captchaToken } : undefined,
        });
        if (error) throw error;
        if (!data.session) throw new Error("A secure guest session could not be created.");
        setHasSession(true);
      }

      await api<WaitlistResponse>("/api/v1/waitlist", {
        method: "POST",
        body: JSON.stringify({ email: email.trim() }),
        retryMutation: true,
        coldStartRetries: 20,
        coldStartTimeoutMs: 85_000,
        idempotencyKey: idempotencyKey.current,
      });
      setSuccess(true);
      setEmail("");
      setMessage("Request saved. No email has been sent.");
      idempotencyKey.current = crypto.randomUUID();
    } catch (error) {
      if (error instanceof RequestError && error.status === 401 && supabase) {
        await supabase.auth.signOut({ scope: "local" }).catch(() => undefined);
        setHasSession(false);
        setCaptchaToken(null);
        setCaptchaVersion((value) => value + 1);
        setMessage("Your guest session ended. Complete verification once more, then retry.");
        return;
      }
      setMessage(error instanceof Error ? error.message : "The preview request could not be saved. Please try again.");
    } finally {
      if (consumedCaptcha) {
        setCaptchaToken(null);
        setCaptchaVersion((value) => value + 1);
      }
      setPending(false);
    }
  }

  return (
    <section id="waitlist" className="waitlist-section" aria-labelledby="waitlist-title">
      <div className="waitlist-copy">
        <p className="eyebrow">Hosted preview access</p>
        <h2 id="waitlist-title">Bring your own policy workflow next.</h2>
        <p>The public Northstar workspace is ready to explore now. Join the preview list if you want to hear when private uploads and persistent team projects open.</p>
        <ul>
          <li><Check size={16} aria-hidden="true" /> Private source ingestion</li>
          <li><Check size={16} aria-hidden="true" /> Team review and approvals</li>
          <li><Check size={16} aria-hidden="true" /> Hosted regression runs</li>
        </ul>
      </div>
      <form className="waitlist-form" onSubmit={submit} aria-describedby="waitlist-privacy">
        <label htmlFor="waitlist-email">Work email</label>
        <div className="waitlist-input"><Mail size={17} aria-hidden="true" /><input id="waitlist-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></div>
        {!hasSession && config?.turnstileSiteKey && (
          <TurnstileWidget key={captchaVersion} siteKey={config.turnstileSiteKey} action="waitlist" onToken={onTurnstileToken} />
        )}
        <button className="marketing-button marketing-button-primary waitlist-submit" type="submit" disabled={pending || Boolean(!hasSession && config?.turnstileSiteKey && !captchaToken)}>
          {pending ? "Saving request…" : "Request preview access"} <ArrowRight size={16} aria-hidden="true" />
        </button>
        {message && <p className={success ? "waitlist-message is-success" : "waitlist-message is-error"} role={success ? "status" : "alert"}>{success && <ShieldCheck size={15} aria-hidden="true" />}{message}</p>}
        <p id="waitlist-privacy" className="waitlist-privacy">Used only to contact you about hosted preview access. This does not subscribe you to a newsletter.</p>
      </form>
    </section>
  );
}
