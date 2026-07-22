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

function conceptCard(concept, index = 0, compact = false) {
  const domain = concept.domains[0] || "跨领域";
  return `
    <a class="concept-card${compact === true ? " concept-card--compact" : ""}" href="${conceptUrl(concept.name)}">
      <div class="card-meta"><span>NO. ${String(index + 1).padStart(3, "0")}</span><span>${escapeHtml(domain)}</span></div>
      <h3>${escapeHtml(concept.name)}${concept.nameEn ? `<small>${escapeHtml(concept.nameEn)}</small>` : ""}</h3>
      ${compact === true ? "" : `<p>${escapeHtml(concept.excerpt)}</p>`}
      <span class="card-arrow" aria-hidden="true">↗</span>
    </a>`;
}

function renderHome() {
  const daySeed = Math.floor(Date.now() / 86400000);
  const picks = [0, 97, 251].map((offset) => concepts[(daySeed + offset) % concepts.length]);
  const topDomains = data.domains.slice(0, 6);
  return `
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <h1>从一个概念<br><em>开始。</em></h1>
        </div>
        <div class="hero-tools">
          <div class="hero-meta" aria-label="概念库统计">
            <span><strong>${formatNumber(data.stats.concepts)}</strong> 概念</span>
            <span><strong>${formatNumber(data.stats.links)}</strong> 连接</span>
            <span><strong>${formatNumber(data.stats.domains)}</strong> 领域</span>
          </div>
          <form class="hero-search" id="hero-search">
            <label class="sr-only" for="hero-query">搜索概念</label>
            <input id="hero-query" placeholder="搜索概念" autocomplete="off" />
            <button type="submit">搜索</button>
          </form>
          <div class="hero-actions">
            <button class="primary-action" data-random type="button">随机打开</button>
            <a class="secondary-action" href="#/concepts">浏览全部</a>
          </div>
        </div>
      </section>

      <section class="section home-section">
        <div class="section-head">
          <h2>领域</h2>
          <a class="text-link" href="#/domains">全部领域</a>
        </div>
        <div class="domain-grid">
          ${topDomains.map((domain, index) => `
            <a class="domain-card" href="${domainUrl(domain.name)}">
              <span class="domain-index">0${index + 1}</span>
              <h3>${escapeHtml(domain.name)}</h3>
              <p>${formatNumber(domain.count)} 个概念</p>
            </a>`).join("")}
        </div>
      </section>

      <section class="section home-section">
        <div class="section-head">
          <h2>今日概念</h2>
          <button class="nav-link" data-random type="button">换一组</button>
        </div>
        <div class="concept-grid home-concept-grid">${picks.map((concept, index) => conceptCard(concept, index, true)).join("")}</div>
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
      <div class="side-label-row"><div class="side-label">${escapeHtml(title)}</div><span class="side-count">${items.length}</span></div>
      <div class="side-links">
        ${items.length ? items.slice(0, 9).map((item) => `
          <a href="${conceptUrl(item.name)}"><strong>${escapeHtml(item.name)}</strong><i aria-hidden="true">→</i></a>
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
          <div class="side-label">本文目录</div>
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
            ${concept.disciplines.length ? `<div class="meta-row taxonomy-row"><span>细分学科 DISCIPLINE</span><strong>${escapeHtml(concept.disciplines.join(" · "))}</strong></div>` : ""}
            ${concept.applies.length ? `<div class="meta-row taxonomy-row"><span>应用场景 APPLY</span><strong>${escapeHtml(concept.applies.join(" · "))}</strong></div>` : ""}
          </div>
          ${sideLinks("被这些概念提到", backlinks, "暂时没有其他概念提到它")}
          ${sideLinks("本文提到的概念", outgoing, "本文暂时没有链接其他概念")}
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
  const navigate = () => {
    history.pushState(null, "", conceptUrl(concept.name));
    renderRoute();
  };
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduceMotion && typeof document.startViewTransition === "function") {
    document.startViewTransition(navigate);
    return;
  }
  navigate();
  if (!reduceMotion) {
    app.classList.remove("roam-enter");
    void app.offsetWidth;
    app.classList.add("roam-enter");
    window.setTimeout(() => app.classList.remove("roam-enter"), 360);
  }
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

function applyTheme(theme, persist = false) {
  document.documentElement.dataset.theme = theme;
  const dark = theme === "dark";
  const toggle = document.querySelector("#theme-toggle");
  toggle.setAttribute("aria-pressed", String(dark));
  toggle.setAttribute("aria-label", dark ? "切换到日间模式" : "切换到夜间模式");
  toggle.querySelector("[data-theme-label]").textContent = dark ? "日间" : "夜间";
  document.querySelector('meta[name="theme-color"]').setAttribute("content", dark ? "#151713" : "#f3f0e8");
  if (persist) localStorage.setItem("merjic-wiki-theme", theme);
}

function startLiveReload() {
  let currentVersion = null;
  let timerId = null;
  const checkVersion = async () => {
    try {
      const response = await fetch("./__wiki_version", { cache: "no-store" });
      if (!response.ok) {
        if (timerId) window.clearInterval(timerId);
        return;
      }
      const status = await response.json();
      if (currentVersion === null) {
        currentVersion = status.version;
      } else if (status.version !== currentVersion) {
        window.location.reload();
      }
    } catch {
      // A deployed static site has no live-preview endpoint; nothing to do.
      if (timerId) window.clearInterval(timerId);
    }
  };
  checkVersion();
  timerId = window.setInterval(checkVersion, 1500);
}

async function init() {
  try {
    data = await loadConceptData();
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

async function loadConceptData() {
  const sources = [
    "https://raw.githubusercontent.com/MERJIC/noosphere/main/wiki/dist/concepts.json",
    "./concepts.json",
  ];
  let lastError;

  for (const source of sources) {
    try {
      const response = await fetch(source, { cache: "no-store" });
      if (!response.ok) throw new Error(`${source}: HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error("概念数据不可用");
}

window.addEventListener("hashchange", renderRoute);
window.addEventListener("scroll", updateReadingProgress, { passive: true });
document.querySelector("#search-trigger").addEventListener("click", () => openSearch());
document.querySelector("#search-close").addEventListener("click", closeSearch);
document.querySelector("#random-link").addEventListener("click", goRandom);
document.querySelector("#theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next, true);
});
searchInput.addEventListener("input", updateSearch);
searchDialog.addEventListener("click", (event) => { if (event.target === searchDialog) closeSearch(); });
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    openSearch();
  }
  if (event.key === "Escape") closeSearch();
});

applyTheme(document.documentElement.dataset.theme || "light");
startLiveReload();
init();
