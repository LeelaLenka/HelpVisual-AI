import { Search, Trash2 } from "lucide-react";
import { Fragment, useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import type { KbDocument, KbPassage } from "../types";
import { Button, EmptyState, ErrorNote, PageHeader, Panel, quietButton, when } from "../ui";

/** Wraps the words of the query that appear in a passage, so a reviewer sees why it matched. */
function Highlighted({ text, query }: { text: string; query: string }) {
  const terms = query.toLowerCase().match(/[a-z0-9]{3,}/g) ?? [];
  if (terms.length === 0) return <>{text}</>;
  const pattern = new RegExp(`\\b(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return (
    <>
      {text.split(pattern).map((part, i) =>
        i % 2 === 1 ? <mark key={i} className="rounded bg-mark-soft px-0.5 text-ink">{part}</mark> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

export default function KnowledgeBase() {
  const [docs, setDocs] = useState<KbDocument[] | null>(null);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState("");
  const [hits, setHits] = useState<KbPassage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.kbList().then(setDocs).catch((e) => setError(e.message));
  }, []);

  async function add(event: FormEvent) {
    event.preventDefault();
    setAdding(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("title", title);
      if (file) form.append("file", file);
      else form.append("text", text);
      const doc = await api.kbAdd(form);
      setDocs((list) => [doc, ...(list ?? [])]);
      setTitle("");
      setText("");
      setFile(null);
      (event.target as HTMLFormElement).reset();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    try {
      setHits(await api.kbSearch(query));
      setSearched(query);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove(doc: KbDocument) {
    if (!window.confirm(`Remove "${doc.title}" from the knowledge base?`)) return;
    try {
      await api.kbDelete(doc.id);
      setDocs((list) => (list ?? []).filter((d) => d.id !== doc.id));
      setHits(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Quality and publishing"         title="Knowledge Base"
        intro="Support documents the assistant may quote when customers ask questions a guide does not answer. Answers name the document they used."
      />
      <ErrorNote message={error} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel className="p-5">
          <h2 className="font-semibold">Add a document</h2>
          <form onSubmit={add} className="mt-4 space-y-3">
            <label className="block">
              <span className="mb-1 block font-medium">Title</span>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Billing FAQ"
                className="h-9 w-full rounded-md border border-line px-3 outline-none focus:border-accent" />
            </label>
            <label className="block">
              <span className="mb-1 block font-medium">Text</span>
              <textarea value={text} onChange={(e) => setText(e.target.value)} disabled={!!file} rows={6}
                placeholder="Paste a policy, FAQ or support article…"
                className="w-full rounded-md border border-line px-3 py-2 outline-none focus:border-accent disabled:opacity-60" />
            </label>
            <div className="flex flex-wrap items-center gap-3 text-ink-soft">
              <span>or upload</span>
              <input type="file" accept=".txt,.md,.pdf,.docx" aria-label="Upload a document"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="text-sm file:mr-3 file:h-8 file:rounded-md file:border file:border-line file:bg-paper file:px-3 file:text-ink" />
            </div>
            <Button type="submit" disabled={adding || (!file && text.trim().split(/\s+/).length < 10)}>
              {adding ? "Adding…" : "Add document"}
            </Button>
          </form>
        </Panel>

        <Panel className="p-5">
          <h2 className="font-semibold">Test a question</h2>
          <p className="mt-1 text-sm text-ink-soft">
            See which passages the assistant would read. Search matches words, not meanings: “sign in” does not find “log in”.
          </p>
          <form onSubmit={search} className="mt-4 flex gap-2">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="How long does a refund take?"
              aria-label="Question" className="h-9 min-w-0 flex-1 rounded-md border border-line px-3 outline-none focus:border-accent" />
            <Button type="submit" disabled={!query.trim()}><Search size={15} aria-hidden="true" className="mr-1.5" />Search</Button>
          </form>
          {hits && (
            <ol className="mt-4 space-y-3" aria-live="polite">
              {hits.length === 0 && <li className="text-ink-soft">No passage contains those words.</li>}
              {hits.map((h, i) => (
                <li key={i} className="rounded-md border border-line p-3">
                  <div className="flex items-baseline justify-between gap-3 text-xs text-ink-soft">
                    <span className="font-medium text-ink">{h.title}</span>
                    <span className="tabular-nums">score {h.score.toFixed(2)}</span>
                  </div>
                  <p className="mt-1.5 line-clamp-4 text-sm"><Highlighted text={h.text} query={searched} /></p>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      </div>

      {docs && docs.length === 0 && (
        <EmptyState title="No documents yet">
          Add your FAQs and policies. The assistant then answers questions such as refund times or opening hours from them,
          and still refuses when nothing covers the question.
        </EmptyState>
      )}
      {docs && docs.length > 0 && (
        <Panel className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left">
            <thead className="border-b border-line text-xs text-ink-soft">
              <tr>
                <th className="px-4 py-3 font-medium">Document</th>
                <th className="px-4 py-3 text-right font-medium">Words</th>
                <th className="px-4 py-3 text-right font-medium">Passages</th>
                <th className="px-4 py-3 font-medium">Added</th>
                <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {docs.map((d) => (
                <tr key={d.id}>
                  <td className="px-4 py-3 font-medium">{d.title}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{d.words.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{d.passages}</td>
                  <td className="px-4 py-3 text-ink-soft">{when(d.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => remove(d)} className={quietButton} aria-label={`Remove ${d.title}`}>
                      <Trash2 size={15} aria-hidden="true" />Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
