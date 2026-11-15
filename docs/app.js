/* Dependency-free reader for the public Markdown bundle. */
(() => {
  'use strict';

  const data = window.HSR_DOCS;
  const $ = id => document.getElementById(id);
  const repo = 'https://github.com/MR-LORD-REX/hsr-cards';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
  if (!data || !data.pages.length) {
    $('article').innerHTML = '<div class="prose"><h1>Documentation bundle missing</h1><p>Run <code>python scripts/build_docs.py</code> from the repository, then reload this page.</p><a href="readme.md">Read the Markdown index</a></div>';
    return;
  }
  const pages = new Map(data.pages.map(page => [page.id, page]));
  const showcase = data.showcase || {items: [], unavailable: []};
  const items = showcase.items || [];
  let currentPage = 'readme';
  let codeBlocks = [];
  let headingObserver;
  let selectedResult = 0;
  let searchEntries = [];
  let toastTimer;

  function plain(text) {
    return String(text).replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/<[^>]*>/g, '').replace(/[`*~]/g, '');
  }

  function slug(text) {
    return plain(text).trim().toLowerCase().replace(/[^\p{L}\p{N}_\s-]/gu, '').replace(/\s/g, '-');
  }

  function headings(markdown) {
    let fenced = false;
    let offset = 0;
    const counts = new Map();
    const result = [];
    for (const line of markdown.split('\n')) {
      const start = offset;
      offset += line.length + 1;
      if (/^\s*(```|~~~)/.test(line)) { fenced = !fenced; continue; }
      const match = !fenced && line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
      if (!match) continue;
      const key = slug(match[2]);
      const count = counts.get(key) || 0;
      counts.set(key, count + 1);
      result.push({level: match[1].length, title: plain(match[2]), id: key + (count ? `-${count}` : ''), offset: start});
    }
    return result;
  }

  function normalize(path) {
    const segments = [];
    for (const part of path.split('/')) {
      if (!part || part === '.') continue;
      if (part === '..') { if (!segments.length) return null; segments.pop(); }
      else segments.push(part);
    }
    return segments.join('/');
  }

  function safeURL(url) {
    const value = String(url).trim();
    if (/[\u0000-\u0020]/.test(value)) return '#';
    if (/^(https?:|mailto:|tel:)/i.test(value)) return value;
    if (/^[a-z][a-z\d+.-]*:/i.test(value) || value.startsWith('//') || value.includes('\\')) return '#';
    return value;
  }

  function resolveLink(url, pageId, image = false) {
    const value = safeURL(url);
    if (value === '#' || /^(https?:|mailto:|tel:)/i.test(value)) return value;
    if (value.startsWith('#/')) return value;
    if (value.startsWith('#')) return `#/${pageId}${value}`;
    const [path, fragment = ''] = value.split('#');
    const base = pageId.includes('/') ? pageId.slice(0, pageId.lastIndexOf('/') + 1) : '';
    const resolved = normalize(base + path);
    if (!image && /(?:^|\/)index\.html$/i.test(path) && fragment.startsWith('/')) return '#' + fragment;
    if (!image && /\.md$/i.test(path)) {
      const id = resolved && resolved.replace(/\.md$/i, '').replace(/^README$/i, 'readme');
      if (pages.has(id)) return `#/${id}${fragment ? '#' + fragment : ''}`;
    }
    if (resolved) return resolved + (fragment ? '#' + fragment : '');
    return image ? '#' : new URL(value, `${repo}/blob/main/docs/${base}`).href;
  }

  function inline(text, pageId, tokens = []) {
    const stash = html => `\u0000${tokens.push(html) - 1}\u0000`;
    let value = text.replace(/`([^`\n]+)`/g, (_, code) => stash(`<code>${escape(code)}</code>`));
    value = value.replace(/!\[([^\]]*)\]\(([^\s)]+)(?:\s+"[^"]*")?\)/g, (_, alt, url) => stash(`<img src="${escape(resolveLink(url, pageId, true))}" alt="${escape(plain(alt))}" loading="lazy">`));
    value = value.replace(/\[([^\]]+)\]\(([^\s)]+)(?:\s+"[^"]*")?\)/g, (_, label, url) => {
      const target = resolveLink(url, pageId);
      const external = /^https?:/i.test(target);
      return stash(`<a href="${escape(target)}"${external ? ' target="_blank" rel="noopener noreferrer"' : ''}>${inline(label, pageId, tokens)}</a>`);
    });
    value = escape(value).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/__([^_]+)__/g, '<strong>$1</strong>').replace(/\*([^*\n]+)\*/g, '<em>$1</em>').replace(/~~([^~]+)~~/g, '<del>$1</del>');
    return value.replace(/\u0000(\d+)\u0000/g, (_, index) => tokens[Number(index)]);
  }

  function highlight(code, language) {
    if (!['python', 'py', 'bash', 'sh', 'powershell', 'json'].includes(language)) return escape(code);
    const pattern = /#[^\n]*|"""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:async|await|from|import|as|with|def|return|for|in|if|else|elif|try|except|raise|class|None|True|False|not|and|or|while|yield|pass|finally)\b|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]\w*(?=\()/g;
    let html = '', position = 0;
    for (const match of code.matchAll(pattern)) {
      html += escape(code.slice(position, match.index));
      const value = match[0];
      const kind = value.startsWith('#') ? 'comment' : /^["']/.test(value) ? 'string' : /^\d/.test(value) ? 'number' : /^\w+$/.test(value) && code[match.index + value.length] === '(' ? 'call' : 'keyword';
      html += `<span class="tok-${kind}">${escape(value)}</span>`;
      position = match.index + value.length;
    }
    return html + escape(code.slice(position));
  }

  function codeBlock(code, language = '') {
    const index = codeBlocks.push(code) - 1;
    return `<div class="code-block"><div class="code-header"><span>${escape(language || 'text')}</span><button class="code-copy" data-copy="${index}" aria-label="Copy code">${icon('copy')}<span>Copy</span></button></div><pre><code>${highlight(code, language.toLowerCase())}</code></pre></div>`;
  }

  function markdown(source, pageId) {
    const lines = source.replace(/\r\n/g, '\n').split('\n');
    const counts = new Map();
    const isBlock = line => /^(#{1,6}\s|\s*(?:```|~~~)|\s*>|\s*[-*+]\s|\s*\d+\.\s|\s*(?:---+|___+|\*\*\*+)\s*$)/.test(line);
    function blocks(input) {
      const out = [];
      let index = 0;
      while (index < input.length) {
        const line = input[index];
        if (!line.trim()) { index++; continue; }
        const fence = line.match(/^\s*(`{3,}|~{3,})(\S*)\s*$/);
        if (fence) {
          const code = [];
          index++;
          while (index < input.length && !input[index].trim().startsWith(fence[1])) code.push(input[index++]);
          index++;
          out.push(codeBlock(code.join('\n'), fence[2]));
          continue;
        }
        const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
        if (heading) {
          const level = heading[1].length, key = slug(heading[2]);
          const count = counts.get(key) || 0;
          counts.set(key, count + 1);
          const id = key + (count ? `-${count}` : '');
          out.push(`<h${level} id="${escape(id)}">${inline(heading[2], pageId)}${level > 1 ? `<a class="heading-anchor" href="#/${pageId}#${escape(id)}" aria-label="Link to ${escape(plain(heading[2]))}">#</a>` : ''}</h${level}>`);
          index++;
          continue;
        }
        if (/^\s*(?:---+|___+|\*\*\*+)\s*$/.test(line)) { out.push('<hr>'); index++; continue; }
        if (/^\s*>/.test(line)) {
          const quote = [];
          while (index < input.length && /^\s*>/.test(input[index])) quote.push(input[index++].replace(/^\s*>\s?/, ''));
          let label = '';
          const notice = quote[0].match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/);
          if (notice) { label = `<span class="callout-label">${escape(notice[1])}</span>`; quote.shift(); }
          out.push(`<blockquote>${label}${blocks(quote)}</blockquote>`);
          continue;
        }
        const list = line.match(/^(\s*)([-*+]|\d+\.)\s+(.+)$/);
        if (list) {
          const indent = list[1].length, ordered = /\d/.test(list[2]);
          const tag = ordered ? 'ol' : 'ul';
          const entries = [];
          while (index < input.length) {
            const item = input[index].match(/^(\s*)([-*+]|\d+\.)\s+(.+)$/);
            if (!item || item[1].length !== indent || /\d/.test(item[2]) !== ordered) break;
            const continuation = [];
            index++;
            while (index < input.length) {
              if (!input[index].trim()) {
                if (index + 1 < input.length && /^\s+\S/.test(input[index + 1]) && input[index + 1].match(/^\s*/)[0].length > indent) { continuation.push(''); index++; continue; }
                break;
              }
              const leading = input[index].match(/^\s*/)[0].length;
              if (leading <= indent) break;
              continuation.push(input[index++].slice(Math.min(leading, indent + item[2].length + 1)));
            }
            entries.push(`<li>${inline(item[3], pageId)}${continuation.length ? blocks(continuation) : ''}</li>`);
            while (index < input.length && !input[index].trim() && input[index + 1]?.match(/^(\s*)([-*+]|\d+\.)\s/)?.[1].length === indent) index++;
          }
          out.push(`<${tag}${ordered && list[2] !== '1.' ? ` start="${parseInt(list[2], 10)}"` : ''}>${entries.join('')}</${tag}>`);
          continue;
        }
        const paragraph = [line.trim()];
        index++;
        while (index < input.length && input[index].trim() && !isBlock(input[index])) paragraph.push(input[index++].trim());
        out.push(`<p>${inline(paragraph.join(' '), pageId)}</p>`);
      }
      return out.join('\n');
    }
    return blocks(lines);
  }

  function renderNavigation() {
    const sections = ['Overview', 'Getting started', 'Guides', 'API reference', 'Showcase'];
    $('navigation').innerHTML = sections.map(section => {
      const group = data.pages.filter(page => page.section === section);
      if (!group.length) return '';
      const links = group.map(page => `<a class="${['readme', 'showcase'].includes(page.id) ? 'nav-primary' : 'nav-link'}${page.id.split('/').length > 2 ? ' nested' : ''}" href="#/${escape(page.id)}"${page.id === currentPage ? ' aria-current="page"' : ''}>${page.id === 'readme' ? icon('book') : page.id === 'showcase' ? icon('cards') : ''}<span>${escape(page.id === 'readme' ? 'Introduction' : page.title)}</span></a>`).join('');
      return ['Overview', 'Showcase'].includes(section) ? links : `<details class="nav-group" open><summary>${escape(section)}</summary>${links}</details>`;
    }).join('');
  }

  function previewButton(item, className = 'showcase-image-button') {
    return `<button class="${className}" data-preview="${escape(item.id)}" aria-label="Preview ${escape(item.title)}"><img src="${escape(safeURL(item.image))}" alt="${escape(item.title)} card" loading="lazy" width="${item.width}" height="${item.height}">${className === 'showcase-image-button' ? '<span class="preview-label">View card</span>' : ''}</button>`;
  }

  function renderHome() {
    const heroCard = items.find(item => item.anchors?.includes('character-info')) || items.find(item => /get_character_info$/.test(item.method)) || items[0];
    const featured = ['character-info', 'current-pf', 'current-as', 'tier-list-moc'].map(id => items.find(item => item.anchors?.includes(id) || item.id === id)).filter(Boolean);
    if (featured.length < 4) for (const item of items) { if (!featured.includes(item)) featured.push(item); if (featured.length === 4) break; }
    return `<div class="eyebrow">Public Python documentation</div>
      <section class="hero"><div><h1>Honkai: Star Rail.<br><span>Ready to render.</span></h1><p class="hero-description">Create character, endgame, and player cards with an async Python library. Query Nanoka, Prydwen, and HoYoLAB through focused clients, then save images or use structured results.</p><div class="hero-actions"><a class="button-primary" href="#/getting-started/quickstart">Get started ${icon('arrow')}</a><a class="button-link" href="#/api/main-client">Explore the API ${icon('code')}</a></div></div>${heroCard ? `<figure class="hero-art"><img src="${escape(heroCard.image)}" alt="${escape(heroCard.title)} example" width="${heroCard.width}" height="${heroCard.height}"><figcaption>${escape(heroCard.title)}<a href="#/showcase#${escape(heroCard.id)}">View output ${icon('arrow')}</a></figcaption></figure>` : ''}</section>
      <div class="feature-strip"><span>${icon('check')} Python 3.10+</span><span>${icon('check')} Async clients</span><span>${icon('check')} Version comparisons</span><span>${icon('check')} Cache controls</span></div>
      <section class="home-section"><div class="section-heading"><h2>Your first card</h2><a href="#/getting-started/installation">Installation guide ${icon('arrow')}</a></div><div class="quickstart-grid"><div class="quickstart-aside"><h3>Start with the source checkout</h3><p>These docs describe the current repository. Install it in your virtual environment to use the latest public methods.</p><div class="install-command">${codeBlock('python -m pip install -e .', 'bash')}</div><p>Character cards need no player account. The first request may download provider data and artwork.</p></div>${codeBlock('import asyncio\nfrom hsr_cards import HonkaiStarrail\n\nasync def main():\n    async with HonkaiStarrail() as client:\n        card = await client.get_character_info(\n            1507, version="4.7.51"\n        )\n        card.save("character-info.png")\n\nasyncio.run(main())', 'python')}</div></section>
      <section class="home-section"><div class="section-heading"><h2>Choose what to build</h2><a href="#/api/card-functions">Card function reference ${icon('arrow')}</a></div><div class="guide-grid">${[
        ['characters', 'code', 'Character & equipment cards', 'Render character info, skill sheets, Light Cones, relics, and items. Compare two provider builds.'],
        ['endgame', 'cards', 'Current & upcoming endgame', 'Render MOC, Pure Fiction, and Apocalyptic Shadow floors with stage details and enemy lineups.'],
        ['player-cards', 'book', 'Player & account cards', 'Turn HoYoLAB battle records, notes, and Currency Wars runs into shareable images.']
      ].map(([id, image, title, description]) => `<a class="guide-card" href="#/guides/${id}">${icon(image)}<h3>${title}</h3><p>${description}</p><span class="card-link">Read the guide ${icon('arrow')}</span></a>`).join('')}</div></section>
      ${featured.length ? `<section class="home-section"><div class="section-heading"><h2>Rendered with the public API</h2><a href="#/showcase">All ${items.length} demo outputs ${icon('arrow')}</a></div><div class="home-gallery">${featured.map(item => `<figure class="mini-demo">${previewButton(item, 'mini-preview')}<figcaption>${escape(item.title)}</figcaption></figure>`).join('')}</div></section>` : ''}
      <div class="home-note"><p>Use the main facade for a convenient entry point, or work directly with independent provider clients. Each reference documents signatures, properties, return values, and resource ownership.</p><a href="#/api/provider-apis">Provider APIs ${icon('arrow')}</a></div>`;
  }

  function renderShowcase(group = 'All') {
    codeBlocks = [];
    const groups = [...new Set(items.map(item => item.group || 'Other'))];
    const filtered = group === 'All' ? items : items.filter(item => item.group === group);
    $('article').innerHTML = `<div class="showcase-intro"><div class="eyebrow">Generated examples</div><h1>Card showcase</h1><p>Browse outputs from the public rendering methods. Every demo identifies its data source; player examples use fictional payloads. Open a card to inspect it and download the original PNG.</p></div><div class="showcase-meta"><span>${items.length} rendered outputs</span><span>Generated ${escape(showcase.generated_at || '')}</span><a href="showcase.md">Markdown gallery</a></div><div class="filter-bar" role="group" aria-label="Filter card demos">${['All', ...groups].map(name => `<button class="filter-button" data-filter="${escape(name)}" aria-pressed="${name === group}">${escape(name)}</button>`).join('')}<span class="gallery-count" aria-live="polite">${filtered.length} outputs</span></div><div class="showcase-grid">${filtered.map(item => `<section class="showcase-card" id="${escape(item.id)}">${(item.anchors || []).filter(anchor => anchor !== item.id).map(anchor => `<span class="showcase-anchor" id="${escape(anchor)}"></span>`).join('')}${previewButton(item)}<h2>${escape(item.title)}</h2><div class="method-name">${escape(item.method)}</div><p><span class="source-badge">${escape(item.source)}</span>${item.width} × ${item.height}</p><p>${escape(item.description)}</p>${item.example ? `<details class="showcase-example"><summary>Usage example</summary>${codeBlock(item.example, 'python')}</details>` : ''}</section>`).join('')}</div><div class="unavailable-note"><h2>Methods and output types</h2><p>Query methods, properties, cache controls, and lifecycle helpers return data or manage resources. Their usage is documented in the API reference. Batch demos show one successful item; methods with multiple game modes have separate examples.</p><p>Nanoka AA floor cards are deferred. The existing HoYoLAB <code>anomaly()</code> method has its own player-card demo.</p>${showcase.unavailable?.length ? `<ul>${showcase.unavailable.map(entry => `<li><code>${escape(entry.method)}</code>: ${escape(entry.reason)}</li>`).join('')}</ul>` : ''}<a href="#/api/main-client">Browse the public API</a></div>`;
  }

  function route() {
    let raw;
    try { raw = decodeURIComponent(location.hash.slice(1)); } catch (_) { raw = ''; }
    const [path, anchor = ''] = raw.replace(/^\//, '').split('#');
    return {id: path || 'readme', anchor};
  }

  function setMenu(open) {
    document.body.classList.toggle('menu-open', open);
    $('sidebar-backdrop').hidden = !open;
    $('menu-toggle').setAttribute('aria-expanded', String(open));
    $('menu-toggle').setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  }

  function scrollToAnchor(anchor) {
    if (!anchor) { window.scrollTo(0, 0); return; }
    requestAnimationFrame(() => {
      const target = document.getElementById(anchor);
      if (target) { target.scrollIntoView({block: 'start'}); target.setAttribute('tabindex', '-1'); target.focus({preventScroll: true}); }
    });
  }

  function renderPage() {
    const {id, anchor} = route();
    if (id === 'main-content') { $('main-content').focus(); return; }
    setMenu(false);
    const page = pages.get(id);
    if (id === currentPage && $('article').dataset.loaded === id) {
      if (id === 'showcase' && anchor && !document.getElementById(anchor)) renderShowcase();
      scrollToAnchor(anchor);
      return;
    }
    currentPage = id;
    codeBlocks = [];
    headingObserver?.disconnect();
    document.body.dataset.page = id;
    $('article').dataset.loaded = id;
    if (!page) {
      $('article').innerHTML = '<div class="prose"><h1>Page not found</h1><p>This documentation page is unavailable.</p><a href="#/readme">Back to the documentation</a></div>';
      $('outline').innerHTML = '';
      $('pagination').innerHTML = '';
      document.title = 'Page not found · HSR Cards';
      renderNavigation();
      return;
    }
    document.title = `${page.id === 'readme' ? 'Documentation' : page.title} · HSR Cards`;
    if (id === 'readme') $('article').innerHTML = renderHome();
    else if (id === 'showcase') renderShowcase();
    else $('article').innerHTML = `<div class="breadcrumbs"><a href="#/readme">Docs</a><span>/</span><span>${escape(page.section)}</span></div><div class="prose">${markdown(page.content, id)}</div>`;
    const outline = ['readme', 'showcase'].includes(id) ? [] : headings(page.content).filter(heading => heading.level === 2 || heading.level === 3);
    $('outline').innerHTML = outline.map(heading => `<a class="level-${heading.level}" href="#/${escape(id)}#${escape(heading.id)}">${escape(heading.title)}</a>`).join('');
    headingObserver = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        $('outline').querySelectorAll('a').forEach(link => link.classList.toggle('active', link.hash.endsWith('#' + entry.target.id)));
      }
    }, {rootMargin: '-80px 0px -65% 0px'});
    $('article').querySelectorAll('h2[id], h3[id]').forEach(heading => headingObserver.observe(heading));
    const index = data.pages.findIndex(entry => entry.id === id);
    const previous = data.pages[index - 1], next = data.pages[index + 1];
    $('pagination').innerHTML = (previous ? `<a href="#/${previous.id}"><small>Previous</small>${escape(previous.title)}</a>` : '') + (next ? `<a class="next" href="#/${next.id}"><small>Next</small>${escape(next.title)}</a>` : '');
    $('source-link').href = `${repo}/blob/main/docs/${id}.md`;
    $('source-link').target = '_blank';
    $('source-link').rel = 'noopener noreferrer';
    renderNavigation();
    setMenu(false);
    scrollToAnchor(anchor);
  }

  function updateTheme() {
    const dark = document.documentElement.dataset.theme === 'dark';
    $('theme-toggle').innerHTML = icon(dark ? 'sun' : 'moon');
    $('theme-toggle').setAttribute('aria-label', `Switch to ${dark ? 'light' : 'dark'} theme`);
    document.querySelector('meta[name="theme-color"]').content = dark ? '#101b20' : '#f8faf9';
  }

  function showToast(message) {
    clearTimeout(toastTimer);
    $('toast').textContent = message;
    $('toast').classList.add('visible');
    toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 2000);
  }

  async function copyCode(button) {
    const text = codeBlocks[Number(button.dataset.copy)];
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const area = document.createElement('textarea');
        area.value = text;
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.append(area);
        area.select();
        const success = document.execCommand('copy');
        area.remove();
        if (!success) throw new Error('Clipboard unavailable');
      }
      button.innerHTML = `${icon('check')}<span>Copied</span>`;
      showToast('Code copied');
      setTimeout(() => { if (button.isConnected) button.innerHTML = `${icon('copy')}<span>Copy</span>`; }, 2000);
    } catch (_) { showToast('Select the code and copy it with your keyboard.'); }
  }

  function openPreview(id) {
    const item = items.find(entry => entry.id === id);
    if (!item) return;
    $('image-title').textContent = item.title;
    $('image-source').textContent = `${item.source} · ${item.width} × ${item.height}`;
    $('image-preview').src = safeURL(item.image);
    $('image-preview').alt = `${item.title} card`;
    $('image-method').textContent = item.method;
    $('image-original').href = safeURL(item.original);
    $('image-dialog').showModal();
  }

  const searchIndex = data.pages.flatMap(page => {
    const sections = headings(page.content);
    return [{page, title: page.title, anchor: '', text: plain(page.content.slice(0, sections[1]?.offset || 300))}, ...(['readme', 'showcase'].includes(page.id) ? [] : sections.map((heading, index) => ({page, title: heading.title, anchor: heading.id, level: heading.level, text: plain(page.content.slice(heading.offset, sections[index + 1]?.offset || page.content.length))})).filter(heading => heading.level > 1))];
  }).concat(items.map(item => ({page: pages.get('showcase'), title: item.title, anchor: item.id, text: `${item.method} ${item.description}`})));

  function search(query) {
    const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    selectedResult = 0;
    searchEntries = searchIndex.map(entry => {
      const title = entry.title.toLowerCase(), page = entry.page.title.toLowerCase(), text = entry.text.toLowerCase();
      const score = terms.length ? terms.reduce((sum, term) => sum + (title === term ? 30 : title.includes(term) ? 12 : page.includes(term) ? 4 : text.includes(term) ? 1 : -100), 0) : entry.anchor ? -1 : 1;
      return {...entry, score};
    }).filter(entry => entry.score > 0).sort((a, b) => b.score - a.score).slice(0, 12);
    function marked(text) {
      if (!terms.length) return escape(text);
      const pattern = terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
      const pieces = text.split(new RegExp(`(${pattern})`, 'gi'));
      return pieces.map(piece => terms.includes(piece.toLowerCase()) ? `<mark>${escape(piece)}</mark>` : escape(piece)).join('');
    }
    $('search-results').innerHTML = searchEntries.length ? searchEntries.map((entry, index) => {
      const text = entry.text.replace(/\s+/g, ' ');
      const match = terms.length ? Math.max(0, text.toLowerCase().indexOf(terms[0]) - 35) : 0;
      const snippet = (match ? '… ' : '') + text.slice(match, match + 140);
      return `<a class="search-result${index === 0 ? ' selected' : ''}" href="#/${escape(entry.page.id)}${entry.anchor ? '#' + escape(entry.anchor) : ''}"><span class="result-title">${marked(entry.title)}</span><span class="result-context">${escape(entry.page.section)} / ${escape(entry.page.title)}</span>${terms.length ? `<span class="result-snippet">${marked(snippet)}</span>` : ''}</a>`;
    }).join('') : '<div class="search-empty">No results. Try a method name such as get_character_info.</div>';
    $('search-status').textContent = `${searchEntries.length} results`;
  }

  function openSearch() {
    $('search-dialog').showModal();
    $('search-input').value = '';
    search('');
    $('search-input').focus();
  }

  $('version').textContent = `v${data.version}`;
  $('theme-toggle').addEventListener('click', () => {
    document.documentElement.dataset.theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('hsr-docs-theme', document.documentElement.dataset.theme); } catch (_) {}
    updateTheme();
  });
  $('menu-toggle').addEventListener('click', () => setMenu(!document.body.classList.contains('menu-open')));
  $('sidebar-backdrop').addEventListener('click', () => { setMenu(false); $('menu-toggle').focus(); });
  $('search-launch').addEventListener('click', openSearch);
  $('search-close').addEventListener('click', () => $('search-dialog').close());
  $('image-close').addEventListener('click', () => $('image-dialog').close());
  $('search-input').addEventListener('input', event => search(event.target.value));
  $('search-results').addEventListener('click', event => { if (event.target.closest('a')) $('search-dialog').close(); });
  $('search-input').addEventListener('keydown', event => {
    const links = [...$('search-results').querySelectorAll('a')];
    if (!links.length) return;
    if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault();
      selectedResult = (selectedResult + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
      links.forEach((link, index) => link.classList.toggle('selected', index === selectedResult));
      links[selectedResult].scrollIntoView({block: 'nearest'});
    } else if (event.key === 'Enter') {
      event.preventDefault();
      links[selectedResult].click();
    }
  });
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); if (!$('search-dialog').open) openSearch(); }
    if (event.key === 'Escape') setMenu(false);
  });
  document.addEventListener('click', event => {
    const copy = event.target.closest('[data-copy]');
    if (copy) copyCode(copy);
    const preview = event.target.closest('[data-preview]');
    if (preview) openPreview(preview.dataset.preview);
    const filter = event.target.closest('[data-filter]');
    if (filter) renderShowcase(filter.dataset.filter);
    const skip = event.target.closest('.skip-link');
    if (skip) { event.preventDefault(); $('main-content').focus(); }
    const link = event.target.closest('a[href^="#/"]');
    if (link && link.hash === location.hash) { $('search-dialog').close(); renderPage(); }
  });
  for (const dialog of [$('search-dialog'), $('image-dialog')]) dialog.addEventListener('click', event => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
  });
  window.addEventListener('hashchange', renderPage);
  window.addEventListener('resize', () => { if (window.innerWidth > 780) setMenu(false); });
  updateTheme();
  renderPage();
})();
