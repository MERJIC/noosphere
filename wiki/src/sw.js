const CACHE_NAME = "merjic-noosphere-v5";
const INDEX_URL = "https://raw.githubusercontent.com/MERJIC/noosphere/main/wiki/dist/concept-index.json";
const DETAIL_ROOT = "https://raw.githubusercontent.com/MERJIC/noosphere/main/wiki/dist/concepts/";
const APP_SHELL = ["/", "/app.js", "/concept-index.json", "/favicon.svg", "/manifest.webmanifest"];

async function cachePut(cache, request, response) {
  if (response && response.ok) await cache.put(request, response.clone());
  return response;
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    return await cachePut(cache, request, await fetch(request));
  } catch {
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;
    throw new Error("网络与离线缓存均不可用");
  }
}

async function tellClients(message) {
  const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  clients.forEach((client) => client.postMessage(message));
}

async function cacheLibrary() {
  const cache = await caches.open(CACHE_NAME);
  const indexResponse = await fetch(INDEX_URL, { cache: "no-store" });
  if (!indexResponse.ok) throw new Error("概念目录下载失败");
  const index = await indexResponse.clone().json();
  await cache.put(INDEX_URL, indexResponse);

  const entries = index.concepts || [];
  const total = entries.length;
  let completed = 0;
  let failed = 0;
  await tellClients({ type: "LIBRARY_PROGRESS", completed, total });

  const worker = async () => {
    while (entries.length) {
      const concept = entries.shift();
      const url = `${DETAIL_ROOT}${concept.id}.json`;
      try {
        if (!await cache.match(url)) {
          const response = await fetch(url, { cache: "no-store" });
          await cachePut(cache, url, response);
        }
      } catch {
        // Keep going: a temporary GitHub request failure should not discard completed pages.
        failed += 1;
      }
      completed += 1;
      if (completed % 12 === 0 || completed === total) {
        await tellClients({ type: "LIBRARY_PROGRESS", completed, total });
      }
    }
  };

  await Promise.all(Array.from({ length: 6 }, worker));
  await tellClients({ type: "LIBRARY_DONE", completed, total, failed });
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.all(APP_SHELL.map(async (url) => {
      try { await cachePut(cache, url, await fetch(url, { cache: "no-store" })); } catch { /* retry at normal navigation */ }
    }));
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    await Promise.all((await caches.keys()).filter((name) => name.startsWith("merjic-noosphere-") && name !== CACHE_NAME).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  const shouldCache = event.request.mode === "navigate" || url.origin === self.location.origin || url.href === INDEX_URL || url.href.startsWith(DETAIL_ROOT);
  if (!shouldCache) return;
  event.respondWith(networkFirst(event.request));
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "CACHE_LIBRARY") return;
  event.waitUntil(cacheLibrary().catch(async () => {
    await tellClients({ type: "LIBRARY_FAILED" });
  }));
});
