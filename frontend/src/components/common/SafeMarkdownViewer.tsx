import React from 'react';
import type { Citation } from '../../types';

interface SafeMarkdownViewerProps {
  content: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation) => void;
  className?: string;
}

/**
 * Pure React Markdown renderer that parses markdown line-by-line and token-by-token
 * without dangerouslySetInnerHTML.
 *
 * Guarantees:
 * - Headings (h1, h2, h3)
 * - Bold (**bold**) and Italic (*italic*)
 * - Inline code (`code`) and block code
 * - Unordered lists (- or *) and ordered lists (1.)
 * - Blockquotes (>)
 * - Interactive inline citation badges matching verified citations
 * - Safe markdown links (http/https only, no javascript: or data:)
 * - 100% XSS immunity (arbitrary HTML is escaped into plain text)
 */
export const SafeMarkdownViewer: React.FC<SafeMarkdownViewerProps> = ({
  content,
  citations = [],
  onCitationClick,
  className = '',
}) => {
  if (!content || !content.trim()) {
    return <p className="text-slate-400 italic text-sm">No explanation content available.</p>;
  }

  // Pre-index citations by reference (case-insensitive)
  const citationMap = new Map<string, Citation>();
  for (const c of citations) {
    if (c.source_reference) {
      citationMap.set(c.source_reference.trim().toUpperCase(), c);
    }
  }

  const renderInline = (text: string): React.ReactNode[] => {
    const nodes: React.ReactNode[] = [];
    let remaining = text;
    let keyIdx = 0;

    while (remaining.length > 0) {
      // 1. Bracketed citation or link: [text](url) or [REF-123]
      const bracketMatch = remaining.match(/\[([^\]]+)\](?:\(((?:[^()]+|\([^()]*\))*)\))?/);
      // 2. Bold text: **text**
      const boldMatch = remaining.match(/\*\*([^*]+)\*\*/);
      // 3. Inline code: `code`
      const codeMatch = remaining.match(/`([^`]+)`/);
      // 4. Italic text: *text*
      const italicMatch = remaining.match(/(?:^|[^*])\*([^*]+)\*/);

      // Find first matching token
      const matches = [
        bracketMatch ? { type: 'bracket', index: bracketMatch.index ?? -1, match: bracketMatch } : null,
        boldMatch ? { type: 'bold', index: boldMatch.index ?? -1, match: boldMatch } : null,
        codeMatch ? { type: 'code', index: codeMatch.index ?? -1, match: codeMatch } : null,
        italicMatch ? { type: 'italic', index: (italicMatch.index ?? -1) + (italicMatch[0].startsWith('*') ? 0 : 1), match: italicMatch } : null,
      ].filter((m): m is NonNullable<typeof m> => m !== null && m.index >= 0);

      if (matches.length === 0) {
        nodes.push(<span key={keyIdx++}>{remaining}</span>);
        break;
      }

      matches.sort((a, b) => a.index - b.index);
      const first = matches[0];

      // Text before match
      if (first.index > 0) {
        nodes.push(<span key={keyIdx++}>{remaining.slice(0, first.index)}</span>);
      }

      if (first.type === 'bracket') {
        const fullMatch = first.match[0];
        const label = first.match[1];
        const linkUrl = first.match[2];

        if (linkUrl) {
          // It's a markdown link [label](url)
          // Sanitize URL - only permit http://, https://, or relative /
          const isSafeUrl = /^(https?:\/\/|\/)/i.test(linkUrl.trim()) && !/^(javascript:|data:|vbscript:)/i.test(linkUrl.trim());
          if (isSafeUrl) {
            nodes.push(
              <a
                key={keyIdx++}
                href={linkUrl.trim()}
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-400 hover:text-teal-300 underline underline-offset-2 decoration-teal-500/50"
              >
                {label}
              </a>
            );
          } else {
            // Unsafe link protocol -> render as safe text
            nodes.push(<span key={keyIdx++}>[{label}]</span>);
          }
        } else {
          // Check if this bracketed label matches a citation
          const upperRef = label.trim().toUpperCase();
          const matchedCitation = citationMap.get(upperRef);

          if (matchedCitation && onCitationClick) {
            nodes.push(
              <button
                key={keyIdx++}
                type="button"
                onClick={() => onCitationClick(matchedCitation)}
                title={`Click to view ${matchedCitation.entity} record`}
                className="inline-flex items-center gap-1 mx-1 px-1.5 py-0.5 rounded bg-teal-500/15 border border-teal-500/30 text-teal-300 text-xs font-mono font-bold hover:bg-teal-500/25 transition cursor-pointer"
              >
                <span>[{label}]</span>
              </button>
            );
          } else {
            nodes.push(
              <span
                key={keyIdx++}
                className="font-mono text-xs font-semibold px-1 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 mx-0.5"
              >
                [{label}]
              </span>
            );
          }
        }

        remaining = remaining.slice(first.index + fullMatch.length);
      } else if (first.type === 'bold') {
        const fullMatch = first.match[0];
        const boldText = first.match[1];
        nodes.push(
          <strong key={keyIdx++} className="font-bold text-white tracking-wide">
            {boldText}
          </strong>
        );
        remaining = remaining.slice(first.index + fullMatch.length);
      } else if (first.type === 'code') {
        const fullMatch = first.match[0];
        const codeText = first.match[1];
        nodes.push(
          <code
            key={keyIdx++}
            className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-teal-300 font-mono text-xs"
          >
            {codeText}
          </code>
        );
        remaining = remaining.slice(first.index + fullMatch.length);
      } else if (first.type === 'italic') {
        const fullMatch = first.match[0].startsWith('*') ? first.match[0] : first.match[0].slice(1);
        const italicText = first.match[1];
        nodes.push(
          <em key={keyIdx++} className="italic text-slate-300">
            {italicText}
          </em>
        );
        remaining = remaining.slice(first.index + fullMatch.length);
      }
    }

    return nodes;
  };

  // Block level parser
  const lines = content.split('\n');
  const blocks: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeBlockLines: string[] = [];
  let currentListItems: React.ReactNode[] = [];
  let listType: 'ul' | 'ol' = 'ul';

  const flushList = (bKey: number) => {
    if (currentListItems.length > 0) {
      if (listType === 'ol') {
        blocks.push(
          <ol key={`ol-${bKey}`} className="list-decimal pl-5 space-y-1 my-2 text-slate-300">
            {currentListItems}
          </ol>
        );
      } else {
        blocks.push(
          <ul key={`ul-${bKey}`} className="list-disc pl-5 space-y-1 my-2 text-slate-300">
            {currentListItems}
          </ul>
        );
      }
      currentListItems = [];
    }
  };

  lines.forEach((line, lineIdx) => {
    const trimmed = line.trim();

    // Code block toggle
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        // Close code block
        blocks.push(
          <pre
            key={`pre-${lineIdx}`}
            className="p-3 my-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-teal-300 overflow-x-auto"
          >
            <code>{codeBlockLines.join('\n')}</code>
          </pre>
        );
        codeBlockLines = [];
        inCodeBlock = false;
      } else {
        flushList(lineIdx);
        inCodeBlock = true;
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      return;
    }

    // Unordered List item (- or *)
    const ulMatch = line.match(/^(\s*)[-*]\s+(.+)$/);
    if (ulMatch) {
      if (currentListItems.length > 0 && listType !== 'ul') {
        flushList(lineIdx);
      }
      listType = 'ul';
      currentListItems.push(
        <li key={`li-${lineIdx}`} className="leading-relaxed">
          {renderInline(ulMatch[2])}
        </li>
      );
      return;
    }

    // Ordered List item (1. )
    const olMatch = line.match(/^(\s*)\d+\.\s+(.+)$/);
    if (olMatch) {
      if (currentListItems.length > 0 && listType !== 'ol') {
        flushList(lineIdx);
      }
      listType = 'ol';
      currentListItems.push(
        <li key={`li-${lineIdx}`} className="leading-relaxed">
          {renderInline(olMatch[2])}
        </li>
      );
      return;
    }

    // Non-list line -> flush any pending list
    flushList(lineIdx);

    // Empty line -> space
    if (!trimmed) {
      return;
    }

    // Headings
    if (trimmed.startsWith('### ')) {
      blocks.push(
        <h3 key={`h3-${lineIdx}`} className="text-base font-bold text-white mt-4 mb-2 tracking-wide flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-teal-400"></span>
          {renderInline(trimmed.slice(4))}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith('## ')) {
      blocks.push(
        <h2 key={`h2-${lineIdx}`} className="text-lg font-bold text-white mt-5 mb-2.5 pb-1 border-b border-slate-800 tracking-wide">
          {renderInline(trimmed.slice(3))}
        </h2>
      );
      return;
    }

    if (trimmed.startsWith('# ')) {
      blocks.push(
        <h1 key={`h1-${lineIdx}`} className="text-xl font-extrabold text-white mt-6 mb-3 tracking-tight">
          {renderInline(trimmed.slice(2))}
        </h1>
      );
      return;
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      blocks.push(
        <blockquote
          key={`bq-${lineIdx}`}
          className="border-l-2 border-teal-500/50 pl-3 my-2 text-xs italic text-slate-400 bg-slate-900/40 py-1 rounded-r"
        >
          {renderInline(trimmed.slice(2))}
        </blockquote>
      );
      return;
    }

    // Standard paragraph
    blocks.push(
      <p key={`p-${lineIdx}`} className="leading-relaxed text-slate-200 my-2 text-sm">
        {renderInline(line)}
      </p>
    );
  });

  // Flush any trailing list or open code block
  flushList(lines.length);
  if (inCodeBlock && codeBlockLines.length > 0) {
    blocks.push(
      <pre
        key="pre-trail"
        className="p-3 my-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-teal-300 overflow-x-auto"
      >
        <code>{codeBlockLines.join('\n')}</code>
      </pre>
    );
  }

  return <div className={`space-y-1 text-sm ${className}`}>{blocks}</div>;
};

export default SafeMarkdownViewer;
