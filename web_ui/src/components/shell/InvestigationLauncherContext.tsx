'use client';

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react';

type InvestigationLauncherValue = {
  open: () => void;
  close: () => void;
  isOpen: boolean;
  /** Register a page-level completion handler; cleanup on unmount. */
  registerOnComplete: (fn: () => void) => () => void;
  /** Invoked by AppShell when a drawer run finishes. */
  onComplete: () => void;
};

const InvestigationLauncherContext =
  createContext<InvestigationLauncherValue | null>(null);

export function InvestigationLauncherProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const onCompleteRef = useRef<(() => void) | null>(null);
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  const registerOnComplete = useCallback((fn: () => void) => {
    onCompleteRef.current = fn;
    return () => {
      if (onCompleteRef.current === fn) {
        onCompleteRef.current = null;
      }
    };
  }, []);

  const onComplete = useCallback(() => {
    onCompleteRef.current?.();
  }, []);

  return (
    <InvestigationLauncherContext.Provider
      value={{ open, close, isOpen, registerOnComplete, onComplete }}
    >
      {children}
    </InvestigationLauncherContext.Provider>
  );
}

export function useInvestigationLauncher(): InvestigationLauncherValue {
  const ctx = useContext(InvestigationLauncherContext);
  if (!ctx) {
    throw new Error(
      'useInvestigationLauncher must be used within InvestigationLauncherProvider',
    );
  }
  return ctx;
}
