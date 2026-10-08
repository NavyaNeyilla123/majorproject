import React from 'react';
import { Lightbulb, PlayCircle, CheckCircle } from 'lucide-react';

export default function Recommendations({ recommendations, onTriggerAction }) {
  if (!recommendations || recommendations.length === 0) return null;

  return (
    <div className="glass-card" style={{ padding: '24px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <Lightbulb size={20} color="#F59E0B" />
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, color: '#F3F4F6' }}>
          Recommended Unblocking Actions
        </h3>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {recommendations.map((rec, idx) => (
          <div 
            key={rec.id || idx} 
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              padding: '14px 18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexWrap: 'wrap'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', flex: 1 }}>
              <span className={`badge ${rec.priority === 'High' ? 'badge-high' : 'badge-medium'}`} style={{ marginTop: '2px' }}>
                {rec.priority}
              </span>
              <p style={{ fontSize: '0.9rem', color: '#F3F4F6', margin: 0, fontWeight: 500 }}>
                {rec.text}
              </p>
            </div>

            {rec.action_type && (
              <button
                onClick={() => onTriggerAction(rec)}
                className="btn-secondary"
                style={{ fontSize: '0.8rem', background: 'rgba(59, 130, 246, 0.1)', borderColor: '#3B82F6', color: '#60A5FA' }}
              >
                <PlayCircle size={14} />
                <span>Execute Workflow</span>
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
