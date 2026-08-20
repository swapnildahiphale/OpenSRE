import Image from 'next/image';

type Variant = 'wordmark' | 'spinner';
// avatar = chat bubble icon (investigation transcript)
type Surface = 'topbar' | 'login' | 'avatar';

const ASSETS = {
  wordmark: { src: '/brand/opensre-wordmark.png', width: 1584, height: 440 },
  spinner: { src: '/brand/opensre-spinner.png', width: 803, height: 815 },
} as const;

type Props = {
  variant: Variant;
  surface: Surface;
  priority?: boolean;
};

export function OpenSreBrandLogo({ variant, surface, priority }: Props) {
  const asset = ASSETS[variant];
  const isSpinner = variant === 'spinner';

  const className =
    surface === 'login'
      ? 'h-24 w-auto max-w-[640px] object-contain object-left'
      : surface === 'avatar'
        ? 'h-5 w-5 object-contain'
        : isSpinner
          ? 'h-7 w-7 object-contain'
          : 'h-[35px] w-auto max-w-[210px] object-contain object-left';

  return (
    <Image
      src={asset.src}
      alt="OpenSRE"
      width={asset.width}
      height={asset.height}
      priority={priority}
      className={className}
    />
  );
}
