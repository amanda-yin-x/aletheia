"use client";

import { FormEvent, useCallback, useMemo, useState } from "react";
import { ArrowRight, Github, KeyRound, Mail, ShieldCheck } from "lucide-react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type { SupabasePublicConfig } from "@/lib/supabase/config";
import { TurnstileWidget } from "@/components/turnstile-widget";

export function LoginForm({ config, nextPath, initialError }: { config: SupabasePublicConfig; nextPath: string; initialError?: string | null }) {
  const supabase = useMemo(() => createSupabaseBrowserClient(config), [config]);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [captchaVersion, setCaptchaVersion] = useState(0);
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState<"email" | "otp" | "github" | null>(null);
  const [message, setMessage] = useState<string | null>(initialError || null);
  const onTurnstileToken = useCallback((token: string | null) => setCaptchaToken(token), []);
  const callbackUrl = `${config.siteUrl}/auth/callback?next=${encodeURIComponent(nextPath)}`;

  async function sendEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (config.turnstileSiteKey && !captchaToken) {
      setMessage("Complete the verification before requesting a sign-in link.");
      return;
    }
    setPending("email");
    setMessage(null);
    try {
      const { error } = await supabase.auth.signInWithOtp({
        email: email.trim(),
        options: {
          emailRedirectTo: callbackUrl,
          shouldCreateUser: true,
          ...(captchaToken ? { captchaToken } : {}),
        },
      });
      if (error) {
        setMessage(error.message);
        return;
      }
      setSent(true);
      setMessage("Check your email for a secure link or enter the one-time code below.");
    } catch {
      setMessage("The sign-in request could not be sent. Please try again.");
    } finally {
      // Turnstile tokens are single-use, including failed auth attempts.
      setCaptchaToken(null);
      setCaptchaVersion((value) => value + 1);
      setPending(null);
    }
  }

  async function verifyCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending("otp");
    setMessage(null);
    const { error } = await supabase.auth.verifyOtp({ email: email.trim(), token: otp.trim(), type: "email" });
    setPending(null);
    if (error) {
      setMessage(error.message);
      return;
    }
    window.location.assign(nextPath);
  }

  async function signInWithGitHub() {
    setPending("github");
    setMessage(null);
    const { error } = await supabase.auth.signInWithOAuth({ provider: "github", options: { redirectTo: callbackUrl } });
    if (error) {
      setPending(null);
      setMessage(error.message);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <div className="auth-brand"><span><ShieldCheck size={20} /></span>Aletheia</div>
        <p className="eyebrow">Protected policy workspace</p>
        <h1 id="login-title">Sign in to open the release gate.</h1>
        <p className="auth-lede">Review source evidence, compile guardrails, and run the Northstar release scenario in your workspace.</p>

        <button className="auth-oauth" type="button" onClick={signInWithGitHub} disabled={pending !== null}>
          <Github size={18} /> {pending === "github" ? "Opening GitHub…" : "Continue with GitHub"}
        </button>
        <div className="auth-divider"><span>or use email</span></div>

        <form onSubmit={sendEmail} className="auth-form">
          <label htmlFor="email">Work email</label>
          <div className="auth-input"><Mail size={17} /><input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></div>
          {config.turnstileSiteKey && <TurnstileWidget key={captchaVersion} siteKey={config.turnstileSiteKey} onToken={onTurnstileToken} />}
          <button className="button button-primary auth-submit" type="submit" disabled={pending !== null}>
            {pending === "email" ? "Sending…" : "Email me a sign-in link"} <ArrowRight size={16} />
          </button>
        </form>

        {sent && (
          <form onSubmit={verifyCode} className="auth-form auth-otp-form">
            <label htmlFor="otp">One-time code</label>
            <div className="auth-input"><KeyRound size={17} /><input id="otp" inputMode="numeric" autoComplete="one-time-code" required minLength={6} value={otp} onChange={(event) => setOtp(event.target.value)} placeholder="6-digit code" /></div>
            <button className="button button-secondary auth-submit" type="submit" disabled={pending !== null}>{pending === "otp" ? "Verifying…" : "Verify code"}</button>
          </form>
        )}
        {message && <p className="auth-message" role="status">{message}</p>}
        <p className="auth-boundary"><ShieldCheck size={14} /> Authentication is handled by Supabase; Aletheia never receives your provider password.</p>
      </section>
    </main>
  );
}
