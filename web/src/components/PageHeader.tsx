import type { LucideIcon } from 'lucide-react';

// Shared hero header for content pages — eyebrow label + large title + subtitle,
// matching the dashboard's hierarchy. Keeps every screen consistent for the demo.
export function PageHeader({ icon: Icon, eyebrow, title, subtitle, right }: {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11.5, fontWeight: 600, color: 'var(--accent)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          <Icon size={14} strokeWidth={2.2} />
          {eyebrow}
        </div>
        <h1 style={{ fontSize: 30, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
          {title}
        </h1>
        {subtitle && <p style={{ color: 'var(--text-secondary)', marginTop: 8, fontSize: 14.5 }}>{subtitle}</p>}
      </div>
      {right && <div>{right}</div>}
    </div>
  );
}

const PAGE_WRAP: React.CSSProperties = { padding: '32px 48px 64px', maxWidth: 1440, margin: '0 auto' };
export function PageWrap({ children, maxWidth }: { children: React.ReactNode; maxWidth?: number }) {
  return <div style={{ ...PAGE_WRAP, maxWidth: maxWidth ?? 1440 }}>{children}</div>;
}
