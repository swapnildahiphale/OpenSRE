import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React, { useState } from 'react';
import { useA2AConnectionTest } from './useA2AConnectionTest';

// Test component simulating the Team Agent Topology & Admin Config connection test UI
function TestConnectionComponent({ initialUrl = 'https://agent.example.com' }: { initialUrl?: string }) {
  const [url, setUrl] = useState(initialUrl);
  const { testing, result, testConnection, clearResult } = useA2AConnectionTest();

  return (
    <div>
      <input
        data-testid="url-input"
        value={url}
        onChange={(e) => {
          setUrl(e.target.value);
          clearResult();
        }}
      />

      <button
        data-testid="test-connection-button"
        disabled={!url || testing}
        onClick={() => testConnection({ url, auth: { type: 'none' } })}
      >
        {testing ? 'Testing...' : 'Test Connection'}
      </button>

      {result && (
        <div
          data-testid="test-result"
          className={result.success ? 'status-success' : 'status-error'}
        >
          {result.message}
        </div>
      )}
    </div>
  );
}

describe('A2A Connection Test Frontend Flow', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('renders success indicator and message when test succeeds', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          message: 'Connection successful. Remote A2A agent is reachable.',
          agentInfo: { name: 'SRE-Agent' },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );

    render(<TestConnectionComponent />);
    const button = screen.getByTestId('test-connection-button');
    expect(button).not.toBeDisabled();

    fireEvent.click(button);

    // Shows loading state and disables button during test
    expect(screen.getByText('Testing...')).toBeInTheDocument();
    expect(button).toBeDisabled();

    await waitFor(() => {
      expect(screen.getByTestId('test-result')).toBeInTheDocument();
    });

    const resultEl = screen.getByTestId('test-result');
    expect(resultEl).toHaveTextContent('Connection successful. Remote A2A agent is reachable.');
    expect(resultEl).toHaveClass('status-success');
    expect(button).not.toBeDisabled();
    expect(button).toHaveTextContent('Test Connection');
  });

  it('renders API-declared failure as error even when endpoint returns HTTP 200', async () => {
    // Crucial scenario from Issue #19:
    // Remote endpoint failed, API returns HTTP 200 with success: false
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          message: 'Agent error: Method not found',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );

    render(<TestConnectionComponent />);
    const button = screen.getByTestId('test-connection-button');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId('test-result')).toBeInTheDocument();
    });

    const resultEl = screen.getByTestId('test-result');
    expect(resultEl).toHaveTextContent('Agent error: Method not found');
    expect(resultEl).toHaveClass('status-error');
    expect(resultEl).not.toHaveClass('status-success');
  });

  it('handles rejected request / network failure cleanly', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    render(<TestConnectionComponent />);
    const button = screen.getByTestId('test-connection-button');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId('test-result')).toBeInTheDocument();
    });

    const resultEl = screen.getByTestId('test-result');
    expect(resultEl).toHaveTextContent('Failed to fetch');
    expect(resultEl).toHaveClass('status-error');
  });

  it('handles timeout failure cleanly', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          message: 'Connection timed out after 10s.',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );

    render(<TestConnectionComponent />);
    const button = screen.getByTestId('test-connection-button');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId('test-result')).toBeInTheDocument();
    });

    const resultEl = screen.getByTestId('test-result');
    expect(resultEl).toHaveTextContent('Connection timed out after 10s.');
    expect(resultEl).toHaveClass('status-error');
  });

  it('clears stale test feedback when URL changes', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: true,
          message: 'Connection successful. Remote A2A agent is reachable.',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );

    render(<TestConnectionComponent />);
    const button = screen.getByTestId('test-connection-button');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId('test-result')).toBeInTheDocument();
    });

    // User edits the URL input
    const input = screen.getByTestId('url-input');
    fireEvent.change(input, { target: { value: 'https://new-agent.example.com' } });

    // Result should be immediately cleared
    expect(screen.queryByTestId('test-result')).not.toBeInTheDocument();
  });
});
