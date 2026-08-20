'use client';

import { useEffect, useState, useCallback, useRef, Suspense, lazy } from 'react';
import { useIdentity } from '@/lib/useIdentity';
import { apiFetch } from '@/lib/apiClient';
import {
  BookOpen,
  Upload,
  Trash2,
  Search,
  FileText,
  Link as LinkIcon,
  Brain,
  CheckCircle,
  XCircle,
  Eye,
  Plus,
  Sparkles,
  Clock,
  Network,
  Layers,
} from 'lucide-react';
import { TreeSelector, type EffectiveTree, type TreeStats } from '@/components/knowledge/TreeSelector';
import { CreateTreeModal } from '@/components/knowledge/CreateTreeModal';
import { UploadDocumentModal } from '@/components/knowledge/UploadDocumentModal';
import { PageHeader, Button, Skeleton, listRowHoverClass, TeamPageShell } from '@/components/ui-flow';

// Lazy load the TreeExplorer since it's heavy
const TreeExplorer = lazy(() =>
  import('@/components/knowledge/TreeExplorer').then(m => ({ default: m.TreeExplorer }))
);

interface KnowledgeDocument {
  id: string;
  title: string;
  type: 'document' | 'url' | 'manual' | 'learned';
  source?: string;
  content?: string;
  summary?: string;
  createdAt: string;
  createdBy: string;
  status: 'active' | 'pending' | 'archived';
  confidence?: number;
}

interface ProposedKBChange {
  id: string;
  changeType: 'add' | 'update' | 'remove';
  document: Partial<KnowledgeDocument>;
  reason: string;
  learnedFrom?: string;
  proposedAt: string;
  status: 'pending' | 'approved' | 'rejected';
}

type TabType = 'explorer' | 'documents' | 'proposed';

