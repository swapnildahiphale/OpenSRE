/**
 * OpenSRE Config Service - Admin UI
 * Visual tree-based organization management
 */

// ============================================================================
// DOM Elements
// ============================================================================
const qs = id => document.getElementById(id);

const adminTokenEl = qs("adminToken");
const orgIdEl = qs("orgId");
const statusEl = qs("status");
const treeContainer = qs("treeContainer");
const tokensList = qs("tokensList");
const teamForTokensEl = qs("teamForTokens");

// Buttons
const connectBtn = qs("connectBtn");
const refreshTreeBtn = qs("refreshTreeBtn");
const addNodeBtn = qs("addNodeBtn");
const issueTokenBtn = qs("issueTokenBtn");

// Node panel
const nodePanel = qs("nodePanel");
const closePanelBtn = qs("closePanelBtn");
const panelNodeName = qs("panelNodeName");
const panelNodeType = qs("panelNodeType");
const panelNodeId = qs("panelNodeId");
const panelParentId = qs("panelParentId");
const panelCreatedAt = qs("panelCreatedAt");
const panelAddChildBtn = qs("panelAddChildBtn");
const panelEditBtn = qs("panelEditBtn");
const panelConfigBtn = qs("panelConfigBtn");
const panelTokensBtn = qs("panelTokensBtn");

// Add node modal
const addNodeModal = qs("addNodeModal");
const newNodeId = qs("newNodeId");
const newNodeName = qs("newNodeName");
const newNodeParent = qs("newNodeParent");
const newNodeType = qs("newNodeType");
const cancelAddNodeBtn = qs("cancelAddNodeBtn");
const confirmAddNodeBtn = qs("confirmAddNodeBtn");

// Edit node modal
const editNodeModal = qs("editNodeModal");
const editNodeIdEl = qs("editNodeId");
const editNodeNameEl = qs("editNodeName");
const editNodeParentEl = qs("editNodeParent");
const cancelEditNodeBtn = qs("cancelEditNodeBtn");
const confirmEditNodeBtn = qs("confirmEditNodeBtn");

// Config modal
const configModal = qs("configModal");
const configNodeIdEl = qs("configNodeId");
const effectiveConfigPre = qs("effectiveConfigPre");
const configPatchTa = qs("configPatchTa");
const cancelConfigBtn = qs("cancelConfigBtn");
const saveConfigBtn = qs("saveConfigBtn");

// ============================================================================
// State
// ============================================================================
let allNodes = [];
let nodeTree = [];
let selectedNode = null;

// ============================================================================
// Helpers
// ============================================================================
function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = "status" + (kind ? ` ${kind}` : "");
}

function orgId() { 
  return (orgIdEl.value || "").trim(); 
}

