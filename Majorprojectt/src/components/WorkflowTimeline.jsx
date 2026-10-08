import React from 'react';
import { GitBranch, CheckCircle2, Clock } from 'lucide-react';

export default function WorkflowTimeline({ workflow }) {
  if (!workflow || workflow.length === 0) return null;

  return (
    <div className="glass-card" style={{ padding: '24px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
        <GitBranch size={20} color="#8B5CF6" />
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#F3F4F6' }}>
          LangGraph Multi-Agent Workflow Execution
        </h3>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {workflow.map((step) => (
          <div 
            key={step.step_id} 
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              padding: '14px',
              position: 'relative'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{
                background: 'rgba(139, 92, 246, 0.15)',
                color: '#C084FC',
                padding: '2px 8px',
                borderRadius: '6px',
                fontSize: '0.72rem',
                fontWeight: 700
              }}>
                Step #{step.step_id}
              </span>
              <span style={{ fontSize: '0.72rem', color: '#10B981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={12} /> {step.status}
              </span>
            </div>

            <h4 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#F3F4F6', margin: '0 0 4px 0' }}>
              {step.agent}
            </h4>

            <p style={{ fontSize: '0.78rem', color: '#60A5FA', fontWeight: 600, margin: '0 0 6px 0' }}>
              {step.action}
            </p>

            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0, lineHeight: '1.4' }}>
              {step.details}
            </p>

            <div style={{ marginTop: '8px', fontSize: '0.7rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={11} /> {step.timestamp}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
