'use client';

import React, { useEffect, useCallback, useMemo, useState } from 'react';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import ServiceNode from './ServiceNode';
import { apiFetch } from '@/lib/apiClient';

const nodeTypes = {
  service: ServiceNode,
};

const initialNodes = [
  { id: 'web', type: 'service', position: { x: 250, y: 0 }, data: { label: 'Web Frontend', type: 'frontend', requests: 1200, status: 'healthy' } },
  { id: 'api', type: 'service', position: { x: 250, y: 150 }, data: { label: 'API Gateway', type: 'api', requests: 3400, status: 'healthy' } },
  
  // Service Layer
  { id: 'auth', type: 'service', position: { x: 50, y: 300 }, data: { label: 'Auth Service', type: 'auth', requests: 800, status: 'healthy' } },
  { id: 'user', type: 'service', position: { x: 250, y: 300 }, data: { label: 'User Service', type: 'service', requests: 500, status: 'warning' } }, // Warning state
  { id: 'payment', type: 'service', position: { x: 450, y: 300 }, data: { label: 'Payment Service', type: 'service', requests: 200, status: 'healthy' } },
  
  // DB Layer
  { id: 'db-auth', type: 'service', position: { x: 50, y: 450 }, data: { label: 'Auth DB', type: 'db', requests: 800, status: 'healthy' } },
  { id: 'db-user', type: 'service', position: { x: 250, y: 450 }, data: { label: 'User DB', type: 'db', requests: 500, status: 'healthy' } },
  { id: 'db-pay', type: 'service', position: { x: 450, y: 450 }, data: { label: 'Payment DB', type: 'db', requests: 200, status: 'healthy' } },
];

const initialEdges = [
  { id: 'e1', source: 'web', target: 'api', animated: true, style: { stroke: '#64748b' } },
  { id: 'e2', source: 'api', target: 'auth', animated: true, style: { stroke: '#64748b' } },
  { id: 'e3', source: 'api', target: 'user', animated: true, style: { stroke: '#64748b' } },
  { id: 'e4', source: 'api', target: 'payment', animated: true, style: { stroke: '#64748b' } },
  { id: 'e5', source: 'auth', target: 'db-auth', animated: true, style: { stroke: '#64748b' } },
  { id: 'e6', source: 'user', target: 'db-user', animated: true, style: { stroke: '#64748b' } },
  { id: 'e7', source: 'payment', target: 'db-pay', animated: true, style: { stroke: '#64748b' } },
];

type AnyRecord = Record<string, any>;

function isRecord(v: unknown): v is AnyRecord {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function normalizeNodes(payload: unknown) {
  // Accept: array of nodes, {nodes:[]}, {items:[]}
  if (Array.isArray(payload)) return payload as AnyRecord[];
  if (isRecord(payload) && Array.isArray(payload.nodes)) return payload.nodes as AnyRecord[];
  if (isRecord(payload) && Array.isArray(payload.items)) return payload.items as AnyRecord[];
  return null;
}

export function LiveGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [backendMode, setBackendMode] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const nodeIdSet = useMemo(() => new Set(nodes.map(n => n.id)), [nodes]);

  // Load topology from backend (if available). This will only work when the app can reach the
  // config service (e.g. running in ECS in the VPC). Locally, it will typically fall back to demo data.
  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        setBackendError(null);
        // Prefer admin endpoint (token decides access). Falls back to demo if unauthorized/unreachable.
        const orgId = (typeof window !== 'undefined' && (window.localStorage.getItem('opensre_org_id') || 'org1')) || 'org1';
        const res = await apiFetch(`/api/admin/orgs/${orgId}/nodes`, { cache: 'no-store' });
        if (!res.ok) {
          const msg = await res.text();
          throw new Error(`${res.status} ${res.statusText}: ${msg}`);
        }

        const json = await res.json();
        const rawNodes = normalizeNodes(json);
        if (!rawNodes || rawNodes.length === 0) {
          throw new Error('Empty nodes payload from backend');
        }

        const mapped = rawNodes.map((n, idx) => {
          const id = String(n.id ?? n.node_id ?? n.name ?? n.slug ?? idx);
          const label = String(n.label ?? n.name ?? n.service ?? id);
          const kind = String(n.type ?? n.kind ?? n.category ?? 'service');
          const status = String(n.status ?? 'healthy');
          const requests = Number(n.requests ?? n.rps ?? n.requests_per_sec ?? 0);

          // Basic deterministic layout (grid-ish) if backend doesn't provide coordinates.
          const x = Number(n.x ?? n.position?.x ?? (idx % 3) * 220 + 40);
          const y = Number(n.y ?? n.position?.y ?? Math.floor(idx / 3) * 140 + 40);

          return {
            id,
            type: 'service',
            position: { x, y },
            data: { label, type: kind, requests, status },
          };
        });

        if (!cancelled) {
          setNodes(mapped as any);
          // If the backend also returned edges, we could wire them up here; otherwise
          // keep edges only if they still reference valid node IDs.
          setEdges((prev) => prev.filter(e => nodeIdSet.has(e.source) && nodeIdSet.has(e.target)));
          setBackendMode(true);
        }
      } catch (e: any) {
        if (!cancelled) {
          setBackendMode(false);
          setBackendError(e?.message || String(e));
        }
      }
    };

    load();
    const interval = setInterval(load, 15_000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [setEdges, setNodes, nodeIdSet]);

  // Simulate live data updates (demo mode only)
  useEffect(() => {
    if (backendMode) return;
    const interval = setInterval(() => {
      setNodes((nds) => nds.map((node) => {
        // Randomize requests slightly
        const reqChange = Math.floor(Math.random() * 50) - 25;
        const newReq = Math.max(0, (node.data.requests as number) + reqChange);
        
        // Occasional status flip for demo
        let status = node.data.status;
        if (node.id === 'user' && Math.random() > 0.9) {
            status = status === 'warning' ? 'healthy' : 'warning';
        }

        return {
          ...node,
          data: {
            ...node.data,
            requests: newReq,
            status
          }
        };
      }));
    }, 2000);

    return () => clearInterval(interval);
  }, [backendMode, setNodes]);

  return (
    <div className="w-full h-[500px] bg-stone-50 dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-right"
        className="bg-stone-50 dark:bg-stone-900"
      >
        <MiniMap 
            nodeStrokeColor={(n) => {
                if (n.data.status === 'error') return '#ef4444';
                if (n.data.status === 'warning') return '#eab308';
                return '#3b82f6';
            }}
            nodeColor={(n) => {
                return '#e5e7eb';
            }}
            className="!bg-white dark:!bg-stone-800 border border-stone-200 dark:border-stone-700"
        />
        <Controls className="!bg-white dark:!bg-stone-800 !border-stone-200 dark:!border-stone-700 !shadow-sm" />
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        
        <Panel position="top-left" className="bg-white/80 dark:bg-stone-800/80 backdrop-blur p-2 rounded-lg border border-stone-200 dark:border-stone-700 shadow-sm">
            <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                <span className="text-xs font-medium text-stone-600 dark:text-stone-300">
                  Live Topology {backendMode ? '(backend)' : '(demo)'}
                </span>
            </div>
            {backendError && (
              <div className="mt-1 text-[10px] text-stone-500 max-w-[240px] truncate" title={backendError}>
                Backend unavailable: {backendError}
              </div>
            )}
        </Panel>
      </ReactFlow>
    </div>
  );
}
