const app = document.querySelector("#app");
const searchDialog = document.querySelector("#search-dialog");
const searchInput = document.querySelector("#global-search");
const searchResults = document.querySelector("#search-results");
const searchHint = document.querySelector("#search-hint");
const progressBar = document.querySelector(".reading-progress span");

let data;
let concepts = [];
let conceptByName = new Map();

const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const conceptUrl = (name) => `#/concept/${encodeURIComponent(name)}`;
const domainUrl = (name) => `#/domain/${encodeURIComponent(name)}`;
const formatNumber = (number) => new Intl.NumberFormat("zh-CN").format(number || 0);

function conceptCard(concept, index = 0) {
  const domain = concept.domains[0] || "跨领域";
  return `
    <a class="concept-card" href="${conceptUrl(concept.name)}">
      <div class="card-meta"><span>NO. ${String(index + 1).padStart(3, "0")}</span><span>${escapeHtml(domain)}</span></div>
      <h3>${escapeHtml(concept.name)}${concept.nameEn ? `<small>${escapeHtml(concept.nameEn)}</small>` : ""}</h3>
      <p>${escapeHtml(concept.excerpt)}</p>
      <span class="card-arrow" aria-hidden="true">↗</span>
    </a>`;
}

function renderHome() {
  const daySeed = Math.floor(Date.now() / 86400000);
  const picks = [0, 97, 251].map((offset) => concepts[(daySeed + offset) % concepts.length]);
  const topDomains = data.domains.slice(0, 9);
  return `
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <div class="eyebrow">Personal Noosphere · 个人思想圈</div>
          <h1>把思想，连成一张<br><em>可以漫游</em>的地图。</h1>
          <p class="hero-intro">从哲学到心理学，从艺术到经济学。这里收藏的不是孤立答案，而是概念之间不断生长的连接。</p>
          <form class="hero-search" id="hero-search">
            <label class="sr-only" for="hero-query">搜索概念</label>
            <input id="hero-query" placeholder="从一个念头出发……" autocomplete="off" />
            <button type="submit" aria-label="开始搜索">→</button>
          </form>
        </div>
        <aside class="hero-aside">
          <div class="aside-number">${formatNumber(data.stats.concepts)}</div>
          <p>个概念正在彼此连接。<br>每一次阅读，都是下一次跳跃的起点。</p>
        </aside>
      </section>

      <section class="stats-band" aria-label="概念库统计">
        <div class="stat"><strong>${formatNumber(data.stats.concepts)}</strong><span>概念 CONCEPTS</span></div>
        <div class="stat"><strong>${formatNumber(data.stats.links)}</strong><span>连接 LINKS</span></div>
        <div class="stat"><strong>${formatNumber(data.stats.domains)}</strong><span>领域 DOMAINS</span></div>
        <div class="stat"><strong>${formatNumber(data.stats.sources)}</strong><span>来源 SOURCES</span></div>
      </section>

      <section class="section">
        <div class="section-head">
          <div><div class="eyebrow">Entries</div><h2>思想的入口</h2></div>
          <a class="text-link" href="#/domains">查看全部领域 →</a>
        </div>
        <div class="domain-grid">
          ${topDomains.map((domain, index) => `
            <a class="domain-card" href="${domainUrl(domain.name)}">
              <span class="domain-index">0${index + 1}</span>
              <h3>${escapeHtml(domain.name)}</h3>
              <p>${formatNumber(domain.count)} 个概念等待探索</p>
            </a>`).join("")}
        </div>
      </section>

      <section class="section">
        <div class="section-head">
          <div><div class="eyebrow">Daily Drift</div><h2>今日漫游</h2></div>
          <button class="nav-link" data-random type="button">换一条路径 ↻</button>
        </div>
        <div class="concept-grid">${picks.map(conceptCard).join("")}</div>
      </section>
    </div>`;
}

