import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import AuthLayout from "../components/AuthLayout";
import { Button, ErrorNote, Field } from "../ui";

export default function Forgot() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setSent((await api.forgot(email)).message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Reset your password"
      intro="Enter the email you signed up with and we'll send a link to set a new password."
      footer={<Link to="/login" className="font-medium text-link hover:underline">Back to sign in</Link>}
    >
      {sent ? (
        <div className="space-y-3">
          <p role="status" className="rounded-md border border-line bg-surface px-3 py-2.5">{sent}</p>
          <p className="text-xs text-ink-soft">
            This development version has no email service yet: the link is printed in the backend terminal.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-6" noValidate>
          <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <ErrorNote message={error} />
          <Button type="submit" disabled={busy || !email} className="h-11 w-full text-[15px]">
            {busy ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
