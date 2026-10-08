import React from 'react';
import { Search, Bell, ChevronDown } from 'lucide-react';
import { KnowledgeOpsLogo } from './Icons';

export default function Topbar({ navigateTo }) {
  return (
    <header style={{
      height: '56px',
      background: '#FFFFFF',
      borderBottom: '1px solid #E2E8F0',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      position: 'sticky',
      top: 0,
      zIndex: 9
    }}>
      {/* Left: Logo */}
      <div 
        onClick={() => navigateTo('dashboard')}
        style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}
      >
        <KnowledgeOpsLogo size={24} />
        <span style={{ fontWeight: 800, fontSize: '1rem', color: '#0F172A', letterSpacing: '-0.2px' }}>
          KnowledgeOps AI
        </span>
      </div>

      {/* Center: Search Bar */}
      <div style={{ position: 'relative', width: '380px' }}>
        <Search size={15} color="#94A3B8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
        <input 
          type="text" 
          placeholder="Search projects, evidence, or conversations"
          style={{
            width: '100%',
            padding: '6px 36px 6px 34px',
            background: '#F8FAFC',
            border: '1px solid #E2E8F0',
            borderRadius: '6px',
            fontSize: '0.8rem',
            color: '#0F172A',
            outline: 'none'
          }}
        />
        <span style={{
          position: 'absolute',
          right: '10px',
          top: '50%',
          transform: 'translateY(-50%)',
          fontSize: '0.675rem',
          fontWeight: 600,
          color: '#94A3B8',
          background: '#FFFFFF',
          border: '1px solid #E2E8F0',
          padding: '1px 5px',
          borderRadius: '4px'
        }}>
          ⌘ K
        </span>
      </div>

      {/* Right Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
        {/* Status Pill */}
        <div 
          onClick={() => navigateTo('mcp')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.75rem',
            fontWeight: 600,
            color: '#059669',
            background: '#ECFDF5',
            padding: '4px 10px',
            borderRadius: '16px',
            border: '1px solid #A7F3D0',
            cursor: 'pointer'
          }}
        >
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10B981' }}></span>
          2 MCP connections live
        </div>

        {/* Bell Icon */}
        <div style={{ position: 'relative', cursor: 'pointer', color: '#64748B' }}>
          <Bell size={18} />
          <span style={{
            position: 'absolute',
            top: '-2px',
            right: '-2px',
            width: '7px',
            height: '7px',
            background: '#2563EB',
            borderRadius: '50%',
            border: '2px solid #FFFFFF'
          }}></span>
        </div>

        {/* User Profile */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: '#DDD6FE',
            color: '#7C3AED',
            fontWeight: 700,
            fontSize: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            AS
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.8rem', color: '#0F172A', lineHeight: '1.1' }}>
              Alex Shah
            </div>
            <div style={{ fontSize: '0.675rem', color: '#64748B' }}>
              Project Manager
            </div>
          </div>
          <ChevronDown size={14} color="#64748B" />
        </div>
      </div>
    </header>
  );
}