function directoryMarkup(items) {
  if (!items.length) return `<div class="empty">没有找到匹配的概念。换一个词，或从领域入口重新出发。</div>`;
  return `<div class="directory-list">${items.map((concept, index) => `
    <a class="directory-item" href="${conceptUrl(concept.name)}">
      <span class="num">${String(index + 1).padStart(3, "0")}</span>
      <strong>${escapeHtml(concept.name)}</strong>
      <p>${escapeHtml(concept.excerpt)}</p>
      <span class="domain">${escapeHtml(concept.domains[0] || "跨领域")}</span>
    </a>`).join("")}</div>`;
}

function renderConceptDirectory(items = concepts, title = "全部概念", description = "按名称浏览这座思想库，也可以输入一个词快速缩小范围。") {
  return `
    <div class="page-shell">
      <header class="page-header">
        <div class="eyebrow">Concept Directory</div>
        <h1>${escapeHtml(title)}</h1>
        <p>${escapeHtml(description)}</p>
        <div class="filter-bar">
          <label class="sr-only" for="directory-filter">筛选当前概念</label>
          <input id="directory-filter" type="search" placeholder="在当前列表中筛选……" autocomplete="off" />
          <span class="count-label" id="directory-count">${formatNumber(items.length)} 个概念</span>
        </div>
      </header>
      <section class="directory" id="directory-results">${directoryMarkup(items)}</section>
    </div>`;
}

function renderDomains() {
  return `
    <div class="page-shell">
      <header class="page-header">
        <div class="eyebrow">Domains</div>
        <h1>领域不是边界，<br>只是进入思想的门。</h1>
        <p>同一个概念常常穿过多个学科。选择熟悉的入口，然后沿关联走向陌生处。</p>
      </header>
      <section class="section">
        <div class="domain-grid">
          ${data.domains.map((domain, index) => `
            <a class="domain-card" href="${domainUrl(domain.name)}">
              <span class="domain-index">${String(index + 1).padStart(2, "0")}</span>
              <h3>${escapeHtml(domain.name)}</h3>
              <p>${formatNumber(domain.count)} 个概念</p>
            </a>`).join("")}
        </div>
      </section>
    </div>`;
}

function sideLinks(title, items, emptyText) {
  return `
    <section class="link-panel">
      <div class="side-label">${escapeHtml(title)}</div>
      <div class="side-links">
        ${items.length ? items.slice(0, 9).map((item) => `
          <a href="${conceptUrl(item.name)}"><strong>${escapeHtml(item.name)}</strong><span>${item.context ? escapeHtml(item.context.slice(0, 42)) + "…" : "打开概念"}</span></a>
        `).join("") : `<span class="count-label">${escapeHtml(emptyText)}</span>`}
      </div>
    </section>`;
}

function relatedConcepts(concept) {
  const ids = new Set();
  const related = [];
  const add = (candidate) => {
    if (candidate && candidate.id !== concept.id && !ids.has(candidate.id)) {
      ids.add(candidate.id);
      related.push(candidate);
    }
  };
  concept.outgoing.forEach((link) => add(concepts.find((item) => item.id === link.targetId)));
  concept.backlinks.forEach((link) => add(concepts.find((item) => item.id === link.id)));
  concepts.filter((item) => item.domains.some((domain) => concept.domains.includes(domain))).forEach(add);
  return related.slice(0, 3);
}

