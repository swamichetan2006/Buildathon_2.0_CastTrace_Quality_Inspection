import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

describe('SafeMarkdown Parsing and Sanitization Logic', () => {
  // Pure tokenizer/sanitizer implementation matching SafeMarkdownViewer
  function parseMarkdownTokens(content, verifiedCitations = []) {
    const citationMap = new Map();
    for (const c of verifiedCitations) {
      if (c.source_reference) {
        citationMap.set(c.source_reference.trim().toUpperCase(), c);
      }
    }

    const lines = content.split('\n');
    const parsedElements = [];

    lines.forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) return;

      if (trimmed.startsWith('### ')) {
        parsedElements.push({ type: 'heading', level: 3, text: trimmed.slice(4) });
      } else if (trimmed.startsWith('## ')) {
        parsedElements.push({ type: 'heading', level: 2, text: trimmed.slice(3) });
      } else if (trimmed.startsWith('# ')) {
        parsedElements.push({ type: 'heading', level: 1, text: trimmed.slice(2) });
      } else if (/^[-*]\s+/.test(trimmed)) {
        parsedElements.push({ type: 'list_item', listType: 'ul', text: trimmed.replace(/^[-*]\s+/, '') });
      } else if (/^\d+\.\s+/.test(trimmed)) {
        parsedElements.push({ type: 'list_item', listType: 'ol', text: trimmed.replace(/^\d+\.\s+/, '') });
      } else if (trimmed.startsWith('> ')) {
        parsedElements.push({ type: 'blockquote', text: trimmed.slice(2) });
      } else {
        parsedElements.push({ type: 'paragraph', text: trimmed });
      }
    });

    return parsedElements;
  }

  function sanitizeLinks(text) {
    // Matches [label](url) allowing nested parens in URL
    const linkPattern = /\[([^\]]+)\]\(((?:[^()]+|\([^()]*\))*)\)/g;
    return text.replace(linkPattern, (match, label, url) => {
      const cleanUrl = url.trim();
      const isSafe = /^(https?:\/\/|\/)/i.test(cleanUrl) && !/^(javascript:|data:|vbscript:)/i.test(cleanUrl);
      if (isSafe) {
        return `<a href="${cleanUrl}">${label}</a>`;
      }
      return `[${label}]`;
    });
  }

  function extractBoldText(text) {
    const boldPattern = /\*\*([^*]+)\*\*/g;
    const matches = [];
    let m;
    while ((m = boldPattern.exec(text)) !== null) {
      matches.push(m[1]);
    }
    return matches;
  }

  test('Correctly parses headings of levels 1, 2, and 3', () => {
    const md = '# Quality Overview\n## Inspection Summary\n### Batch Metrics';
    const elements = parseMarkdownTokens(md);

    assert.equal(elements.length, 3);
    assert.deepEqual(elements[0], { type: 'heading', level: 1, text: 'Quality Overview' });
    assert.deepEqual(elements[1], { type: 'heading', level: 2, text: 'Inspection Summary' });
    assert.deepEqual(elements[2], { type: 'heading', level: 3, text: 'Batch Metrics' });
  });

  test('Extracts bold text enclosed in double asterisks', () => {
    const text = '**Batch Status**: Under review. Found **1 major defect** pending reinspection.';
    const boldItems = extractBoldText(text);

    assert.equal(boldItems.length, 2);
    assert.equal(boldItems[0], 'Batch Status');
    assert.equal(boldItems[1], '1 major defect');
  });

  test('Correctly classifies unordered and ordered list items', () => {
    const md = '- Item 1 inspected\n* Item 2 defective\n1. Review completed\n2. Action assigned';
    const elements = parseMarkdownTokens(md);

    assert.equal(elements.length, 4);
    assert.equal(elements[0].type, 'list_item');
    assert.equal(elements[0].listType, 'ul');
    assert.equal(elements[2].type, 'list_item');
    assert.equal(elements[2].listType, 'ol');
  });

  test('Sanitizes malicious links: permits https, rejects javascript: and data: URIs', () => {
    const safeInput = 'Refer to [Batch Policy](https://casttrace.local/policy)';
    assert.equal(sanitizeLinks(safeInput), 'Refer to <a href="https://casttrace.local/policy">Batch Policy</a>');

    const unsafeXSS = 'Click [Free Release](javascript:alert("XSS"))';
    assert.equal(sanitizeLinks(unsafeXSS), 'Click [Free Release]');

    const unsafeData = 'View [Payload](data:text/html,<script>evil()</script>)';
    assert.equal(sanitizeLinks(unsafeData), 'View [Payload]');
  });

  test('Handles empty, whitespace, and malformed markdown gracefully without crashing', () => {
    assert.deepEqual(parseMarkdownTokens(''), []);
    assert.deepEqual(parseMarkdownTokens('   \n\n   '), []);
    assert.equal(parseMarkdownTokens('Unclosed **bold and `inline code').length, 1);
  });
});
