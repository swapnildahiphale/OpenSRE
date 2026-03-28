"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function GitHubSetupContent() {
  const searchParams = useSearchParams();
  const account = searchParams.get("account");
  const action = searchParams.get("action");
  const installationId = searchParams.get("installation_id");

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50 dark:bg-stone-800">
      <div className="max-w-md w-full bg-white dark:bg-stone-700 rounded-lg shadow-lg p-8 text-center">
        <div className="mb-6">
          <div className="w-16 h-16 mx-auto bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
            <svg
              className="w-8 h-8 text-green-600 dark:text-green-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        </div>

        <h1 className="text-2xl font-bold text-stone-900 dark:text-white mb-2">
          GitHub App {action === "install" ? "Installed" : "Updated"}!
        </h1>

        {account && (
          <p className="text-stone-600 dark:text-stone-300 mb-6">
            Successfully {action === "install" ? "installed on" : "updated for"}{" "}
            <span className="font-semibold text-stone-900 dark:text-white">
              {account}
            </span>
          </p>
        )}

        <div className="bg-forest-light/10 dark:bg-forest/20 rounded-lg p-4 mb-6">
          <p className="text-forest-dark dark:text-forest-light text-sm">
            <strong>Next step:</strong> Return to Slack and enter{" "}
            <code className="bg-forest-light/15 dark:bg-forest/20 px-1 rounded">
              {account || "your GitHub org name"}
            </code>{" "}
            in the GitHub configuration modal to complete the setup.
          </p>
        </div>

        <div className="text-sm text-stone-500 dark:text-stone-400">
          <p>Installation ID: {installationId || "N/A"}</p>
        </div>

        <div className="mt-8 pt-6 border-t border-stone-200 dark:border-stone-600">
          <p className="text-xs text-stone-400 dark:text-stone-500">
            You can close this window and return to Slack.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function GitHubSetupPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-stone-900" />
        </div>
      }
    >
      <GitHubSetupContent />
    </Suspense>
  );
}
