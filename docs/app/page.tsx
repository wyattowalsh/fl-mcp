import Link from 'next/link';

const cards = [
  {
    title: 'Getting Started',
    href: '/docs/getting-started',
    description: 'Bootstrapping FL MCP quickly and safely.'
  },
  {
    title: 'Reference',
    href: '/docs/reference/api-schema',
    description: 'Schema + public API inventory generated from source.'
  },
  {
    title: 'Client Setup',
    href: '/docs/clients',
    description: 'Configure Claude Code, Codex, Gemini CLI, and Copilot.'
  }
];

export default function LandingPage() {
  return (
    <main className="landing">
      <section>
        <p className="eyebrow">FL Studio MCP</p>
        <h1>Docs Hub</h1>
        <p>
          A documentation app built with Fumadocs + pnpm, including curated guides,
          references, provider instructions, and AI workflow playbooks.
        </p>
      </section>
      <section className="card-grid">
        {cards.map((card) => (
          <Link key={card.href} href={card.href} className="card">
            <h2>{card.title}</h2>
            <p>{card.description}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
