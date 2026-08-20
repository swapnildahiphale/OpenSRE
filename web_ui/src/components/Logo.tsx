import Image from 'next/image';

/** Admin sidebar wordmark — asset includes text; no duplicate label beside it. */
export const LogoFull = () => (
  <div className="relative flex h-full w-full items-center">
    <Image
      src="/brand/opensre-wordmark.png"
      alt="OpenSRE"
      width={1584}
      height={440}
      className="h-7 w-auto max-w-[180px] object-contain object-left"
    />
  </div>
);
