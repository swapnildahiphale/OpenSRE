import { useState, useCallback } from 'react';
import { testA2AConnection, A2ATestConnectionOptions, A2ATestResult } from './a2aClient';

export function useA2AConnectionTest() {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<A2ATestResult | null>(null);

  const testConnection = useCallback(async (config: A2ATestConnectionOptions): Promise<A2ATestResult> => {
    setTesting(true);
    setResult(null);
    try {
      const res = await testA2AConnection(config);
      setResult(res);
      return res;
    } finally {
      setTesting(false);
    }
  }, []);

  const clearResult = useCallback(() => {
    setResult(null);
  }, []);

  return {
    testing,
    result,
    testConnection,
    clearResult,
  };
}
