'use client';

import { useEffect, useState, useCallback } from 'react';
import { RequireRole } from '@/components/RequireRole';
import { apiFetch } from '@/lib/apiClient';
import { useIdentity } from '@/lib/useIdentity';
import { Network, RefreshCcw, Plus, X, ChevronRight, Settings, Key, Edit2 } from 'lucide-react';

// Types
interface OrgNode {
  org_id: string;
  node_id: string;
  parent_id: string | null;
  node_type: 'org' | 'team';
  name: string | null;
  created_at?: string;
  children?: OrgNode[];
}

// Tree building
function buildTree(nodes: OrgNode[]): OrgNode[] {
  const byId: Record<string, OrgNode> = {};
  for (const n of nodes) {
    byId[n.node_id] = { ...n, children: [] };
  }
  const roots: OrgNode[] = [];
  for (const n of nodes) {
    const parent = n.parent_id ? byId[n.parent_id] : null;
    if (parent) {
      parent.children!.push(byId[n.node_id]);
    } else {
      roots.push(byId[n.node_id]);
    }
  }
  const sortChildren = (node: OrgNode) => {
    node.children?.sort((a, b) => a.node_id.localeCompare(b.node_id));
    node.children?.forEach(sortChildren);
  };
  roots.forEach(sortChildren);
  return roots.sort((a, b) => a.node_id.localeCompare(b.node_id));
}

// Node type colors
const nodeColors = {
  org: { bg: 'bg-emerald-600', border: 'border-emerald-500', text: 'text-emerald-600' },
  team: { bg: 'bg-blue-600', border: 'border-blue-500', text: 'text-forest' },
};

