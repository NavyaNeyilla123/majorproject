import React from 'react';
import { PieChart } from 'lucide-react';

export default function SourceBreakdown({ breakdown }) {
  const getSourceColor = (s) => {
    switch (s) {
      case 'Jira': return '#3B82F6';
      case 'GitHub': return '#A855F7';
      case 'Confluence': return '#10B981';
      case 'Slack': return '#F43F5E';
      default: return '#3B82F6';
    }
  };

  return (
    <div className="glass-card" style={{ padding: '20px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
        <PieChart size={18} color="#A855F7" />
        <h4 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
          Enterprise Evidence Source Breakdown
        </h4>
      </div>

      <div style={{ display: 'flex', height: '10px', borderRadius: '6px', overflow: 'hidden', marginBottom: '16px', background: 'var(--bg-input)' }}>
        {breakdown.map((b, idx) => (
          <div 
            key={idx} 
            style={{
              width: `${b.percentage}%`,
              background: getSourceColor(b.source),
              transition: 'width 0.4s ease'
            }} 
            title={`${b.source}: ${b.percentage}%`}
          />
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
        {breakdown.map((b, idx) => (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '3px', background: getSourceColor(b.source) }} />
            <span style={{ fontWeight: 600, color: '#F3F4F6' }}>{b.source}:</span>
            <span style={{ color: 'var(--text-muted)' }}>{b.count} ({b.percentage}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}
