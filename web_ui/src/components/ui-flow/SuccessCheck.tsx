/**
 * Small filled success tick matching `web_ui/design/team-investigation-detail-mockup.html`
 * (Phosphor Check path). Prefer this over Lucide Check/CheckCircle — stroke icons read
 * much heavier at the same box size.
 */
export function SuccessCheck({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 256 256"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M173.66,98.34a8,8,0,0,1,0,11.32l-56,56a8,8,0,0,1-11.32,0l-24-24a8,8,0,0,1,11.32-11.32L112,148.69l50.34-50.35A8,8,0,0,1,173.66,98.34Z" />
    </svg>
  );
}
