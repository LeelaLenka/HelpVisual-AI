import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { GuideSummary } from "../types";
import { Button, EmptyState, ErrorNote, PageHeader, Panel, when } from "../ui";

export default function Multilingual() {
  const [guides, setGuides] = useState<GuideSummary[] | null>(null);
  const [languages, setLanguages] = useState<Record<string, string>>({});
  const [source, setSource] = useState("");
  const [language, setLanguage] = useState("hi");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ id: string; title: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.listGuides().then(setGuides).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    api.languages().then(setLanguages).catch(() => undefined);
  }, []);

  const originals = useMemo(() => (guides ?? []).filter((g) => !g.source_guide_id && g.status === "ready"), [guides]);
  const translations = useMemo(() => (guides ?? []).filter((g) => g.source_guide_id), [guides]);
  const titleOf = (id: string | null) => (guides ?? []).find((g) => g.id === id)?.title ?? "A deleted guide";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const guide = await api.translate(source, language);
      setDone({ id: guide.id, title: guide.title });
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const targets = Object.entries(languages).filter(([code]) => code !== "en");

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Studio"         title="Multilingual Studio"
        intro="Translate a finished guide. The steps keep their order and their pictures; only the words change."
      />
      <ErrorNote message={error} />

      <Panel className="p-5">
        {originals.length === 0 && guides !== null ? (
          <p className="text-ink-soft">
            No guide is ready to translate. Generate a guide's pictures first, then come back here.
          </p>
        ) : (
          <form onSubmit={submit} className="flex flex-wrap items-end gap-4">
            <label className="min-w-[260px] flex-1">
              <span className="mb-1 block font-medium">Guide</span>
              <select value={source} onChange={(e) => setSource(e.target.value)} required
                className="h-9 w-full rounded-md border border-line px-2">
                <option value="">Choose a guide…</option>
                {originals.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
              </select>
            </label>
            <label>
              <span className="mb-1 block font-medium">Language</span>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}
                className="h-9 rounded-md border border-line px-2">
                {targets.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
            </label>
            <Button type="submit" disabled={busy || !source}>{busy ? "Translating…" : "Translate"}</Button>
          </form>
        )}
        <div className="mt-4 space-y-1 text-xs text-ink-soft">
          <p>Takes about a minute on the Kaggle server. The translation is checked: if a step is dropped, merged or renamed, it is corrected once or not saved.</p>
          <p>Button and screen names stay in English, because the app's own translated labels are unknown. This is machine translation: have a speaker review it before approving.</p>
        </div>
        {done && (
          <p role="status" className="mt-4 rounded-md border border-line bg-surface px-3 py-2">
            Saved as <Link to={`/app/guides/${done.id}`} className="font-medium text-link hover:underline">{done.title}</Link>.
          </p>
        )}
      </Panel>

      {guides && translations.length === 0 && (
        <EmptyState title="No translations yet">Translations you make appear here, with the guide they came from.</EmptyState>
      )}
      {translations.length > 0 && (
        <Panel className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left">
            <thead className="border-b border-line text-xs text-ink-soft">
              <tr>
                <th className="px-4 py-3 font-medium">Translation</th>
                <th className="px-4 py-3 font-medium">Language</th>
                <th className="px-4 py-3 font-medium">From</th>
                <th className="px-4 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {translations.map((g) => (
                <tr key={g.id}>
                  <td className="px-4 py-3" lang={g.language}>
                    <Link to={`/app/guides/${g.id}`} className="font-medium hover:text-link hover:underline">{g.title}</Link>
                  </td>
                  <td className="px-4 py-3">{languages[g.language] ?? g.language}</td>
                  <td className="px-4 py-3 text-ink-soft">{titleOf(g.source_guide_id)}</td>
                  <td className="px-4 py-3 text-ink-soft">{when(g.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
