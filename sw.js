/* 상하이 소통카드 — 오프라인 캐시
   페이지(문서)는 네트워크 우선 + 3.5초 타임아웃 후 캐시로 폴백:
   온라인이면 항상 최신, 중국처럼 느리거나 막혀도 저장된 화면으로 바로 뜹니다. */
const CACHE = 'shanghai-talk-v7';
const ASSETS = ['./', './index.html', './manifest.json', './icon.svg'];
const TIMEOUT = 3500;

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => Promise.all(ASSETS.map(u => c.add(new Request(u, {cache: 'reload'})).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  const net = fetch(req, {cache: 'no-store'}).then(res => {
    if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
    return res;
  }).catch(() => null);
  const timeout = new Promise(r => setTimeout(() => r('TIMEOUT'), TIMEOUT));
  const first = await Promise.race([net, timeout]);
  if (first && first !== 'TIMEOUT') return first;
  const hit = (await cache.match(req, {ignoreSearch: true})) ||
              (await cache.match('./index.html', {ignoreSearch: true})) ||
              (await cache.match('./'));
  return hit || new Response('오프라인 상태입니다. 한 번 열었던 화면은 저장되어 있어야 합니다.', {
    status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'}
  });
}

async function cacheFirst(req) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req, {ignoreSearch: true});
  if (hit) {
    fetch(req).then(res => { if (res && res.ok) cache.put(req, res.clone()).catch(() => {}); }).catch(() => {});
    return hit;
  }
  const res = await fetch(req).catch(() => null);
  if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
  return res || new Response('', {status: 504});
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  const isDoc = req.mode === 'navigate' || req.destination === 'document' ||
                url.pathname.endsWith('/') || url.pathname.endsWith('index.html');
  e.respondWith(isDoc ? networkFirst(req) : cacheFirst(req));
});