function renderConcept(concept) {
  if (!concept) return renderNotFound();
  const outgoing = concept.outgoing.filter((link) => link.resolved && conceptByName.has(link.name));
  const backlinks = concept.backlinks;
  const related = relatedConcepts(concept);
  return `
    <div class="article-shell">
      <nav class="breadcrumb" aria-label="面包屑">
        <a href="#/">首页</a><span>/</span>
        ${concept.domains[0] ? `<a href="${domainUrl(concept.domains[0])}">${escapeHtml(concept.domains[0])}</a><span>/</span>` : ""}
        <span>${escapeHtml(concept.name)}</span>
      </nav>
      <div class="article-layout">
        <aside class="article-sidebar">
          <div class="side-label">On this page</div>
          <nav class="toc" aria-label="本文目录">
            ${concept.headings.filter((heading) => Number(heading.level) <= 3).map((heading) => `<a class="level-${heading.level}" href="#${heading.id}">${escapeHtml(heading.title)}</a>`).join("")}
          </nav>
        </aside>

        <article>
          <header class="article-header">
            <div class="eyebrow">${escapeHtml(concept.domains.join(" · ") || "跨领域概念")}</div>
            <h1>${escapeHtml(concept.name)}</h1>
            ${concept.nameEn ? `<div class="english-name">${escapeHtml(concept.nameEn)}</div>` : ""}
          </header>
          <div class="article-body">${concept.html}</div>
        </article>

        <aside class="article-sidebar">
          <div class="article-meta">
            <div class="meta-row"><span>来源 SOURCE</span><strong>${escapeHtml(concept.source || "未标注")}</strong></div>
            <div class="meta-row"><span>收录日期 DATE</span><strong>${escapeHtml(concept.date || "未标注")}</strong></div>
            <div class="meta-row"><span>阅读规模 LENGTH</span><strong>${formatNumber(concept.wordCount)} 字</strong></div>
          </div>
          ${sideLinks("通向这里 · BACKLINKS", backlinks, "暂时没有概念通向这里")}
          ${sideLinks("继续前往 · LINKS", outgoing, "暂时没有出发路径")}
        </aside>
      </div>
    </div>
    <section class="article-end">
      <div class="section-head"><div><div class="eyebrow">Keep Exploring</div><h2>沿着连接，继续漫游</h2></div></div>
      <div class="concept-grid">${related.map(conceptCard).join("")}</div>
    </section>`;
}

function renderNotFound() {
  return `<div class="page-shell"><header class="page-header"><div class="eyebrow">404</div><h1>这条思想路径还不存在。</h1><p><a class="text-link" href="#/">回到概念库首页</a></p></header></div>`;
}

function parseRoute() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path] = raw.split("?");
  const parts = path.split("/").filter(Boolean).map((part) => decodeURIComponent(part));
  return parts;
}

function renderRoute() {
  const parts = parseRoute();
  progressBar.style.width = "0";
  let html;
  let title = "MERJIC 概念库";
  if (!parts.length) {
    html = renderHome();
  } else if (parts[0] === "concepts") {
    html = renderConceptDirectory();
    title = "全部概念 · MERJIC 概念库";
  } else if (parts[0] === "domains") {
    html = renderDomains();
    title = "领域 · MERJIC 概念库";
  } else if (parts[0] === "domain" && parts[1]) {
    const items = concepts.filter((concept) => concept.domains.includes(parts[1]));
    html = renderConceptDirectory(items, parts[1], `从 ${formatNumber(items.length)} 个概念进入这一领域，再沿着双向链接跨越学科边界。`);
    title = `${parts[1]} · MERJIC 概念库`;
  } else if (parts[0] === "concept" && parts[1]) {
    const concept = conceptByName.get(parts.slice(1).join("/"));
    html = renderConcept(concept);
    title = concept ? `${concept.name} · MERJIC 概念库` : title;
  } else {
    html = renderNotFound();
  }
  app.innerHTML = html;
  document.title = title;
  window.scrollTo({ top: 0, behavior: "instant" });
  bindPageInteractions();
  app.focus({ preventScroll: true });
}

function bindPageInteractions() {
  const heroSearch = document.querySelector("#hero-search");
  heroSearch?.addEventListener("submit", (event) => {
    event.preventDefault();
    openSearch(document.querySelector("#hero-query").value);
  });

  const filter = document.querySelector("#directory-filter");
  if (filter) {
    const parts = parseRoute();
    const baseItems = parts[0] === "domain"
      ? concepts.filter((concept) => concept.domains.includes(parts[1]))
      : concepts;
    filter.addEventListener("input", () => {
      const query = filter.value.trim().toLocaleLowerCase("zh-CN");
      const filtered = query ? baseItems.filter((concept) => concept.searchText.includes(query)) : baseItems;
      document.querySelector("#directory-results").innerHTML = directoryMarkup(filtered);
      document.querySelector("#directory-count").textContent = `${formatNumber(filtered.length)} 个概念`;
    });
  }
  document.querySelectorAll("[data-random]").forEach((button) => button.addEventListener("click", goRandom));
}