function adminHeaders() {
  let t = (adminTokenEl.value || "");
  t = t.replace(/^Bearer\s+/i, "");
  t = t.normalize("NFKC");
  t = t.replace(/[\u200B-\u200D\uFEFF]/g, "");
  t = t.replace(/[\u2010-\u2015\u2212]/g, "-");
  t = t.replace(/^["']+|["']+$/g, "");
  t = t.replace(/\s+/g, "");
  return { "Authorization": `Bearer ${t}` };
}

async function fetchJson(url, opts = {}) {
  const resp = await fetch(url, opts);
  const text = await resp.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* ignore */ }
  if (!resp.ok) {
    const detail = data?.detail || text || `HTTP ${resp.status}`;
    throw new Error(detail);
  }
  return data;
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

// ============================================================================
// Tree Building
// ============================================================================
function buildTree(nodes) {
  const byId = {};
  for (const n of nodes) {
    byId[n.node_id] = { ...n, children: [] };
  }
  const roots = [];
  for (const n of nodes) {
    const parent = n.parent_id ? byId[n.parent_id] : null;
    if (parent) {
      parent.children.push(byId[n.node_id]);
    } else {
      roots.push(byId[n.node_id]);
    }
  }
  // Sort children alphabetically
  const sortChildren = (node) => {
    node.children.sort((a, b) => a.node_id.localeCompare(b.node_id));
    node.children.forEach(sortChildren);
  };
  roots.forEach(sortChildren);
  roots.sort((a, b) => a.node_id.localeCompare(b.node_id));
  return roots;
}

// ============================================================================
// Tree Visualization (SVG)
// ============================================================================
function renderTree(roots) {
  if (!roots || roots.length === 0) {
    treeContainer.innerHTML = `
      <div style="text-align:center; color:var(--muted); padding:40px;">
        No nodes found. Click "+ Add Node" to create the first node.
      </div>`;
    return;
  }

  // Calculate tree layout
  const nodeWidth = 120;
  const nodeHeight = 36;
  const levelGap = 60;
  const siblingGap = 20;

  // Assign positions to each node
  let positions = new Map();
  let maxX = 0;
  let maxY = 0;

  function layoutTree(node, level, startX) {
    if (node.children.length === 0) {
      positions.set(node.node_id, { x: startX, y: level * levelGap, node });
      maxX = Math.max(maxX, startX + nodeWidth);
      maxY = Math.max(maxY, level * levelGap + nodeHeight);
      return startX + nodeWidth + siblingGap;
    }

    let childX = startX;
    for (const child of node.children) {
      childX = layoutTree(child, level + 1, childX);
    }

    // Center parent above children
    const firstChild = positions.get(node.children[0].node_id);
    const lastChild = positions.get(node.children[node.children.length - 1].node_id);
    const centerX = (firstChild.x + lastChild.x) / 2;
    
    positions.set(node.node_id, { x: centerX, y: level * levelGap, node });
    maxX = Math.max(maxX, centerX + nodeWidth);
    maxY = Math.max(maxY, level * levelGap + nodeHeight);
    
    return childX;
  }

  let currentX = 20;
  for (const root of roots) {
    currentX = layoutTree(root, 0, currentX);
  }

  const svgWidth = maxX + 40;
  const svgHeight = maxY + 40;

  // Build SVG
  let edgesHtml = '';
  let nodesHtml = '';

  positions.forEach((pos, nodeId) => {
    const n = pos.node;
    
    // Draw edge to parent
    if (n.parent_id && positions.has(n.parent_id)) {
      const parentPos = positions.get(n.parent_id);
      const startX = parentPos.x + nodeWidth / 2;
      const startY = parentPos.y + nodeHeight;
      const endX = pos.x + nodeWidth / 2;
      const endY = pos.y;
      const midY = startY + (endY - startY) / 2;
      
      edgesHtml += `<path class="tree-edge" d="M${startX},${startY} C${startX},${midY} ${endX},${midY} ${endX},${endY}" />`;
    }

    // Draw node
    const displayName = n.name || n.node_id;
    const truncatedName = displayName.length > 14 ? displayName.slice(0, 12) + '…' : displayName;
    
    nodesHtml += `
      <g class="tree-node ${n.node_type}" data-node-id="${n.node_id}" transform="translate(${pos.x}, ${pos.y})">
        <rect class="node-bg" width="${nodeWidth}" height="${nodeHeight}" />
        <text x="${nodeWidth/2}" y="${nodeHeight/2 + 4}" text-anchor="middle">${truncatedName}</text>
      </g>
    `;
  });

  treeContainer.innerHTML = `
    <svg class="tree-svg" width="${svgWidth}" height="${svgHeight}" viewBox="0 0 ${svgWidth} ${svgHeight}">
      <g class="edges">${edgesHtml}</g>
      <g class="nodes">${nodesHtml}</g>
    </svg>
  `;

  // Add click handlers to nodes
  treeContainer.querySelectorAll('.tree-node').forEach(el => {
    el.addEventListener('click', (e) => {
      const nodeId = el.dataset.nodeId;
      const node = allNodes.find(n => n.node_id === nodeId);
      if (node) showNodePanel(node);
    });
  });
}

// ============================================================================
// Node Panel
// ============================================================================
function showNodePanel(node) {
  selectedNode = node;
  
  panelNodeName.textContent = node.name || node.node_id;
  panelNodeType.textContent = node.node_type;
  panelNodeType.className = `pill ${node.node_type}`;
  panelNodeId.textContent = node.node_id;
  panelParentId.textContent = node.parent_id || '(root)';
  panelCreatedAt.textContent = node.created_at ? new Date(node.created_at).toLocaleString() : '-';
  
  // Show/hide tokens button based on node type
  panelTokensBtn.style.display = node.node_type === 'team' ? 'inline-block' : 'none';
  
  nodePanel.classList.add('show');
}

function hideNodePanel() {
  nodePanel.classList.remove('show');
  selectedNode = null;
}

// ============================================================================
// Modals
// ============================================================================
function showAddNodeModal(parentId = null) {
  newNodeId.value = '';
  newNodeName.value = '';
  newNodeType.value = 'team';
  
  // Populate parent dropdown
  newNodeParent.innerHTML = '';
  for (const n of allNodes) {
    const opt = document.createElement('option');
    opt.value = n.node_id;
    opt.textContent = `${n.node_id} (${n.node_type})`;
    if (n.node_id === parentId) opt.selected = true;
    newNodeParent.appendChild(opt);
  }
  
  addNodeModal.classList.add('show');
}

function hideAddNodeModal() {
  addNodeModal.classList.remove('show');
}

function showEditNodeModal(node) {
  editNodeIdEl.value = node.node_id;
  editNodeNameEl.value = node.name || '';
  
  // Populate parent dropdown (exclude self and descendants)
  const descendants = new Set();
  const collectDescendants = (n) => {
    descendants.add(n.node_id);
    (n.children || []).forEach(collectDescendants);
  };
  const nodeWithChildren = nodeTree.find(n => n.node_id === node.node_id) || 
    allNodes.find(n => n.node_id === node.node_id);
  if (nodeWithChildren) collectDescendants(nodeWithChildren);
  
  editNodeParentEl.innerHTML = '<option value="">(root - no parent)</option>';
  for (const n of allNodes) {
    if (descendants.has(n.node_id)) continue; // Can't be own descendant
    const opt = document.createElement('option');
    opt.value = n.node_id;
    opt.textContent = `${n.node_id} (${n.node_type})`;
    if (n.node_id === node.parent_id) opt.selected = true;
    editNodeParentEl.appendChild(opt);
  }
  
  editNodeModal.classList.add('show');
}

function hideEditNodeModal() {
  editNodeModal.classList.remove('show');
}

async function showConfigModal(node) {
  configNodeIdEl.textContent = node.node_id;
  effectiveConfigPre.textContent = 'Loading...';
  configPatchTa.value = '{}';
  
  configModal.classList.add('show');
  
  try {
    // Load effective config
    const effective = await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/nodes/${encodeURIComponent(node.node_id)}/effective`,
      { headers: adminHeaders() }
    );
    effectiveConfigPre.textContent = pretty(effective?.config || {});
    
    // Load raw (local) config
    const raw = await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/nodes/${encodeURIComponent(node.node_id)}/raw`,
      { headers: adminHeaders() }
    );
    configPatchTa.value = pretty(raw?.config || {});
  } catch (e) {
    effectiveConfigPre.textContent = `Error: ${e.message}`;
  }
}

function hideConfigModal() {
  configModal.classList.remove('show');
}

// ============================================================================
// API Actions
// ============================================================================
async function loadOrgTree() {
  try {
    const nodes = await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/nodes`,
      { headers: adminHeaders() }
    );
    allNodes = nodes || [];
    nodeTree = buildTree(allNodes);
    renderTree(nodeTree);
    updateTeamDropdown();
    setStatus(`Connected (${allNodes.length} nodes)`, 'ok');
  } catch (e) {
    setStatus(`Error: ${e.message}`, 'err');
    treeContainer.innerHTML = `<div style="text-align:center; color:var(--danger); padding:40px;">Failed to load: ${e.message}</div>`;
  }
}

function updateTeamDropdown() {
  teamForTokensEl.innerHTML = '<option value="">Select team...</option>';
  for (const n of allNodes) {
    if (n.node_type === 'team') {
      const opt = document.createElement('option');
      opt.value = n.node_id;
      opt.textContent = n.name || n.node_id;
      teamForTokensEl.appendChild(opt);
    }
  }
}

async function createNode() {
  const body = {
    node_id: newNodeId.value.trim(),
    parent_id: newNodeParent.value || null,
    node_type: newNodeType.value,
    name: newNodeName.value.trim() || null,
  };
  
  if (!body.node_id) {
    alert('Node ID is required');
    return;
  }

  try {
    await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/nodes`,
      {
        method: 'POST',
        headers: { ...adminHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      }
    );
    hideAddNodeModal();
    await loadOrgTree();
    setStatus('Node created successfully', 'ok');
  } catch (e) {
    alert(`Failed to create node: ${e.message}`);
  }
}

async function updateNode() {
  const nodeId = editNodeIdEl.value;
  const body = {};
  
  const name = editNodeNameEl.value.trim();
  const parentId = editNodeParentEl.value;
  
  if (name) body.name = name;
  if (parentId !== undefined) body.parent_id = parentId || null;
  
  try {
    await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/nodes/${encodeURIComponent(nodeId)}`,
      {
        method: 'PATCH',
        headers: { ...adminHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      }
    );
    hideEditNodeModal();
    hideNodePanel();
    await loadOrgTree();
    setStatus('Node updated successfully', 'ok');
  } catch (e) {
    alert(`Failed to update node: ${e.message}`);
  }
}

async function saveConfig() {
  const nodeId = configNodeIdEl.textContent;
  let patch = {};
  
  try {
    patch = JSON.parse(configPatchTa.value || '{}');
  } catch (e) {
    alert(`Invalid JSON: ${e.message}`);
    return;
  }
  
  try {
    await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/nodes/${encodeURIComponent(nodeId)}/config`,
      {
        method: 'PUT',
        headers: { ...adminHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ patch }),
      }
    );
    hideConfigModal();
    setStatus('Config saved successfully', 'ok');
  } catch (e) {
    alert(`Failed to save config: ${e.message}`);
  }
}

