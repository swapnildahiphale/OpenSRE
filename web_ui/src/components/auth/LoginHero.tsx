import Link from 'next/link';
import { OpenSreBrandLogo } from '@/components/brand/OpenSreBrandLogo';
import styles from './LoginHero.module.css';

const ROTATING_WORDS = [
  'investigator.',
  'first responder.',
  'debugger.',
  'troubleshooter.',
] as const;

/** Marketing left pane — opensre.in hero copy + word slider (login mockup Option C). */
export function LoginHero() {
  return (
    <div
      className="relative flex flex-col justify-center min-h-[50vh] lg:min-h-screen px-10 py-16 lg:px-16 xl:px-20 border-b lg:border-b-0 lg:border-r border-slate-200/60"
      style={{
        background:
          'linear-gradient(165deg, rgb(209 250 229 / 0.7) 0%, #f9fafb 45%, white 100%)',
      }}
    >
      <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <div
        className="absolute top-0 right-0 w-[480px] h-[480px] rounded-full breath"
        style={{
          background: 'rgb(16 185 129 / 0.15)',
          filter: 'blur(80px)',
          transform: 'translate(30%, -20%)',
        }}
      />
      <div
        className="absolute bottom-0 left-0 w-64 h-64 rounded-full opacity-40"
        style={{ background: 'rgb(16 185 129 / 0.1)', filter: 'blur(60px)' }}
      />
      </div>

      <div className="relative w-full max-w-xl flex flex-col items-start gap-8">
        <Link href="https://opensre.in" aria-label="OpenSRE">
          <OpenSreBrandLogo variant="wordmark" surface="login" priority />
        </Link>

        <div className={styles.copy}>
          <h1 className={styles.headline}>
            <span className={styles.headlineLine}>Your incidents</span>
            <span className={styles.headlineLine}>deserve a better</span>
            <span className={`${styles.headlineLine} ${styles.container} text-emerald-800`}>
              <span className={styles.list}>
                {ROTATING_WORDS.map((word) => (
                  <span key={word}>{word}</span>
                ))}
                <span aria-hidden="true">{ROTATING_WORDS[0]}</span>
              </span>
            </span>
          </h1>

          <p className="text-slate-600 text-lg leading-relaxed max-w-md">
            An AI SRE that autonomously investigates production incidents,
            remembers every past investigation, and maps your entire service
            topology.
          </p>

          <a
            href="https://opensre.in"
            className="text-sm text-emerald-700 hover:text-emerald-900 font-mono transition-colors"
          >
            Learn more at opensre.in →
          </a>
        </div>
      </div>
    </div>
  );
}
