import React from 'react';
import { 
  LayoutGrid, 
  Sparkles, 
  Briefcase, 
  FileText, 
  BarChart3, 
  Workflow, 
  Plug, 
  SlidersHorizontal, 
  Settings, 
  ChevronsUpDown,
  HelpCircle,
  ArrowUpRight
} from 'lucide-react';
import { GitHubIcon, GmailIcon } from './Icons';
import { githubService } from '../services/githubService';
import useCacheTick from '../hooks/useCacheTick';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function shortDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.slice(0, 10).split('-').map(Number);
  if (!m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}`;
}

export default function Sidebar({ currentRoute, navigateTo }) {
  useCacheTick();
  const ghConn = githubService.getConnectionStatus();
  const ghRepos = githubService.getRepositories();
  const ghIndexedIso = ghRepos.map(r => r.synced_at || '').filter(Boolean).sort().pop() || '';
  const knowledgeUpToDate = githubService.isLoaded() && ghConn.badge === 'Connected';
  const navGroups = [
    {
      title: 'WORKSPACE',
      items: [
        { id: 'dashboard', label: 'Dashboard', icon: LayoutGrid },
        { id: 'ask', label: 'Ask KnowledgeOps', icon: Sparkles },
        { id: 'project-details', label: 'Projects', icon: Briefcase },
      ]
    },
    {
      title: 'KNOWLEDGE',
      items: [
        { id: 'github', label: 'GitHub', icon: GitHubIcon },
        { id: 'gmail', label: 'Gmail', icon: GmailIcon },
        { id: 'evidence', label: 'Evidence', icon: FileText },
        { id: 'reports', label: 'Reports', icon: BarChart3 },
      ]
    },
    {
      title: 'OPERATIONS',
      items: [
        { id: 'workflows', label: 'Workflows', icon: Workflow },
        { id: 'mcp', label: 'MCP Connections', icon: Plug },
        { id: 'evaluation', label: 'Evaluation', icon: SlidersHorizontal },
      ]
    },
  ];

  return (
    <aside style={{
      width: '240px',
      height: '100vh',
      position: 'sticky',
      top: 0,
      background: '#FFFFFF',
      borderRight: '1px solid #E2E8F0',
      display: 'flex',
      flexDirection: 'column',
      justify: 'space-between',
      zIndex: 10,
      flexShrink: 0
    }}>
      {/* Top Workspace Selector */}
      <div style={{ padding: '16px 12px 12px 12px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 10px',
          borderRadius: '8px',
          background: '#F8FAFC',
          border: '1px solid #E2E8F0',
          cursor: 'pointer'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              background: '#F3E8FF',
              color: '#7C3AED',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              A
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '0.825rem', color: '#0F172A', lineHeight: '1.2' }}>
                Acme Engineering
              </div>
              <div style={{ fontSize: '0.7rem', color: '#64748B' }}>
                Enterprise workspace
              </div>
            </div>
          </div>
          <ChevronsUpDown size={16} color="#64748B" />
        </div>
      </div>

      {/* Nav List */}
      <div style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }}>
        {navGroups.map((group, gIdx) => (
          <div key={gIdx} style={{ marginBottom: '20px' }}>
            <div style={{
              fontSize: '0.675rem',
              fontWeight: 700,
              color: '#94A3B8',
              letterSpacing: '0.5px',
              marginBottom: '8px',
              paddingLeft: '8px'
            }}>
              {group.title}
            </div>
            {group.items.map((item) => {
              const IconComp = item.icon;
              const isActive = currentRoute === item.id || 
                (item.id === 'ask' && currentRoute === 'answer');
              return (
                <div
                  key={item.id}
                  onClick={() => navigateTo(item.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    fontSize: '0.825rem',
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? '#2563EB' : '#475569',
                    background: isActive ? '#EFF6FF' : 'transparent',
                    cursor: 'pointer',
                    marginBottom: '2px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <IconComp size={16} color={isActive ? '#2563EB' : '#64748B'} />
                  <span>{item.label}</span>
                </div>
              );
            })}
          </div>
        ))}

        {/* Settings Item */}
        <div
          onClick={() => navigateTo('settings')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '8px 10px',
            borderRadius: '6px',
            fontSize: '0.825rem',
            fontWeight: currentRoute === 'settings' ? 600 : 500,
            color: currentRoute === 'settings' ? '#2563EB' : '#475569',
            background: currentRoute === 'settings' ? '#EFF6FF' : 'transparent',
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
        >
          <Settings size={16} color={currentRoute === 'settings' ? '#2563EB' : '#64748B'} />
          <span>Settings</span>
        </div>
      </div>

      {/* Bottom Knowledge Status Card */}
      <div style={{ padding: '12px', borderTop: '1px solid #F1F5F9' }}>
        <div style={{
          padding: '12px',
          borderRadius: '8px',
          background: '#F8FAFC',
          border: '1px solid #E2E8F0',
          fontSize: '0.725rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: knowledgeUpToDate ? '#059669' : '#D97706', marginBottom: '4px' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: knowledgeUpToDate ? '#10B981' : '#F59E0B', display: 'inline-block' }}></span>
            {knowledgeUpToDate ? 'Knowledge is up to date' : 'Sync pending — check connections'}
          </div>
          <div style={{ color: '#64748B', marginBottom: '6px' }}>
            {ghIndexedIso
              ? `Last indexed ${shortDate(ghIndexedIso)} at ${ghConn.synced}`
              : 'Not indexed yet'}
          </div>
          <div 
            onClick={() => navigateTo('mcp')}
            style={{ 
              color: '#2563EB', 
              fontWeight: 600, 
              display: 'flex', 
              alignItems: 'center', 
              gap: '4px',
              cursor: 'pointer' 
            }}
          >
            RAG index ready <ArrowUpRight size={12} />
          </div>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginTop: '12px',
          paddingLeft: '4px',
          fontSize: '0.75rem',
          color: '#64748B',
          cursor: 'pointer'
        }}>
          <HelpCircle size={14} color="#64748B" />
          <span>Help & documentation</span>
        </div>
      </div>
    </aside>
  );
}