// Tree Node Component
function TreeNodeComponent({ 
  node, 
  level = 0, 
  onSelect 
}: { 
  node: OrgNode; 
  level?: number; 
  onSelect: (node: OrgNode) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = (node.children?.length ?? 0) > 0;
  const colors = nodeColors[node.node_type] || nodeColors.team;

  return (
    <div className="relative">
      {/* Vertical line from parent */}
      {level > 0 && (
        <div className="absolute left-[-20px] top-0 w-[20px] h-[24px] border-l-2 border-b-2 border-stone-300 dark:border-stone-600 rounded-bl-lg" />
      )}
      
      {/* Node */}
      <div className="flex items-center gap-2 mb-2">
        {hasChildren && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-5 h-5 flex items-center justify-center text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 transition-transform"
            style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        )}
        {!hasChildren && <div className="w-5" />}
        
        <button
          onClick={() => onSelect(node)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border-2 ${colors.border} bg-white dark:bg-stone-800 hover:shadow-md transition-all cursor-pointer`}
        >
          <span className={`w-2 h-2 rounded-full ${colors.bg}`} />
          <span className="font-medium text-stone-900 dark:text-white text-sm">
            {node.name || node.node_id}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${colors.bg} text-white`}>
            {node.node_type}
          </span>
        </button>
      </div>

      {/* Children */}
      {hasChildren && expanded && (
        <div className="ml-8 pl-4 border-l-2 border-stone-200 dark:border-stone-700">
          {node.children!.map((child) => (
            <TreeNodeComponent 
              key={child.node_id} 
              node={child} 
              level={level + 1} 
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Modal Component
function Modal({ 
  isOpen, 
  onClose, 
  title, 
  children 
}: { 
  isOpen: boolean; 
  onClose: () => void; 
  title: string; 
  children: React.ReactNode;
}) {
  if (!isOpen) return null;
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white dark:bg-stone-800 rounded-xl shadow-2xl max-w-lg w-full mx-4 max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between p-4 border-b border-stone-200 dark:border-stone-700">
          <h3 className="font-semibold text-lg text-stone-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg">
            <X className="w-5 h-5 text-stone-500" />
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

export default function OrgTreePage() {
  const { identity } = useIdentity();
  const [nodes, setNodes] = useState<OrgNode[]>([]);
  const [tree, setTree] = useState<OrgNode[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Selected node panel
  const [selectedNode, setSelectedNode] = useState<OrgNode | null>(null);
  
  // Modals
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [editNodeOpen, setEditNodeOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [tokensOpen, setTokensOpen] = useState(false);
  const [issuedToken, setIssuedToken] = useState<string | null>(null);
  
  // Form state
  const [newNodeId, setNewNodeId] = useState('');
  const [newNodeName, setNewNodeName] = useState('');
  const [newNodeParent, setNewNodeParent] = useState('');
  const [newNodeType, setNewNodeType] = useState<'team'>('team');
  
  // Edit form state
  const [editNodeName, setEditNodeName] = useState('');
  const [editNodeParent, setEditNodeParent] = useState('');
  
  // Config state
  const [effectiveConfig, setEffectiveConfig] = useState<Record<string, unknown> | null>(null);
  const [configPatch, setConfigPatch] = useState('{}');
  
  // Tokens state
  const [tokens, setTokens] = useState<{ token_id: string; revoked_at?: string }[]>([]);

  const orgId = identity?.org_id || (identity?.role === 'admin' ? 'local' : undefined);

  const loadNodes = useCallback(async () => {
    if (!orgId) return; // Wait for identity to load
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/nodes`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      const data = await res.json();
      setNodes(data);
      setTree(buildTree(data));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    if (orgId) {
      loadNodes();
    }
  }, [orgId, loadNodes]);

  // Handle node selection
  const handleNodeSelect = (node: OrgNode) => {
    setSelectedNode(node);
  };

  // Create node
  const handleCreateNode = async () => {
    if (!newNodeId.trim()) {
      alert('Node ID is required');
      return;
    }
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_id: newNodeId.trim(),
          parent_id: newNodeParent || null,
          node_type: newNodeType,
          name: newNodeName.trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      setAddNodeOpen(false);
      setNewNodeId('');
      setNewNodeName('');
      setNewNodeParent('');
      await loadNodes();
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  // Open add node modal with parent pre-selected
  const openAddNodeWithParent = (parentId: string) => {
    setNewNodeParent(parentId);
    setAddNodeOpen(true);
  };

  // Open edit modal
  const openEditNode = () => {
    if (!selectedNode) return;
    setEditNodeName(selectedNode.name || '');
    setEditNodeParent(selectedNode.parent_id || '');
    setEditNodeOpen(true);
  };

  // Save edit
  const handleSaveEdit = async () => {
    if (!selectedNode) return;
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/nodes/${selectedNode.node_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editNodeName.trim() || null,
          parent_id: editNodeParent || null,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      setEditNodeOpen(false);
      setSelectedNode(null);
      await loadNodes();
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  // Load config
  const loadConfig = async () => {
    if (!selectedNode || !orgId) return;
    try {
      const [effRes, rawRes] = await Promise.all([
        apiFetch(`/api/admin/orgs/${orgId}/config/${selectedNode.node_id}/effective`, { cache: 'no-store' }),
        apiFetch(`/api/admin/orgs/${orgId}/config/${selectedNode.node_id}/raw`, { cache: 'no-store' }),
      ]);
      if (effRes.ok) {
        const effData = await effRes.json();
        setEffectiveConfig(effData.effective_config || effData);
      }
      if (rawRes.ok) {
        const rawData = await rawRes.json();
        // rawData contains the local config for this node
        setConfigPatch(JSON.stringify(rawData.config || {}, null, 2));
      }
    } catch (e) {
      console.error('Failed to load config:', e);
      alert('Failed to load configuration');
    }
  };

  // Save config
  const saveConfig = async () => {
    if (!selectedNode || !orgId) return;
    try {
      // Parse the JSON from the textarea
      const parsedConfig = JSON.parse(configPatch);

      const res = await apiFetch(`/api/admin/orgs/${orgId}/config/${selectedNode.node_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          config: parsedConfig,
          reason: 'Updated via org tree UI'
        }),
      });

      if (!res.ok) {
        const error = await res.text();
        throw new Error(error);
      }

      alert('Configuration saved successfully!');
      setConfigOpen(false);
      // Reload the config to show updated values
      await loadConfig();
    } catch (e) {
      console.error('Failed to save config:', e);
      alert(`Failed to save configuration: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  // Load tokens
  const loadTokens = async (teamNodeId: string) => {
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/teams/${teamNodeId}/tokens`, { cache: 'no-store' });
      if (res.ok) {
        setTokens(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Issue token
  const issueToken = async () => {
    if (!selectedNode || selectedNode.node_type !== 'team') return;
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/teams/${selectedNode.node_id}/tokens`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      const data = await res.json();
      setIssuedToken(data.token);
      await loadTokens(selectedNode.node_id);
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  // Revoke token
  const revokeToken = async (tokenId: string) => {
    if (!selectedNode || !confirm(`Revoke token ${tokenId}?`)) return;
    try {
      const res = await apiFetch(`/api/admin/orgs/${orgId}/teams/${selectedNode.node_id}/tokens/${tokenId}/revoke`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
      await loadTokens(selectedNode.node_id);
    } catch (e) {
      alert(`Failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  return (
    <RequireRole role="admin" fallbackHref="/">
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Network className="w-7 h-7 text-stone-500" />
            <div>
              <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">Organization Tree</h1>
              <p className="text-sm text-stone-500">Manage teams and hierarchy for <span className="font-mono">{orgId}</span></p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setNewNodeParent('root'); setAddNodeOpen(true); }}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-forest text-white rounded-lg hover:bg-forest-dark"
            >
              <Plus className="w-4 h-4" /> Add Node
            </button>
          <button
              onClick={loadNodes}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 disabled:opacity-70"
          >
              <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
          </div>
        </div>

        {error && (
          <div className="text-sm text-clay bg-clay-light/10 dark:bg-clay/20 border border-red-100 dark:border-red-900/40 rounded-lg p-3">
            {error}
          </div>
        )}

        {/* Legend */}
        <div className="flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-600" />
            <span className="text-stone-600 dark:text-stone-400">Organization</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-amber-500" />
            <span className="text-stone-600 dark:text-stone-400">Unit (Group)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-blue-600" />
            <span className="text-stone-600 dark:text-stone-400">Team</span>
          </div>
        </div>

        {/* Main content - Tree + Details */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Tree */}
          <div className="lg:col-span-2 bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 shadow-sm">
            {tree.length === 0 ? (
              <div className="text-center py-12 text-stone-500">
                {loading ? 'Loading...' : 'No nodes found. Create your first node!'}
              </div>
            ) : (
              <div className="space-y-2">
                {tree.map((root) => (
                  <TreeNodeComponent key={root.node_id} node={root} onSelect={handleNodeSelect} />
                ))}
              </div>
            )}
          </div>

          {/* Details Panel */}
          <div className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 rounded-xl p-6 shadow-sm">
            {selectedNode ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-lg text-stone-900 dark:text-white">
                    {selectedNode.name || selectedNode.node_id}
                  </h3>
                  <span className={`text-xs px-2 py-1 rounded-full ${nodeColors[selectedNode.node_type].bg} text-white`}>
                    {selectedNode.node_type}
                  </span>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between py-2 border-b border-stone-100 dark:border-stone-700">
                    <span className="text-stone-500">Node ID</span>
                    <span className="font-mono text-stone-900 dark:text-white">{selectedNode.node_id}</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-stone-100 dark:border-stone-700">
                    <span className="text-stone-500">Parent</span>
                    <span className="font-mono text-stone-900 dark:text-white">{selectedNode.parent_id || '(root)'}</span>
                  </div>
                  {selectedNode.created_at && (
                    <div className="flex justify-between py-2 border-b border-stone-100 dark:border-stone-700">
                      <span className="text-stone-500">Created</span>
                      <span className="text-stone-900 dark:text-white">
                        {new Date(selectedNode.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2">
                  <button
                    onClick={() => openAddNodeWithParent(selectedNode.node_id)}
                    className="flex items-center justify-center gap-1 px-3 py-2 text-sm bg-forest text-white rounded-lg hover:bg-forest-dark"
                  >
                    <Plus className="w-4 h-4" /> Add Child
                  </button>
                  <button
                    onClick={openEditNode}
                    className="flex items-center justify-center gap-1 px-3 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
                  >
                    <Edit2 className="w-4 h-4" /> Edit
                  </button>
                  <button
                    onClick={() => { loadConfig(); setConfigOpen(true); }}
                    className="flex items-center justify-center gap-1 px-3 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
                  >
                    <Settings className="w-4 h-4" /> Config
                  </button>
                  {selectedNode.node_type === 'team' && (
                    <button
                      onClick={() => { loadTokens(selectedNode.node_id); setTokensOpen(true); }}
                      className="flex items-center justify-center gap-1 px-3 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
                    >
                      <Key className="w-4 h-4" /> Tokens
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-stone-500">
                Click a node to see details
              </div>
            )}
          </div>
        </div>

        {/* Add Node Modal */}
        <Modal isOpen={addNodeOpen} onClose={() => setAddNodeOpen(false)} title="Add New Node">
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Node ID</label>
              <input
                value={newNodeId}
                onChange={(e) => setNewNodeId(e.target.value)}
                placeholder="e.g. platform-sre"
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700"
              />
            </div>
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Display Name</label>
              <input
                value={newNodeName}
                onChange={(e) => setNewNodeName(e.target.value)}
                placeholder="e.g. Platform SRE Team"
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700"
              />
            </div>
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Parent Node</label>
              <select
                value={newNodeParent}
                onChange={(e) => setNewNodeParent(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700"
              >
                <option value="">(Select parent)</option>
                {nodes.map((n) => (
                  <option key={n.node_id} value={n.node_id}>
                    {n.node_id} ({n.node_type})
                  </option>
                ))}
              </select>
            </div>
            {/* Node type is always 'team' (removed unit concept) */}
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setAddNodeOpen(false)}
                className="px-4 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateNode}
                className="px-4 py-2 text-sm bg-forest text-white rounded-lg hover:bg-forest-dark"
              >
                Create Node
              </button>
            </div>
          </div>
        </Modal>

        {/* Edit Node Modal */}
        <Modal isOpen={editNodeOpen} onClose={() => setEditNodeOpen(false)} title="Edit Node">
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Node ID (read-only)</label>
              <input
                value={selectedNode?.node_id || ''}
                disabled
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-stone-100 dark:bg-stone-700 opacity-60"
              />
            </div>
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Display Name</label>
              <input
                value={editNodeName}
                onChange={(e) => setEditNodeName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700"
              />
            </div>
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Parent Node</label>
              <select
                value={editNodeParent}
                onChange={(e) => setEditNodeParent(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700"
              >
                <option value="">(root - no parent)</option>
                {nodes.filter(n => n.node_id !== selectedNode?.node_id).map((n) => (
                  <option key={n.node_id} value={n.node_id}>
                    {n.node_id} ({n.node_type})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setEditNodeOpen(false)}
                className="px-4 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-4 py-2 text-sm bg-forest text-white rounded-lg hover:bg-forest-dark"
              >
                Save Changes
              </button>
            </div>
          </div>
        </Modal>

        {/* Config Modal */}
        <Modal isOpen={configOpen} onClose={() => setConfigOpen(false)} title={`Config: ${selectedNode?.node_id}`}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Effective Config (inherited)</label>
              <pre className="text-xs bg-stone-50 dark:bg-stone-900 p-3 rounded-lg overflow-auto max-h-40 border border-stone-200 dark:border-stone-700">
                {effectiveConfig ? JSON.stringify(effectiveConfig, null, 2) : 'Loading...'}
        </pre>
            </div>
            <div>
              <label className="block text-sm text-stone-600 dark:text-stone-400 mb-1">Local Config (JSON)</label>
              <textarea
                value={configPatch}
                onChange={(e) => setConfigPatch(e.target.value)}
                rows={6}
                className="w-full px-3 py-2 rounded-lg border border-stone-200 dark:border-stone-600 bg-white dark:bg-stone-700 font-mono text-xs"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setConfigOpen(false)}
                className="px-4 py-2 text-sm bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700"
              >
                Close
              </button>
              <button
                onClick={saveConfig}
                className="px-4 py-2 text-sm bg-forest text-white rounded-lg hover:bg-forest-dark"
              >
                Save Config
              </button>
            </div>
          </div>
        </Modal>

        {/* Tokens Modal */}
        <Modal isOpen={tokensOpen} onClose={() => setTokensOpen(false)} title={`Tokens: ${selectedNode?.node_id}`}>
          <div className="space-y-4">
            <button
              onClick={issueToken}
              className="w-full px-4 py-2 text-sm bg-forest text-white rounded-lg hover:bg-forest-dark"
            >
              Issue New Token
            </button>
            
            {tokens.length === 0 ? (
              <div className="text-center py-6 text-stone-500 text-sm">
                No tokens issued for this team
              </div>
            ) : (
              <div className="space-y-2">
                {tokens.map((t) => (
                  <div key={t.token_id} className="flex items-center justify-between p-3 bg-stone-50 dark:bg-stone-700 rounded-lg">
                    <div>
                      <div className="font-mono text-xs text-stone-900 dark:text-white">{t.token_id}</div>
                      <div className="text-xs text-stone-500">
                        {t.revoked_at ? `Revoked: ${new Date(t.revoked_at).toLocaleDateString()}` : 'Active'}
                      </div>
                    </div>
                    {!t.revoked_at && (
                      <button
                        onClick={() => revokeToken(t.token_id)}
                        className="px-3 py-1 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700"
                      >
                        Revoke
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>

        {/* Issued Token Modal */}
        <Modal isOpen={!!issuedToken} onClose={() => setIssuedToken(null)} title="Token Issued">
          <p className="text-sm text-stone-600 dark:text-stone-400 mb-3">
            Copy this token now — it won&apos;t be shown again.
          </p>
          <div className="relative">
            <pre className="p-3 bg-stone-100 dark:bg-stone-800 rounded-lg text-xs font-mono break-all whitespace-pre-wrap select-all border border-stone-200 dark:border-stone-700">
              {issuedToken}
            </pre>
            <button
              onClick={() => {
                if (issuedToken) {
                  navigator.clipboard.writeText(issuedToken);
                }
              }}
              className="absolute top-2 right-2 px-2 py-1 text-xs bg-forest text-white rounded hover:bg-forest-dark"
            >
              Copy
            </button>
          </div>
          <div className="flex justify-end mt-4">
            <button
              onClick={() => setIssuedToken(null)}
              className="px-4 py-2 text-sm bg-forest text-white rounded-lg hover:bg-forest-dark"
            >
              Done
            </button>
          </div>
        </Modal>
      </div>
    </RequireRole>
  );
}
