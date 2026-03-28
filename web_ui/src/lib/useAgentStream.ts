'use client';

import { useState, useCallback, useRef } from 'react';

export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  isStreaming?: boolean;
}

export interface ToolCall {
  id: string;
  name: string;
  status: 'running' | 'completed' | 'error';
  input?: Record<string, unknown>;
  output?: string;
  startedAt: Date;
  completedAt?: Date;
}

export interface StreamEvent {
  type: string;
  data: Record<string, unknown>;
}

interface UseAgentStreamOptions {
  /** Agent name to use. If not provided, uses team's configured entrance_agent from config. */
  agentName?: string;
  onComplete?: (output: string) => void;
  onError?: (error: string) => void;
}

export function useAgentStream(options: UseAgentStreamOptions = {}) {
  // Note: If agentName is undefined, the API route will fetch the team's entrance_agent from config
  const { agentName, onComplete, onError } = options;

  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCall[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastResponseIdRef = useRef<string | null>(null);

  // Track tool call count for stable IDs
  const toolCallCountRef = useRef(0);

  // Define handleStreamEvent FIRST so it can be used in sendMessage's dependency array
  // Supports both orchestrator format and sre-agent format:
  //   Orchestrator: {type: "tool_started", tool: "...", sequence: N, ...}
  //   SRE-Agent:    {type: "tool_start", data: {name: "...", ...}, thread_id: "...", ...}
  const handleStreamEvent = useCallback((event: Record<string, unknown>, assistantMsgId: string) => {
    const eventType = event.type as string || (event.agent ? 'agent_started' : 'unknown');
    // sre-agent nests details inside "data", flatten for uniform access
    const eventData = (event.data && typeof event.data === 'object') ? event.data as Record<string, unknown> : {};
    console.log('[useAgentStream] handleStreamEvent:', eventType, event);

    switch (eventType) {
      case 'agent_started':
        console.log('[useAgentStream] Agent started');
        break;

      // sre-agent: "thought" events contain agent reasoning
      case 'thought': {
        const text = eventData.text as string || '';
        // Skip empty/placeholder thought events
        if (text && text.trim() !== '(no content)') {
          setMessages(prev => prev.map(m =>
            m.id === assistantMsgId
              ? { ...m, content: m.content + (m.content ? '\n' : '') + text }
              : m
          ));
        }
        break;
      }

      // Support both "tool_started" (orchestrator) and "tool_start" (sre-agent)
      case 'tool_started':
      case 'tool_start': {
        toolCallCountRef.current += 1;
        const toolName = event.tool as string || eventData.name as string || 'unknown';
        const toolCall: ToolCall = {
          id: eventData.tool_use_id as string || `tool-${Date.now()}-${toolCallCountRef.current}`,
          name: toolName,
          status: 'running',
          input: event.input as Record<string, unknown> || eventData.input as Record<string, unknown>,
          startedAt: new Date(),
        };
        setCurrentToolCalls(prev => [...prev, toolCall]);
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
            : m
        ));
        break;
      }

      // Support both "tool_completed" (orchestrator) and "tool_end" (sre-agent)
      case 'tool_completed':
      case 'tool_end': {
        const toolUseId = eventData.tool_use_id as string;
        const outputText = event.output_preview as string || eventData.output as string || eventData.summary as string || '';
        const success = eventData.success !== false;

        if (toolUseId) {
          // Match by tool_use_id
          setCurrentToolCalls(prev => prev.map(tc =>
            tc.id === toolUseId
              ? { ...tc, status: success ? 'completed' : 'error', output: outputText, completedAt: new Date() }
              : tc
          ));
          setMessages(prev => prev.map(m => {
            if (m.id !== assistantMsgId) return m;
            const updatedToolCalls = (m.toolCalls || []).map(tc =>
              tc.id === toolUseId
                ? { ...tc, status: (success ? 'completed' : 'error') as 'completed' | 'error', output: outputText, completedAt: new Date() }
                : tc
            );
            return { ...m, toolCalls: updatedToolCalls };
          }));
        } else {
          // Fallback: mark the last running tool as completed
          setCurrentToolCalls(prev => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].status === 'running') {
                updated[i] = { ...updated[i], status: success ? 'completed' : 'error', output: outputText, completedAt: new Date() };
                break;
              }
            }
            return updated;
          });
          setMessages(prev => prev.map(m => {
            if (m.id !== assistantMsgId) return m;
            const updatedToolCalls = [...(m.toolCalls || [])];
            for (let i = updatedToolCalls.length - 1; i >= 0; i--) {
              if (updatedToolCalls[i].status === 'running') {
                updatedToolCalls[i] = { ...updatedToolCalls[i], status: (success ? 'completed' : 'error') as 'completed' | 'error', output: outputText, completedAt: new Date() };
                break;
              }
            }
            return { ...m, toolCalls: updatedToolCalls };
          }));
        }
        break;
      }

      case 'message':
      case 'text_delta': {
        const content = event.content_preview as string || event.content as string || '';
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: m.content + content }
            : m
        ));
        break;
      }

      // sre-agent: "result" is the final output
      case 'result': {
        // Clean up "(no content)" placeholders from the concatenated result
        const rawResultText = eventData.text as string || '';
        const resultText = rawResultText
          .replace(/\n*\(no content\)\n*/g, '\n')
          .replace(/\n{3,}/g, '\n\n')
          .trim();
        const success = eventData.success !== false;

        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: resultText || m.content, isStreaming: false }
            : m
        ));

        if (success) {
          onComplete?.(resultText);
        } else {
          setError('Investigation failed');
          onError?.('Investigation failed');
        }
        break;
      }

      case 'agent_completed': {
        console.log('[useAgentStream] Agent completed, event.output:', event.output, 'type:', typeof event.output);
        let output = '';
        if (typeof event.output === 'string') {
          output = event.output;
        } else if (event.output && typeof event.output === 'object') {
          const structured = event.output as Record<string, unknown>;
          if (structured.summary && typeof structured.summary === 'string') {
            output = structured.summary;
          } else {
            output = JSON.stringify(event.output, null, 2);
          }
        }

        const lastResponseId = event.last_response_id as string;
        if (lastResponseId) {
          lastResponseIdRef.current = lastResponseId;
        }

        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: output || m.content, isStreaming: false }
            : m
        ));

        if (event.success) {
          onComplete?.(output);
        } else if (event.error) {
          setError(event.error as string);
          onError?.(event.error as string);
        }
        break;
      }

      case 'error': {
        const errorMsg = eventData.message as string || 'Unknown error';
        setError(errorMsg);
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: m.content || `Error: ${errorMsg}`, isStreaming: false }
            : m
        ));
        onError?.(errorMsg);
        break;
      }

      case 'subagent_started':
      case 'subagent_completed':
        // Sub-agent events - could show nested progress
        break;
    }
  }, [onComplete, onError]);

  const sendMessage = useCallback(async (userMessage: string) => {
    console.log('[useAgentStream] sendMessage called:', userMessage);
    if (isStreaming) {
      console.log('[useAgentStream] Already streaming, returning');
      return;
    }

    setError(null);
    setIsStreaming(true);

    // Add user message
    const userMsgId = `user-${Date.now()}`;
    const userMsg: AgentMessage = {
      id: userMsgId,
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    // Add placeholder assistant message
    const assistantMsgId = `assistant-${Date.now()}`;
    const assistantMsg: AgentMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      toolCalls: [],
      isStreaming: true,
    };
    setMessages(prev => [...prev, assistantMsg]);
    setCurrentToolCalls([]);

    // Create abort controller
    abortControllerRef.current = new AbortController();

    try {
      console.log('[useAgentStream] Fetching /api/team/agent/stream...');
      const response = await fetch('/api/team/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          // Only include agent_name if explicitly provided; otherwise API uses team's entrance_agent
          ...(agentName && { agent_name: agentName }),
          previous_response_id: lastResponseIdRef.current,
        }),
        signal: abortControllerRef.current.signal,
      });

      console.log('[useAgentStream] Response status:', response.status, response.ok);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      let chunkCount = 0;

      console.log('[useAgentStream] Starting to read stream...');

      let currentEventType = '';  // Track the event type from "event:" line

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('[useAgentStream] Stream done, total chunks:', chunkCount);

          // Finalize: mark any still-running tool calls as completed and stop streaming
          setMessages(prev => prev.map(m => {
            if (m.id !== assistantMsgId) return m;
            const finalizedToolCalls = (m.toolCalls || []).map(tc =>
              tc.status === 'running'
                ? { ...tc, status: 'completed' as const, completedAt: new Date() }
                : tc
            );
            return { ...m, toolCalls: finalizedToolCalls, isStreaming: false };
          }));
          setCurrentToolCalls(prev => prev.map(tc =>
            tc.status === 'running'
              ? { ...tc, status: 'completed' as const, completedAt: new Date() }
              : tc
          ));

          break;
        }

        chunkCount++;
        const chunk = decoder.decode(value, { stream: true });
        console.log('[useAgentStream] Chunk', chunkCount, ':', chunk.substring(0, 200));
        buffer += chunk;

        // Parse SSE events
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            // Capture the event type for the next data line
            currentEventType = line.slice(7).trim();
            console.log('[useAgentStream] Event type:', currentEventType);
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              // Inject the event type from the "event:" line into the data
              const eventWithType = { ...data, type: currentEventType || data.type };
              console.log('[useAgentStream] Parsed data with type:', eventWithType);
              handleStreamEvent(eventWithType, assistantMsgId);
              currentEventType = ''; // Reset after use
            } catch (e) {
              console.log('[useAgentStream] Parse error for line:', line, e);
            }
          }
        }
      }

    } catch (err) {
      console.log('[useAgentStream] Caught error:', err);
      if ((err as Error).name === 'AbortError') {
        console.log('[useAgentStream] User cancelled');
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: m.content || 'Cancelled', isStreaming: false }
            : m
        ));
      } else {
        const errorMessage = (err as Error).message || 'Failed to run agent';
        console.log('[useAgentStream] Error message:', errorMessage);
        setError(errorMessage);
        setMessages(prev => prev.map(m =>
          m.id === assistantMsgId
            ? { ...m, content: `Error: ${errorMessage}`, isStreaming: false }
            : m
        ));
        onError?.(errorMessage);
      }
    } finally {
      console.log('[useAgentStream] Finally block - setting isStreaming=false');
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [isStreaming, agentName, onError, handleStreamEvent]);

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setError(null);
    setCurrentToolCalls([]);
    lastResponseIdRef.current = null;
  }, []);

  return {
    messages,
    isStreaming,
    error,
    currentToolCalls,
    sendMessage,
    cancel,
    reset,
  };
}
