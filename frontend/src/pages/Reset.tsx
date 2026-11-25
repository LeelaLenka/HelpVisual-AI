import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import AuthLayout from "../components/AuthLayout";
import { Button, ErrorNote, Field } from "../ui";

export default function Reset() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password.length < 8) return setError("Use at least 8 characters for your password.");
    if (password !== confirm) return setError("The two passwords don't match.");
    setBusy(true);
    setError(null);
    try {
      await api.reset(token, password);
      setDone(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout title="Reset link missing" intro="Open the full link from your reset request, or ask for a new one.">
        <Link to="/forgot" className="font-medium text-link hover:underline">Request a new link</Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Set a new password" intro="Choose a password you don't use anywhere else.">
      {done ? (
        <div className="space-y-4">
          <p role="status" className="rounded-md border border-line bg-surface px-3 py-2.5">Your password has been changed.</p>
          <Link to="/login" className="inline-flex h-11 w-full items-center justify-center rounded-md bg-accent font-medium text-white hover:bg-accent-dark">
            Sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-6" noValidate>
          <Field label="New password" type="password" autoComplete="new-password" hint="At least 8 characters."
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <Field label="Confirm new password" type="password" autoComplete="new-password"
            value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <ErrorNote message={error} />
          <Button type="submit" disabled={busy || !password || !confirm} className="h-11 w-full text-[15px]">
            {busy ? "Saving…" : "Set new password"}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
