import { DocsBody, DocsDescription, DocsPage, DocsTitle } from 'fumadocs-ui/page';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { source } from '@/lib/source';

export async function generateMetadata(props: {
  params: Promise<{ slug?: string[] }>;
}): Promise<Metadata> {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) {
    return {};
  }

  const title = page.data.title;
  const description = page.data.description;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: 'article'
    },
    twitter: {
      card: 'summary',
      title,
      description
    }
  };
}

export default async function Page(props: {
  params: Promise<{ slug?: string[] }>;
}) {
  const params = await props.params;
  const page = source.getPage(params.slug);
  if (!page) notFound();

  const Mdx = page.data.body;

  return (
    <div id="main-content" tabIndex={-1}>
      <DocsPage toc={page.data.toc} full={false}>
        <DocsTitle>{page.data.title}</DocsTitle>
        <DocsDescription>{page.data.description}</DocsDescription>
        <DocsBody>
          <Mdx />
        </DocsBody>
      </DocsPage>
    </div>
  );
}

export async function generateStaticParams() {
  return source.generateParams();
}