async function loadTokens(teamNodeId) {
  if (!teamNodeId) {
    tokensList.innerHTML = '<div class="small" style="padding:10px;">Select a team to view tokens</div>';
    return;
  }
  
  try {
    const tokens = await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/teams/${encodeURIComponent(teamNodeId)}/tokens`,
      { headers: adminHeaders() }
    );
    renderTokensList(tokens || []);
  } catch (e) {
    tokensList.innerHTML = `<div class="small" style="color:var(--danger); padding:10px;">Error: ${e.message}</div>`;
  }
}

function renderTokensList(tokens) {
  if (!tokens || tokens.length === 0) {
    tokensList.innerHTML = '<div class="small" style="padding:10px; color:var(--muted);">No tokens issued for this team</div>';
    return;
  }
  
  tokensList.innerHTML = tokens.map(t => `
    <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 12px; background:#0f1630; border-radius:8px; margin-bottom:8px;">
      <div>
        <div style="font-size:12px; font-family:monospace;">${t.token_id}</div>
        <div class="small">${t.revoked_at ? `Revoked: ${new Date(t.revoked_at).toLocaleString()}` : 'Active'}</div>
      </div>
      ${!t.revoked_at ? `<button class="danger" onclick="revokeToken('${t.token_id}')" style="padding:6px 10px; font-size:11px;">Revoke</button>` : ''}
    </div>
  `).join('');
}

async function issueToken() {
  const teamNodeId = teamForTokensEl.value;
  if (!teamNodeId) {
    alert('Please select a team first');
    return;
  }
  
  try {
    const result = await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/teams/${encodeURIComponent(teamNodeId)}/tokens`,
      { method: 'POST', headers: adminHeaders() }
    );
    alert(`New token issued!\n\nCopy this now (shown only once):\n\n${result.token}`);
    await loadTokens(teamNodeId);
  } catch (e) {
    alert(`Failed to issue token: ${e.message}`);
  }
}