function searchConcepts(query) {
  const normalized = query.trim().toLocaleLowerCase("zh-CN");
  if (!normalized) return [];
  return concepts.map((concept) => {
    const name = concept.name.toLocaleLowerCase("zh-CN");
    let score = 0;
    if (name === normalized) score += 100;
    else if (name.startsWith(normalized)) score += 60;
    else if (name.includes(normalized)) score += 40;
    if (concept.nameEn.toLocaleLowerCase().includes(normalized)) score += 25;
    if (concept.aliases.some((alias) => alias.toLocaleLowerCase().includes(normalized))) score += 24;
    if (concept.domains.some((domain) => domain.toLocaleLowerCase().includes(normalized))) score += 18;
    if (concept.tags.some((tag) => tag.toLocaleLowerCase().includes(normalized))) score += 12;
    if (concept.searchText.includes(normalized)) score += 5;
    return { concept, score };
  }).filter((result) => result.score > 0).sort((a, b) => b.score - a.score || a.concept.name.localeCompare(b.concept.name, "zh-CN")).slice(0, 24);
}

function updateSearch() {
  const query = searchInput.value;
  const results = searchConcepts(query);
  searchHint.hidden = Boolean(query.trim());
  searchResults.innerHTML = query.trim() && !results.length
    ? `<div class="empty">没有找到“${escapeHtml(query)}”。试试更短的关键词。</div>`
    : results.map(({ concept }) => `
      <a class="search-result" href="${conceptUrl(concept.name)}">
        <div><strong>${escapeHtml(concept.name)}</strong><p>${escapeHtml(concept.excerpt)}</p></div>
        <span>${escapeHtml(concept.domains[0] || "跨领域")}</span>
      </a>`).join("");
  searchResults.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeSearch));
}

function openSearch(initial = "") {
  if (!searchDialog.open) searchDialog.showModal();
  searchInput.value = initial;
  updateSearch();
  requestAnimationFrame(() => searchInput.focus());
}

function closeSearch() {
  if (searchDialog.open) searchDialog.close();
}

function goRandom() {
  const current = parseRoute()[0] === "concept" ? parseRoute().slice(1).join("/") : "";
  let concept = concepts[Math.floor(Math.random() * concepts.length)];
  if (concept.name === current) concept = concepts[(concepts.indexOf(concept) + 1) % concepts.length];
  location.hash = conceptUrl(concept.name).slice(1);
}

function updateReadingProgress() {
  if (parseRoute()[0] !== "concept") {
    progressBar.style.width = "0";
    return;
  }
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const progress = scrollable > 0 ? Math.min(100, (window.scrollY / scrollable) * 100) : 0;
  progressBar.style.width = `${progress}%`;
}

async function init() {
  try {
    const response = await fetch("./concepts.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    concepts = data.concepts.map((concept) => ({
      ...concept,
      searchText: `${concept.name} ${concept.nameEn} ${concept.aliases.join(" ")} ${concept.domains.join(" ")} ${concept.tags.join(" ")} ${concept.excerpt} ${concept.html.replace(/<[^>]+>/g, " ")}`.toLocaleLowerCase("zh-CN"),
    }));
    conceptByName = new Map(concepts.map((concept) => [concept.name, concept]));
    document.querySelector("#build-time").textContent = `最近构建 ${data.generatedAt.replace("T", " ")} UTC`;
    renderRoute();
  } catch (error) {
    console.error(error);
    app.innerHTML = `<div class="page-shell"><header class="page-header"><div class="eyebrow">无法载入</div><h1>概念数据没有成功打开。</h1><p>请先运行构建脚本，并通过本地网页服务访问。</p></header></div>`;
  }
}

window.addEventListener("hashchange", renderRoute);
window.addEventListener("scroll", updateReadingProgress, { passive: true });
document.querySelector("#search-trigger").addEventListener("click", () => openSearch());
document.querySelector("#search-close").addEventListener("click", closeSearch);
document.querySelector("#random-link").addEventListener("click", goRandom);
searchInput.addEventListener("input", updateSearch);
searchDialog.addEventListener("click", (event) => { if (event.target === searchDialog) closeSearch(); });
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    openSearch();
  }
  if (event.key === "Escape") closeSearch();
});

init();
