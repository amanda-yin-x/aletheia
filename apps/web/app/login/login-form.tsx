"use client";

import { FormEvent, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Github, KeyRound, Mail, ShieldCheck } from "lucide-react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type { SupabasePublicConfig } from "@/lib/supabase/config";
import { TurnstileWidget } from "@/components/turnstile-widget";

export function LoginForm({ config, nextPath, initialError, hasAnonymousSession }: { config: SupabasePublicConfig; nextPath: string; initialError?: string | null; hasAnonymousSession: boolean }) {
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
  // The anonymous session was CAPTCHA-verified when it was created. Supabase's
  // in-place email-linking API does not accept another CAPTCHA token.
  const requiresCaptcha = Boolean(config.turnstileSiteKey && !hasAnonymousSession);

  async function sendEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (requiresCaptcha && !captchaToken) {
      setMessage("Complete the verification before requesting a sign-in link.");
      return;
    }
    setPending("email");
    setMessage(null);
    try {
      const emailAddress = email.trim();
      const { error } = hasAnonymousSession
        ? await supabase.auth.updateUser(
            { email: emailAddress },
            { emailRedirectTo: callbackUrl },
          )
        : await supabase.auth.signInWithOtp({
            email: emailAddress,
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
      setMessage(config.emailOtpEnabled
        ? "Check your email for a secure link or enter the one-time code below."
        : "Check your email for a secure, single-use sign-in link.");
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
    const { error } = await supabase.auth.verifyOtp({
      email: email.trim(),
      token: otp.trim(),
      type: hasAnonymousSession ? "email_change" : "email",
    });
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
    const credentials = { provider: "github" as const, options: { redirectTo: callbackUrl } };
    const { error } = hasAnonymousSession
      ? await supabase.auth.linkIdentity(credentials)
      : await supabase.auth.signInWithOAuth(credentials);
    if (error) {
      setPending(null);
      setMessage(error.message);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <div className="auth-brand"><span><ShieldCheck size={20} /></span>Aletheia</div>
        <p className="eyebrow">Optional persistent access</p>
        <h1 id="login-title">Keep a workspace across visits.</h1>
        <p className="auth-lede">Sign in for a persistent team identity and workspace. You can also explore the complete Northstar workflow without creating an account.</p>

        <Link className="auth-guest-link" href="/demo">
          <span><strong>Open the no-account demo</strong><small>A temporary guest workspace, ready in the browser.</small></span>
          <ArrowRight size={18} />
        </Link>
        <div className="auth-divider"><span>or keep your workspace</span></div>

        {config.githubAuthEnabled && (
          <>
            <button className="auth-oauth" type="button" onClick={signInWithGitHub} disabled={pending !== null}>
              <Github size={18} /> {pending === "github" ? "Opening GitHub…" : "Continue with GitHub"}
            </button>
            <div className="auth-divider"><span>or use email</span></div>
          </>
        )}

        <form onSubmit={sendEmail} className="auth-form">
          <label htmlFor="email">Work email</label>
          <div className="auth-input"><Mail size={17} /><input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></div>
          {requiresCaptcha && <TurnstileWidget key={captchaVersion} siteKey={config.turnstileSiteKey} action="login" onToken={onTurnstileToken} />}
          <button className="button button-primary auth-submit" type="submit" disabled={pending !== null}>
            {pending === "email" ? "Sending…" : "Email me a sign-in link"} <ArrowRight size={16} />
          </button>
        </form>

        {sent && config.emailOtpEnabled && (
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
