import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import type { ReactNode } from 'react';
import { source } from '@/lib/source';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <DocsLayout
      tree={source.pageTree}
      nav={{
        title: 'FL MCP Docs',
        url: '/'
      }}
      links={[
        { text: 'Docs Home', url: '/docs' },
        { text: 'Providers', url: '/docs/providers' },
        { text: 'ADR Index', url: '/docs/adr' },
        { text: 'Roadmap', url: '/docs/roadmap' },
        { text: 'Contributing', url: '/docs/contributing' }
      ]}
    >
      {children}
    </DocsLayout>
  );
}
