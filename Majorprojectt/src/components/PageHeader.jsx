import React from 'react';

export default function PageHeader({ 
  breadcrumb = [], 
  title, 
  subtitle, 
  actions,
  date = "Wednesday, October 7, 2026"
}) {
  return (
    <div style={{ marginBottom: '24px' }}>
      {/* Top Breadcrumb & Date row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '8px',
        fontSize: '0.75rem',
        color: '#64748B'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {breadcrumb.map((item, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && <span>/</span>}
              <span style={{ color: idx === breadcrumb.length - 1 ? '#0F172A' : '#64748B', fontWeight: idx === breadcrumb.length - 1 ? 600 : 400 }}>
                {item}
              </span>
            </React.Fragment>
          ))}
        </div>
        <div style={{ fontWeight: 500 }}>
          {date}
        </div>
      </div>

      {/* Main Title & Action Row */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '20px'
      }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.3px', lineHeight: '1.2' }}>
            {title}
          </h1>
          {subtitle && (
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginTop: '4px' }}>
              {subtitle}
            </p>
          )}
        </div>

        {actions && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
