import Link from "next/link";

export default function IncidentsPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-4">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Incidents</h1>
      <p className="text-stone-600 dark:text-stone-300">
        This screen was demo-only and used hardcoded incidents. For the enterprise product we’ll back this with your real
        incident source (PagerDuty/Jira/ServiceNow/etc) and audit-grade storage.
      </p>
      <p className="text-sm text-stone-500">
        For now, manage live agent config via <Link className="underline" href="/configuration">Team Configuration</Link>.
      </p>
    </div>
  );
}