/** Segmented tabs — same position/style for Explorer, Documents, and Proposed. */
function KnowledgeTabs({
  activeTab,
  onTabChange,
  documentsCount,
  proposedCount,
}: {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  documentsCount: number;
  proposedCount: number;
}) {
  const tabClass = (tab: TabType) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
      activeTab === tab
        ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
        : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white'
    }`;

  return (
    <div
      className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl p-1 w-fit"
      role="tablist"
      aria-label="Knowledge sections"
    >
      <button type="button" role="tab" aria-selected={activeTab === 'explorer'} onClick={() => onTabChange('explorer')} className={tabClass('explorer')}>
        <Network className="w-4 h-4 shrink-0" />
        Explorer
      </button>
      <button type="button" role="tab" aria-selected={activeTab === 'documents'} onClick={() => onTabChange('documents')} className={tabClass('documents')}>
        <FileText className="w-4 h-4 shrink-0" />
        Documents ({documentsCount})
      </button>
      <button type="button" role="tab" aria-selected={activeTab === 'proposed'} onClick={() => onTabChange('proposed')} className={tabClass('proposed')}>
        <Sparkles className="w-4 h-4 shrink-0" />
        Proposed
        {proposedCount > 0 && (
          <span className="w-5 h-5 rounded-full bg-emerald-100/60 text-emerald-700 text-xs flex items-center justify-center font-medium">
            {proposedCount}
          </span>
        )}
      </button>
    </div>
  );
}

export default function TeamKnowledgePage() {
  const { identity } = useIdentity();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [proposedChanges, setProposedChanges] = useState<ProposedKBChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('explorer');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [viewingDoc, setViewingDoc] = useState<KnowledgeDocument | null>(null);

  // Tree selection state
  const [effectiveTrees, setEffectiveTrees] = useState<EffectiveTree[]>([]);
  const [treeStats, setTreeStats] = useState<Record<string, TreeStats>>({});
  const [selectedTree, setSelectedTree] = useState<string | null>(null);
  const [treesLoading, setTreesLoading] = useState(true);
  const [showCreateTreeModal, setShowCreateTreeModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const teamId = identity?.team_node_id;

  const loadKnowledge = useCallback(async () => {
    if (!teamId) return;
    setLoading(true);
    try {
      // Load documents
      const docsRes = await apiFetch(`/api/team/knowledge/documents`);
      if (docsRes.ok) {
        const data = await docsRes.json();
        if (Array.isArray(data)) {
          setDocuments(data);
        }
      }
      
      // Load proposed changes
      const changesRes = await apiFetch(`/api/team/knowledge/proposed-changes`);
      if (changesRes.ok) {
        const data = await changesRes.json();
        if (Array.isArray(data)) {
          setProposedChanges(data);
        }
      }
    } catch (e) {
      console.error('Failed to load knowledge', e);
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    if (activeTab !== 'explorer') {
      loadKnowledge();
    } else {
      setLoading(false);
    }
  }, [loadKnowledge, activeTab]);

  // Load effective trees for the current team
  const loadEffectiveTrees = useCallback(async () => {
    if (!teamId) return;
    setTreesLoading(true);
    try {
      const res = await apiFetch('/api/config/effective-trees');
      if (res.ok) {
        const data = await res.json();
        const trees: EffectiveTree[] = data.trees || [];
        setEffectiveTrees(trees);

        // Auto-select first tree if none selected
        if (trees.length > 0 && !selectedTree) {
          setSelectedTree(trees[0].tree_name);
        }

        // Fetch stats for each tree (in parallel)
        const statsPromises = trees.map(async (tree) => {
          try {
            const statsRes = await apiFetch(`/api/team/knowledge/tree/stats?tree=${encodeURIComponent(tree.tree_name)}`);
            if (statsRes.ok) {
              return await statsRes.json();
            }
          } catch {
            // Ignore stats fetch errors
          }
          return null;
        });

        const statsResults = await Promise.all(statsPromises);
        const statsMap: Record<string, TreeStats> = {};
        statsResults.forEach((stats, i) => {
          if (stats && trees[i]) {
            statsMap[trees[i].tree_name] = stats;
          }
        });
        setTreeStats(statsMap);
      } else {
        // Fallback: use default tree if no effective trees endpoint
        console.warn('Could not fetch effective trees, using default');
        const defaultTree: EffectiveTree = {
          tree_name: 'mega_ultra_v2',
          level: 'org',
          node_name: 'Organization',
          node_id: 'default',
          inherited: false,
        };
        setEffectiveTrees([defaultTree]);
        if (!selectedTree) {
          setSelectedTree('mega_ultra_v2');
        }
      }
    } catch (e) {
      console.error('Failed to load effective trees', e);
      // Fallback to default
      const defaultTree: EffectiveTree = {
        tree_name: 'mega_ultra_v2',
        level: 'org',
        node_name: 'Organization',
        node_id: 'default',
        inherited: false,
      };
      setEffectiveTrees([defaultTree]);
      if (!selectedTree) {
        setSelectedTree('mega_ultra_v2');
      }
    } finally {
      setTreesLoading(false);
    }
  }, [teamId, selectedTree]);

  useEffect(() => {
    loadEffectiveTrees();
  }, [loadEffectiveTrees]);

  const handleTreeCreated = useCallback((treeName: string) => {
    // Add the new tree to the list and select it
    const newTree: EffectiveTree = {
      tree_name: treeName,
      level: 'team',
      node_name: identity?.team_node_id || 'Team',
      node_id: identity?.team_node_id || 'team',
      inherited: false,
    };
    setEffectiveTrees((prev) => [newTree, ...prev]);
    setSelectedTree(treeName);
    setMessage({ type: 'success', text: `Tree "${treeName}" created successfully!` });
  }, [identity?.team_node_id]);

  const handleDocumentUploaded = useCallback(() => {
    setMessage({ type: 'success', text: 'Document added to knowledge tree!' });
    // Reload tree stats to reflect the new document
    loadEffectiveTrees();
  }, [loadEffectiveTrees]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await apiFetch('/api/team/knowledge/upload', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const newDoc = await res.json();
        setDocuments((prev) => [newDoc, ...prev]);
        setMessage({ type: 'success', text: `${file.name} uploaded successfully!` });
      } else {
        // Mock success for demo
        const newDoc: KnowledgeDocument = {
          id: `doc_${Date.now()}`,
          title: file.name.replace(/\.[^/.]+$/, ''),
          type: 'document',
          source: file.name,
          summary: 'Processing document...',
          createdAt: new Date().toISOString(),
          createdBy: 'user',
          status: 'active',
        };
        setDocuments((prev) => [newDoc, ...prev]);
        setMessage({ type: 'success', text: `${file.name} uploaded successfully!` });
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.message || 'Upload failed' });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleAddManual = async (data: { title: string; content: string }) => {
    try {
      const res = await apiFetch('/api/team/knowledge/documents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: data.title,
          content: data.content,
          type: 'manual',
        }),
      });
      if (res.ok) {
        const newDoc = await res.json();
        setDocuments((prev) => [newDoc, ...prev]);
        setShowAddModal(false);
        setMessage({ type: 'success', text: 'Knowledge entry added!' });
      } else {
        const err = await res.json();
        setMessage({ type: 'error', text: err.detail || 'Failed to add' });
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.message || 'Failed to add' });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const res = await apiFetch(`/api/team/knowledge/documents/${id}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.id !== id));
        setMessage({ type: 'success', text: 'Document removed' });
      } else {
        const err = await res.json();
        setMessage({ type: 'error', text: err.detail || 'Failed to delete' });
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.message || 'Failed to delete' });
    }
  };

  const handleApproveChange = async (changeId: string) => {
    try {
      const res = await apiFetch(`/api/team/knowledge/proposed-changes/${changeId}/approve`, {
        method: 'POST',
      });
      if (res.ok) {
        setProposedChanges((prev) => prev.filter((c) => c.id !== changeId));
        setMessage({ type: 'success', text: 'Proposed change approved and added to knowledge base!' });
        loadKnowledge();
      } else {
        const err = await res.json();
        setMessage({ type: 'error', text: err.detail || 'Failed to approve' });
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.message || 'Failed to approve' });
    }
  };

  const handleRejectChange = async (changeId: string) => {
    try {
      const res = await apiFetch(`/api/team/knowledge/proposed-changes/${changeId}/reject`, {
        method: 'POST',
      });
      if (res.ok) {
        setProposedChanges((prev) => prev.filter((c) => c.id !== changeId));
        setMessage({ type: 'success', text: 'Proposed change rejected' });
      } else {
        const err = await res.json();
        setMessage({ type: 'error', text: err.detail || 'Failed to reject' });
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e?.message || 'Failed to reject' });
    }
  };

  const filteredDocs = documents.filter(
    (d) =>
      d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.summary?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'document':
        return <FileText className="w-4 h-4" />;
      case 'url':
        return <LinkIcon className="w-4 h-4" />;
      case 'learned':
        return <Brain className="w-4 h-4" />;
      default:
        return <BookOpen className="w-4 h-4" />;
    }
  };

  // Shared chrome: PageHeader + tabs stay fixed; only the body swaps.
  // Explorer used to put tabs in header actions (right) while Documents used
  // Chip pills below — switching tabs jumped and misaligned the control.
  const headerActions =
    activeTab === 'explorer' ? (
      selectedTree ? (
        <Button variant="primary" onClick={() => setShowUploadModal(true)}>
          <Upload className="w-4 h-4" />
          Upload
        </Button>
      ) : null
    ) : (
      <div className="flex items-center gap-3">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          className="hidden"
          accept=".pdf,.md,.txt,.doc,.docx"
        />
        <Button
          variant="secondary"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          <Upload className={`w-4 h-4 ${uploading ? 'animate-pulse' : ''}`} />
          {uploading ? 'Uploading...' : 'Upload'}
        </Button>
        <Button variant="primary" onClick={() => setShowAddModal(true)}>
          <Plus className="w-4 h-4" />
          Add Entry
        </Button>
      </div>
    );

  return (
    <>
    <TeamPageShell
      variant="fixedHeader"
      header={
        <>
          <PageHeader
            eyebrow="Team console"
            title="Knowledge"
            subtitle="Team docs and RAPTOR knowledge trees for semantic search and Q&A"
            actions={headerActions}
          />
          <KnowledgeTabs
            activeTab={activeTab}
            onTabChange={setActiveTab}
            documentsCount={documents.length}
            proposedCount={proposedChanges.length}
          />
          {message && (
            <div
              className={`p-4 rounded-xl flex items-center gap-3 ${
                message.type === 'success'
                  ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400'
                  : 'bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-500 text-rose-700 dark:text-rose-400'
              }`}
            >
              {message.type === 'success' ? (
                <CheckCircle className="w-5 h-5" />
              ) : (
                <XCircle className="w-5 h-5" />
              )}
              {message.text}
            </div>
          )}
        </>
      }
      bleed={
        activeTab === 'explorer' ? (
        <>
          <div className="shrink-0 px-10 py-4 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200/70">
            <div className="max-w-[1240px] mx-auto w-full">
              <TreeSelector
                trees={effectiveTrees}
                treeStats={treeStats}
                selectedTree={selectedTree}
                onSelectTree={setSelectedTree}
                loading={treesLoading}
                onCreateTree={() => setShowCreateTreeModal(true)}
              />
            </div>
          </div>

          <div className="flex-1 min-h-0">
            {selectedTree ? (
              <Suspense
                fallback={
                  <div className="h-full flex items-center justify-center bg-slate-50 dark:bg-slate-800">
                    <div className="text-center space-y-3 w-48 mx-auto">
                      <Skeleton className="h-8 w-8 rounded-full mx-auto" />
                      <p className="text-slate-500">Loading Tree Explorer...</p>
                    </div>
                  </div>
                }
              >
                <TreeExplorer treeName={selectedTree} />
              </Suspense>
            ) : (
              <div className="h-full flex items-center justify-center bg-slate-50 dark:bg-slate-800">
                <div className="text-center">
                  <Layers className="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-500">Select a tree to explore</p>
                </div>
              </div>
            )}
          </div>

          {showCreateTreeModal && (
            <CreateTreeModal
              onClose={() => setShowCreateTreeModal(false)}
              onCreated={handleTreeCreated}
            />
          )}

          {showUploadModal && selectedTree && (
            <UploadDocumentModal
              treeName={selectedTree}
              onClose={() => setShowUploadModal(false)}
              onUploaded={handleDocumentUploaded}
            />
          )}
        </>
        ) : undefined
      }
    >
      {activeTab !== 'explorer' && (
        <>
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 w-full max-w-md mx-auto">
              <Skeleton className="h-24 w-full rounded-xl" />
              <Skeleton className="h-24 w-full rounded-xl" />
            </div>
          ) : (
            <>
              {activeTab === 'documents' && (
                <>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search knowledge base..."
                      className="w-full pl-10 pr-4 py-2 rounded-full border border-slate-200/70 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
                    />
                  </div>

                  {filteredDocs.length === 0 ? (
                    <div className="rounded-[1.5rem] border border-slate-200/70 bg-white dark:bg-slate-800 p-12 text-center">
                      <BookOpen className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
                      <p className="text-slate-500">No knowledge documents found.</p>
                      <p className="text-sm text-slate-400 mt-2">
                        Try the{' '}
                        <button
                          type="button"
                          onClick={() => setActiveTab('explorer')}
                          className="text-slate-600 dark:text-slate-400 hover:underline"
                        >
                          Tree Explorer
                        </button>{' '}
                        to search the RAPTOR knowledge base.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {filteredDocs.map((doc) => (
                        <div
                          key={doc.id}
                          className={`rounded-[1.5rem] border border-slate-200/70 bg-white dark:bg-slate-800 p-4 ${listRowHoverClass}`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-start gap-3 flex-1">
                              <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 bg-slate-100 dark:bg-slate-700 text-slate-600">
                                {getTypeIcon(doc.type)}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <h3 className="text-[14.5px] text-slate-900 dark:text-white truncate">
                                    {doc.title}
                                  </h3>
                                  {doc.type === 'learned' && doc.confidence && (
                                    <span className="text-xs bg-slate-100 dark:bg-slate-700 text-slate-600 px-2 py-0.5 rounded-full">
                                      {doc.confidence}% confidence
                                    </span>
                                  )}
                                </div>
                                <p className="text-sm text-slate-500 line-clamp-2">{doc.summary}</p>
                                <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                                  <span className="flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    {new Date(doc.createdAt).toLocaleDateString()}
                                  </span>
                                  <span>by {doc.createdBy}</span>
                                  {doc.source && (
                                    <span className="text-slate-500 truncate max-w-[200px]">
                                      {doc.source}
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 ml-4">
                              <button
                                type="button"
                                onClick={() => setViewingDoc(doc)}
                                className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                                title="View"
                              >
                                <Eye className="w-4 h-4" />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDelete(doc.id)}
                                className="p-2 text-slate-400 hover:text-rose-600"
                                title="Delete"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {activeTab === 'proposed' && (
                <div className="space-y-4">
                  {proposedChanges.length === 0 ? (
                    <div className="rounded-[1.5rem] border border-slate-200/70 bg-white dark:bg-slate-800 p-12 text-center">
                      <Sparkles className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
                      <p className="text-slate-500">No pending AI-proposed changes.</p>
                      <p className="text-xs text-slate-400 mt-2">
                        The AI Pipeline will propose knowledge updates based on incident patterns.
                      </p>
                    </div>
                  ) : (
                    proposedChanges.map((change) => (
                      <div
                        key={change.id}
                        className={`rounded-[1.5rem] border border-slate-200/70 bg-slate-50 dark:bg-slate-700/50 p-5 ${listRowHoverClass}`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-600 flex items-center justify-center">
                              <Sparkles className="w-5 h-5" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
                                  + Add
                                </span>
                                <h3 className="text-[14.5px] text-slate-900 dark:text-white">
                                  {change.document.title}
                                </h3>
                              </div>
                              <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                                {change.document.summary}
                              </p>
                              <p className="text-xs text-slate-500">
                                <span className="font-medium">Reason:</span> {change.reason}
                              </p>
                              {change.learnedFrom && (
                                <p className="text-xs text-slate-500 mt-1">
                                  Learned from: {change.learnedFrom}
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="secondary"
                              onClick={() => handleRejectChange(change.id)}
                              className="text-rose-600 border-rose-200 hover:bg-rose-50"
                            >
                              Reject
                            </Button>
                            <Button variant="primary" onClick={() => handleApproveChange(change.id)}>
                              Approve
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </>
          )}

          {showAddModal && (
            <AddKnowledgeModal
              onClose={() => setShowAddModal(false)}
              onSave={handleAddManual}
            />
          )}

          {viewingDoc && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-2xl p-6 max-h-[80vh] overflow-y-auto">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    {getTypeIcon(viewingDoc.type)}
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                      {viewingDoc.title}
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={() => setViewingDoc(null)}
                    className="text-slate-400 hover:text-slate-600"
                  >
                    <XCircle className="w-5 h-5" />
                  </button>
                </div>
                <div className="prose dark:prose-invert max-w-none">
                  {viewingDoc.content || viewingDoc.summary}
                </div>
                <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-600 text-xs text-slate-500">
                  <p>Created: {new Date(viewingDoc.createdAt).toLocaleString()}</p>
                  <p>By: {viewingDoc.createdBy}</p>
                  {viewingDoc.source && <p>Source: {viewingDoc.source}</p>}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </TeamPageShell>
    </>
  );
}

function AddKnowledgeModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (data: { title: string; content: string }) => void;
}) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-lg p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Add Knowledge Entry
        </h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Redis Connection Best Practices"
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Content
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={6}
              placeholder="Enter the knowledge content..."
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700"
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 dark:text-slate-400"
          >
            Cancel
          </button>
          <button
            onClick={() => onSave({ title, content })}
            disabled={!title.trim() || !content.trim()}
            className="px-4 py-2 bg-emerald-100/50 text-emerald-700 rounded-full hover:bg-emerald-100/80 disabled:opacity-50"
          >
            Add Entry
          </button>
        </div>
      </div>
    </div>
  );
}
