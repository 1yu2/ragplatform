function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizeTableLine(line: string) {
  return (line || '').replace(/｜/g, '|').trim();
}

function splitMdTableRow(line: string) {
  let s = normalizeTableLine(line);
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|')) s = s.slice(0, -1);
  return s.split('|').map((x) => x.trim());
}

function isMdTableSep(line: string) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(normalizeTableLine(line));
}

function isMdTableRow(line: string) {
  const s = normalizeTableLine(line);
  if (!s) return false;
  if (!s.includes('|')) return false;
  return true;
}

function renderInlineMarkdown(text: string, citationSup: boolean) {
  let html = escapeHtml(text);

  const codeSpans: string[] = [];
  html = html.replace(/`([^`]+)`/g, (_m, g1) => {
    const idx = codeSpans.length;
    codeSpans.push(`<code>${g1}</code>`);
    return `@@CODE_SPAN_${idx}@@`;
  });

  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  if (citationSup) {
    html = html.replace(/\[(\d+)\]/g, '<sup>[$1]</sup>');
  }

  html = html.replace(/@@CODE_SPAN_(\d+)@@/g, (_m, g1) => codeSpans[Number(g1)] || '');
  return html;
}

function fitCells(cells: string[], targetLen: number) {
  if (cells.length === targetLen) return cells;
  if (cells.length > targetLen) return cells.slice(0, targetLen);
  return [...cells, ...new Array(targetLen - cells.length).fill('')];
}

function renderMdTable(lines: string[], citationSup: boolean) {
  if (lines.length < 2) return '';
  const header = splitMdTableRow(lines[0]);
  const bodyStart = isMdTableSep(lines[1]) ? 2 : 1;
  const bodyRaw = lines.slice(bodyStart).map(splitMdTableRow).filter((row) => row.some((cell) => cell.trim()));
  if (!header.length && !bodyRaw.length) return '';

  const colCount = Math.max(header.length, ...bodyRaw.map((r) => r.length), 1);
  const fixedHeader = fitCells(header, colCount);
  const fixedRows = bodyRaw.map((r) => fitCells(r, colCount));

  const headerHtml = `<tr>${fixedHeader.map((x) => `<th>${renderInlineMarkdown(x, citationSup)}</th>`).join('')}</tr>`;
  const bodyHtml = fixedRows
    .map((r) => `<tr>${r.map((x) => `<td>${renderInlineMarkdown(x, citationSup)}</td>`).join('')}</tr>`)
    .join('');
  return `<table><thead>${headerHtml}</thead><tbody>${bodyHtml}</tbody></table>`;
}

export interface MarkdownRenderOptions {
  citationSup?: boolean;
}

export function markdownToHtml(md: string, options: MarkdownRenderOptions = {}) {
  const citationSup = options.citationSup ?? false;
  const lines = (md || '').split(/\r?\n/);
  const htmlLines: string[] = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) {
      i += 1;
      continue;
    }

    if (/^<\s*table[\s>]/i.test(trimmed)) {
      const parts = [trimmed];
      i += 1;
      while (i < lines.length) {
        parts.push(lines[i]);
        if (/<\s*\/\s*table\s*>/i.test(lines[i])) {
          i += 1;
          break;
        }
        i += 1;
      }
      htmlLines.push(parts.join('\n'));
      continue;
    }

    const normalized = normalizeTableLine(trimmed);
    const nextLine = i + 1 < lines.length ? normalizeTableLine(lines[i + 1]) : '';
    const canStartTable = normalized.startsWith('|') || (isMdTableRow(normalized) && isMdTableSep(nextLine));
    if (canStartTable) {
      const tableLines = [normalized];
      i += 1;
      while (i < lines.length && isMdTableRow(lines[i])) {
        tableLines.push(normalizeTableLine(lines[i]));
        i += 1;
      }
      const tableHtml = renderMdTable(tableLines, citationSup);
      if (tableHtml) {
        htmlLines.push(tableHtml);
        continue;
      }
      htmlLines.push(`<p>${renderInlineMarkdown(line, citationSup)}</p>`);
      continue;
    }

    if (/^<\s*img[\s>]/i.test(trimmed)) {
      htmlLines.push(trimmed);
      i += 1;
      continue;
    }

    const mdImg = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (mdImg) {
      htmlLines.push(`<figure><img src="${escapeHtml(mdImg[2])}" alt="${escapeHtml(mdImg[1])}" loading="lazy" /></figure>`);
      i += 1;
      continue;
    }

    const h3 = trimmed.match(/^###\s+(.+)$/);
    if (h3) {
      htmlLines.push(`<h3>${renderInlineMarkdown(h3[1], citationSup)}</h3>`);
      i += 1;
      continue;
    }
    const h2 = trimmed.match(/^##\s+(.+)$/);
    if (h2) {
      htmlLines.push(`<h2>${renderInlineMarkdown(h2[1], citationSup)}</h2>`);
      i += 1;
      continue;
    }
    const h1 = trimmed.match(/^#\s+(.+)$/);
    if (h1) {
      htmlLines.push(`<h1>${renderInlineMarkdown(h1[1], citationSup)}</h1>`);
      i += 1;
      continue;
    }

    if (trimmed === '[表格]' || trimmed === '[图片/图表]') {
      htmlLines.push(`<div class="md-badge">${escapeHtml(trimmed.slice(1, -1))}</div>`);
      i += 1;
      continue;
    }

    htmlLines.push(`<p>${renderInlineMarkdown(line, citationSup)}</p>`);
    i += 1;
  }

  return htmlLines.join('\n');
}
