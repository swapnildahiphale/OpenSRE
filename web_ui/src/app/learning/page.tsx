import Link from "next/link";

export default function LearningPage() {
    return (
    <div className="p-8 max-w-4xl mx-auto space-y-4">
      <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Learning</h1>
      <p className="text-stone-600 dark:text-stone-300">
        This page was demo-only. In the enterprise product, learning will be driven by real incident data, evaluations, and
        change-control workflows.
      </p>
      <p className="text-sm text-stone-500">
        Use <Link className="underline" href="/configuration">Team Configuration</Link> to manage live agent config today.
      </p>
        </div>
    );
}


