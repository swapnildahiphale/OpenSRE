'use client';

import Link from 'next/link';

export default function IncidentReviewIndex() {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-4">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Incident Review</h1>
      <p className="text-stone-600 dark:text-stone-300">
        This area was part of the original demo (hardcoded post-mortems, chat, export). We’ll reintroduce this once it is
        backed by real incident data + audit logs.
      </p>
      <p className="text-sm text-stone-500">
        For now, manage live agent config via <Link className="underline" href="/configuration">Team Configuration</Link>.
      </p>
    </div>
  );
}

