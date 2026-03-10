import type { Metadata } from 'next';
import { RootProvider } from 'fumadocs-ui/provider';
import './global.css';

export const metadata: Metadata = {
  title: 'FL MCP Documentation',
  description: 'Operational docs for FL Studio MCP and associated tooling.'
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