window.revokeToken = async function(tokenId) {
  const teamNodeId = teamForTokensEl.value;
  if (!confirm(`Revoke token ${tokenId}? This will immediately invalidate it.`)) return;
  
  try {
    await fetchJson(
      `/api/v1/admin/orgs/${encodeURIComponent(orgId())}/teams/${encodeURIComponent(teamNodeId)}/tokens/${encodeURIComponent(tokenId)}/revoke`,
      { method: 'POST', headers: adminHeaders() }
    );
    await loadTokens(teamNodeId);
  } catch (e) {
    alert(`Failed to revoke token: ${e.message}`);
  }
};

// ============================================================================
// Event Listeners
// ============================================================================
connectBtn?.addEventListener('click', loadOrgTree);
refreshTreeBtn?.addEventListener('click', loadOrgTree);
addNodeBtn?.addEventListener('click', () => showAddNodeModal());

closePanelBtn?.addEventListener('click', hideNodePanel);
panelAddChildBtn?.addEventListener('click', () => {
  if (selectedNode) {
    hideNodePanel();
    showAddNodeModal(selectedNode.node_id);
  }
});
panelEditBtn?.addEventListener('click', () => {
  if (selectedNode) {
    hideNodePanel();
    showEditNodeModal(selectedNode);
  }
});
panelConfigBtn?.addEventListener('click', () => {
  if (selectedNode) {
    hideNodePanel();
    showConfigModal(selectedNode);
  }
});
panelTokensBtn?.addEventListener('click', () => {
  if (selectedNode && selectedNode.node_type === 'team') {
    teamForTokensEl.value = selectedNode.node_id;
    loadTokens(selectedNode.node_id);
    hideNodePanel();
  }
});

// Add node modal
cancelAddNodeBtn?.addEventListener('click', hideAddNodeModal);
confirmAddNodeBtn?.addEventListener('click', createNode);

// Edit node modal
cancelEditNodeBtn?.addEventListener('click', hideEditNodeModal);
confirmEditNodeBtn?.addEventListener('click', updateNode);

// Config modal
cancelConfigBtn?.addEventListener('click', hideConfigModal);
saveConfigBtn?.addEventListener('click', saveConfig);

// Team tokens dropdown
teamForTokensEl?.addEventListener('change', () => loadTokens(teamForTokensEl.value));
issueTokenBtn?.addEventListener('click', issueToken);

// Close modals on overlay click
addNodeModal?.addEventListener('click', (e) => { if (e.target === addNodeModal) hideAddNodeModal(); });
editNodeModal?.addEventListener('click', (e) => { if (e.target === editNodeModal) hideEditNodeModal(); });
configModal?.addEventListener('click', (e) => { if (e.target === configModal) hideConfigModal(); });

// Close panel on outside click
document.addEventListener('click', (e) => {
  if (nodePanel.classList.contains('show') && 
      !nodePanel.contains(e.target) && 
      !e.target.closest('.tree-node')) {
    hideNodePanel();
  }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    hideNodePanel();
    hideAddNodeModal();
    hideEditNodeModal();
    hideConfigModal();
  }
});
