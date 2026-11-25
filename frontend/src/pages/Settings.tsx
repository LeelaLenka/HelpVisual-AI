import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api } from "../api";
import ProviderPanel from "../components/ProviderPanel";
import { useAuth } from "../auth";
import { LogoMark } from "../components/Logo";
import { ThemeSwitch } from "../theme";
import type { Health } from "../types";
import { Button, ErrorNote, Field, Panel, PageHeader } from "../ui";

function Card({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <Panel className="grid gap-6 p-6 md:grid-cols-[240px_minmax(0,1fr)]">
      <div>
        <h2 className="font-semibold">{title}</h2>
        {intro && <p className="mt-1 text-sm text-ink-soft">{intro}</p>}
      </div>
      <div className="max-w-lg space-y-4">{children}</div>
    </Panel>
  );
}

function Saved({ text }: { text: string | null }) {
  return text ? <p role="status" className="text-sm text-good">{text}</p> : null;
}

export default function Settings() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.name ?? "");
  const [profileMsg, setProfileMsg] = useState<string | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [passwordMsg, setPasswordMsg] = useState<string | null>(null);
  const [brandName, setBrandName] = useState(user?.brand_name ?? "");
  const [brandColor, setBrandColor] = useState(user?.brand_color ?? "#13716e");
  const [brandMsg, setBrandMsg] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const run = async (action: () => Promise<void>) => {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const saveProfile = (e: FormEvent) => {
    e.preventDefault();
    run(async () => { setUser(await api.updateProfile(name)); setProfileMsg("Profile saved."); });
  };
  const savePassword = (e: FormEvent) => {
    e.preventDefault();
    if (next.length < 8) return setError("Use at least 8 characters for the new password.");
    run(async () => { await api.changePassword(current, next); setCurrent(""); setNext(""); setPasswordMsg("Password changed."); });
  };
  const saveBrand = (e: FormEvent) => {
    e.preventDefault();
    run(async () => { setUser(await api.updateBranding(brandName, brandColor)); setBrandMsg("Branding saved."); });
  };

  if (!user) return null;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Account" title="Settings" intro="Your account, how your guides look to customers, and the AI services this app uses." />
      <ErrorNote message={error} />

      <Card title="Profile" intro="Shown in the sidebar.">
        <form onSubmit={saveProfile} className="space-y-4">
          <Field label="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <Field label="Email" value={user.email} disabled hint="Your sign-in email cannot be changed here." />
          <div className="flex items-center gap-3"><Button type="submit" disabled={!name.trim()}>Save profile</Button><Saved text={profileMsg} /></div>
        </form>
      </Card>

      <Card title="Password" intro="You stay signed in on this device after changing it.">
        <form onSubmit={savePassword} className="space-y-4">
          <Field label="Current password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          <Field label="New password" type="password" autoComplete="new-password" hint="At least 8 characters." value={next} onChange={(e) => setNext(e.target.value)} />
          <div className="flex items-center gap-3"><Button type="submit" disabled={!current || !next}>Change password</Button><Saved text={passwordMsg} /></div>
        </form>
      </Card>

      <Card title="Branding" intro="Customers see this at the top of your published guides.">
        <form onSubmit={saveBrand} className="space-y-4">
          <Field label="Brand name" placeholder="MyBank" value={brandName} onChange={(e) => setBrandName(e.target.value)} />
          <div>
            <label htmlFor="brand-color" className="mb-1.5 block font-medium">Brand colour</label>
            <div className="flex items-center gap-3">
              <input id="brand-color" type="color" value={brandColor} onChange={(e) => setBrandColor(e.target.value)}
                className="h-10 w-14 cursor-pointer rounded-md border border-line p-1" />
              <code className="text-sm text-ink-soft">{brandColor}</code>
            </div>
          </div>
          <div>
            <p className="mb-1.5 font-medium">Logo</p>
            <div className="flex flex-wrap items-center gap-3">
              {user.logo_url ? <img src={user.logo_url} alt="Your logo" className="h-10 max-w-[160px] rounded border border-line object-contain p-1" /> : <span className="text-sm text-ink-soft">No logo</span>}
              <input ref={fileInput} type="file" accept="image/png,image/jpeg" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) run(async () => setUser(await api.uploadLogo(f))); }} />
              <Button type="button" variant="secondary" onClick={() => fileInput.current?.click()}>Upload logo</Button>
              {user.logo_url && <Button type="button" variant="danger" onClick={() => run(async () => setUser(await api.removeLogo()))}>Remove</Button>}
            </div>
            <p className="mt-1 text-xs text-ink-soft">PNG or JPEG, up to 1 MB.</p>
          </div>
          <div>
            <p className="mb-1.5 font-medium">Preview</p>
            <div className="flex h-14 items-center gap-3 rounded-md border border-line bg-paper px-4" style={{ borderTop: `3px solid ${brandColor}` }}>
              {user.logo_url ? <img src={user.logo_url} alt="" className="h-8 max-w-[120px] object-contain" /> : <LogoMark size={24} />}
              <span className="font-semibold">{brandName || "HelpVisual AI"}</span>
            </div>
          </div>
          <div className="flex items-center gap-3"><Button type="submit">Save branding</Button><Saved text={brandMsg} /></div>
        </form>
      </Card>

      <Card title="Appearance" intro="Light, dark, or follow your device.">
        <div className="max-w-xs"><ThemeSwitch /></div>
      </Card>

      <ProviderPanel />

      <Card title="AI server" intro="Reading articles, picture checks, translation and SDXL run on your own HelpVisual ML server on Kaggle. Images can also come from Gemini (see Image generation).">
        <dl className="divide-y divide-line rounded-md border border-line">
          {[
            ["Connection", health ? (health.connected ? "Connected" : null) : null],
            ["Language model", health?.llm],
            ["Image generation", health?.image],
            ["Image checks", health ? (health.verifier === "clip+ocr" ? "CLIP and OCR" : health.verifier) : null],
          ].map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-4 px-4 py-2.5">
              <dt className="text-ink-soft">{label}</dt>
              <dd className={`text-right text-sm ${value ? "" : "text-bad"}`}>{value ?? (label === "Connection" ? "Offline" : "Not connected")}</dd>
            </div>
          ))}
        </dl>
        {health && (!health.connected || !health.llm || !health.image) && (
          <p className="text-sm text-ink-soft">
            Start the Kaggle notebook, paste the lines it prints into <code>backend/.env</code>, then restart the backend.
          </p>
        )}
      </Card>
    </div>
  );
}
