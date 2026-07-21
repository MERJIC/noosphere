const VERSION = "merjic-noosphere-offline-v1";
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;
const DATA_URL = "https://raw.githubusercontent.com/MERJIC/noosphere/main/wiki/dist/concepts.json";

const cacheResponse = async (cacheName, request, response) => {
  if (response && response.ok) {
    const cache = await caches.open(cacheName);
    await cache.put(request, response.clone());
  }
  return response;
};

async function cacheShell() {
  const request = new Request("./", { cache: "no-store" });
  const response = await fetch(request);
  await cacheResponse(SHELL_CACHE, request, response);
  const html = await response.clone().text();
  const assets = [...html.matchAll(/(?:src|href)="([^"]+)"/g)]
    .map((match) => new URL(match[1], self.location.href))
    .filter((url) => url.origin === self.location.origin);
  await Promise.all(assets.map(async (url) => {
    try {
      await cacheResponse(SHELL_CACHE, url, await fetch(url));
    } catch {
      // The shell itself remains usable when an optional asset cannot be cached.
    }
  }));
}

async function warmOfflineCache() {
  await cacheShell();
  await cacheResponse(DATA_CACHE, DATA_URL, await fetch(DATA_URL, { cache: "no-store" }));
}

self.addEventListener("install", (event) => {
  event.waitUntil(cacheShell().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("merjic-noosphere-") && !key.startsWith(VERSION)).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "WARM_OFFLINE_CACHE") event.waitUntil(warmOfflineCache());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);

  if (url.href === DATA_URL) {
    event.respondWith((async () => {
      try {
        return await cacheResponse(DATA_CACHE, event.request, await fetch(event.request));
      } catch {
        const cached = await caches.match(event.request);
        if (cached) return cached;
        throw new Error("离线概念数据尚未准备好");
      }
    })());
    return;
  }

  if (event.request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        return await cacheResponse(SHELL_CACHE, event.request, await fetch(event.request));
      } catch {
        return (await caches.match(event.request)) || (await caches.match("./"));
      }
    })());
    return;
  }

  if (url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      return cacheResponse(SHELL_CACHE, event.request, await fetch(event.request));
    })());
  }
});
