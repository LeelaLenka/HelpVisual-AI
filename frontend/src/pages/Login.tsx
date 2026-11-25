import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import AuthLayout from "../components/AuthLayout";
import { Button, ErrorNote, Field } from "../ui";

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      const next = params.get("next");
      navigate(next && next.startsWith("/app") ? next : "/app", { replace: true });
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Sign in to HelpVisual"
      intro="Turn help articles into illustrated, verified guides."
      footer={<>New to HelpVisual? <Link to="/register" className="font-medium text-link hover:underline">Create an account</Link></>}
    >
      <form onSubmit={submit} className="space-y-6" noValidate>
        <Field label="Email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aside={<Link to="/forgot" className="text-xs font-medium text-link hover:underline">Forgot password?</Link>}
        />
        <ErrorNote message={error} />
        <Button type="submit" disabled={busy || !email || !password} className="h-11 w-full text-[15px]">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthLayout>
  );
}
