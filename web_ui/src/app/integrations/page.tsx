import Link from "next/link";

export default function IntegrationsPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-4">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Integrations</h1>
      <p className="text-stone-600 dark:text-stone-300">
        This area was part of the original demo. We’ll reintroduce it once integrations are backed by real config schema and
        service endpoints.
      </p>
      <p className="text-sm text-stone-500">
        For now, configure your agent behavior via <Link className="underline" href="/configuration">Team Configuration</Link>.
      </p>
    </div>
  );
}


