import Link from "next/link";

export default function IncidentReviewDemoRemoved() {
    return (
    <div className="p-8 max-w-4xl mx-auto space-y-4">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Incident Review</h1>
      <p className="text-stone-600 dark:text-stone-300">
        The previous content here was a static demo post‑mortem. It has been removed as part of the enterprise refactor.
      </p>
      <p className="text-sm text-stone-500">
        Configure your agents via <Link className="underline" href="/configuration">Team Configuration</Link>.
      </p>
        </div>
    );
}


