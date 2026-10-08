import React from 'react';
import { AlertTriangle, TrendingDown, ShieldAlert } from 'lucide-react';

export default function RootCauseImpact({ rootCause, impact, risk }) {
  const getRiskBadge = (r) => {
    if (!r) return <span className="badge badge-high">High Risk</span>;
    if (r.toLowerCase().includes('high')) return <span className="badge badge-high">High Risk</span>;
    return <span className="badge badge-medium">Medium Risk</span>;
  };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
      gap: '20px',
      marginBottom: '24px'
    }}>
      {/* Root Cause Card */}
      <div className="glass-card" style={{
        padding: '20px',
        borderTop: '3px solid #F43F5E',
        background: 'linear-gradient(180deg, rgba(244, 63, 94, 0.05) 0%, rgba(17, 23, 38, 0.95) 100%)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <AlertTriangle size={18} color="#F43F5E" />
          <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#F43F5E', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
            Root Cause Identified
          </h4>
        </div>
        <p style={{ fontSize: '0.92rem', color: '#F3F4F6', fontWeight: 600, lineHeight: '1.5', margin: 0 }}>
          {rootCause || "Analyzing core root cause..."}
        </p>
      </div>

      {/* Impact & Risk Card */}
      <div className="glass-card" style={{
        padding: '20px',
        borderTop: '3px solid #F59E0B',
        background: 'linear-gradient(180deg, rgba(245, 158, 11, 0.05) 0%, rgba(17, 23, 38, 0.95) 100%)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingDown size={18} color="#F59E0B" />
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#F59E0B', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
              Project Impact & Risk
            </h4>
          </div>
          {getRiskBadge(risk)}
        </div>
        <p style={{ fontSize: '0.88rem', color: '#E5E7EB', lineHeight: '1.5', margin: 0 }}>
          {impact || "Evaluating downstream project dependencies..."}
        </p>
      </div>
    </div>
  );
}
