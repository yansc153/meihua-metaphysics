/* 花椒短线 Service Worker —— 公网 Tunnel 刷新卡顿修复（2026-09-03 上线，09-04 审查加固 v2）
 *
 * 背景：免费版 Cloudflare 把中国流量路由到海外边缘（实测 CDG 巴黎），
 * 每个未命中边缘缓存的请求都要「边缘→cloudflared→Mac mini」跨洋往返，
 * 静态 index.html TTFB ~1.4s、每个 API ~1–3s，整页刷新 5–8s。
 *
 * 策略（数据诚实性 + 鉴权联动优先）：
 * - 导航请求：network-first（700ms 超时回落本地壳）；超时后网络响应仍会
 *   到达并更新壳缓存——否则慢链路上新部署永远送不进来的旧壳（审查 P1-4）。
 * - /assets/ 指纹文件：cache-first（文件名即版本，immutable）。
 * - GET 数据面 API——只允许 /api/ashare/ /api/us/ /api/drawer/ 三个前缀
 *   （显式白名单；/api/admin/（明文订阅码）、/api/subscription/、
 *   /api/auth/ 一律不接管——审查 P0-1）：
 *   · 带 ?date= 的历史回看：cache-first 且不后台换新（历史不可变）。
 *   · 其余 stale-while-revalidate：有缓存先秒回（响应自带 collected_at/
 *     data_as_of，界面时间标签如实显示），后台拉新；内容有变化才广播。
 *   · 后台拉新收到 401/403（订阅到期/会话撤销）→ 立即清空整个 API 缓存
 *     并广播 hj:auth-lost，页面复核登录态收回数据面（审查 P1-1）。
 *   · 首次填缓存（此前无快照）不广播——页面本来就拿到了 fresh 响应。
 * - 登出（POST /api/auth/logout*）成功 / 'hj:clear-api' 消息：API 缓存
 *   整仓删除 + generation++；在途的后台拉新完成时校验 generation，
 *   变了就丢弃——防止清缓存后被在途响应重新写入（审查 P2-5）。
 * - /ops/ 运维面板：不接管，纯网络。
 */

// 外壳缓存版本。**必须随每次会改变 bundle 的部署而变**——返回访客的
// index.html 是 cache-first 取的，版本不变就意味着旧壳一直引用旧 bundle 哈希，
// 新部署对老用户永不可见（2026-09-11 实证：第四条车道已上线，owner 刷新后
// 仍看到三条车道）。为避免靠人记得手动 bump，vite.config.js 的
// hj-shell-version 插件会在构建时把 dist/index.html 引用的资源哈希烧进这里，
// 构建产物一变版本就变（见 __SHELL_VERSION__ 占位符）。未替换时（dev server
// 直出 public/）版本就是字面占位符，本地开发不需要清壳缓存，无影响。
const SHELL_VERSION = '__SHELL_VERSION__'
const SHELL_CACHE = `hj-shell-${SHELL_VERSION}`
// v2（2026-09-04）：升版即孤儿化 v1——旧 SW 存量里可能含 /api/admin 响应
// （明文订阅码），activate 清理会把 v1 整仓删除，设备上不再残留
// v3（2026-09-09）：升版清掉「今日 ?date=」被 cache-first 固化的旧响应
// （如两点半精选未公布/游资未采到时的快照，会永久滞留到登出才消失）
// v4（2026-09-09）：复盘板块重构（reviewViews.jsx 拆件+响应契约扩展：
// for review API 新增 summary.market/days.lanes/strategies.annualized_est_pct）
const API_CACHE = 'hj-api-v4'
// 导航超时：网络优先，超时回落缓存壳。**故意保持低于外网往返**——2026-09-03
// 的优化就是靠命中壳缓存把公网刷新从 4–6s 压到 <0.5s（Cloudflare 把中国流量
// 路由到海外边缘，单程边缘→cloudflared→Mac mini 约 1s；2026-09-11 实测公网
// TTFB 1.37–2.69s）。所以超时几乎每次都会触发，这是设计如此，不是 bug。
//
// 由此带来一个必须守住的约束：**回落用的壳必须永远属于当前构建**，否则
// 「快」会变成「旧」。这就是上面 SHELL_VERSION 必须随构建变化的原因——
// 升版时 activate 会删掉旧壳，下一次导航没有旧壳可回落，即使超时也走 network
// 拿到新 HTML。2026-09-11 owner 报「UI 没有任何改变」正是这条约束被破坏：
// SHELL_CACHE 自 v1 起从未升版，旧壳一直引用旧 bundle 哈希。
const NAV_TIMEOUT_MS = 700

function chinaToday() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date())
}
// 只缓存订阅数据面三族；admin（明文订阅码）/subscription/auth 永不进 Cache Storage
// 抽屉已冻结、前端零调用(2026-09-07 审查 P2):白名单只留两个活跃数据面
const API_PREFIXES = ['/api/ashare/', '/api/us/']

// 清缓存代际：logout/clear-api 时 +1，在途 fetchFresh 完成时校验
let apiGeneration = 0

self.addEventListener('install', () => {
  // 不 precache：首访无缓存属正常路径，install 即激活，避免排队等旧 SW
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys()
    await Promise.all(names.filter((name) => name !== SHELL_CACHE && name !== API_CACHE).map((name) => caches.delete(name)))
    await self.clients.claim()
  })())
})

async function clearApiCache() {
  apiGeneration += 1
  await caches.delete(API_CACHE)
}

self.addEventListener('message', (event) => {
  if (event.data === 'hj:clear-api' || event.data?.type === 'hj:clear-api') {
    event.waitUntil(clearApiCache())
  }
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') {
    // 登出成功后清 API 缓存（POST 不缓存，respondWith 直通避免双发请求）
    if (/\/api\/auth\/logout(-all)?$/.test(new URL(request.url).pathname)) {
      event.respondWith((async () => {
        const response = await fetch(request)
        if (response.ok) await clearApiCache()
        return response
      })())
    }
    return
  }
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/ops/')) return
  if (url.pathname.startsWith('/api/')) {
    if (url.pathname.startsWith('/api/us/metaphysics/')) return
    if (API_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
      event.respondWith(apiStrategy(request, url))
    }
    // 白名单外的 /api/*（auth/admin/subscription）原样直通
    return
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(request, SHELL_CACHE))
    return
  }
  if (request.mode === 'navigate') {
    event.respondWith(navigationStrategy(request, event))
  }
})

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName)
  const cached = await cache.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) cache.put(request, response.clone())
  return response
}

async function navigationStrategy(request, event) {
  const cache = await caches.open(SHELL_CACHE)
  const network = fetch(request)
  try {
    const response = await Promise.race([
      network,
      new Promise((_, reject) => setTimeout(() => reject(new Error('nav-timeout')), NAV_TIMEOUT_MS)),
    ])
    if (response && response.ok) {
      // 统一以 '/' 为键存放（/?view=XX 与 / 同壳），下次超时回落用。
      // 必须 waitUntil 托底：这里已经 resolve 了 respondWith，SW 随时可能被
      // 回收，后台的 cache.put 会被直接掐掉——壳缓存「有时写了有时没写」正是
      // 这个原因（2026-09-11 排查）。
      event.waitUntil(cache.put('/', response.clone()))
      return response
    }
  } catch {
    // 超时/失败：先回本地壳保刷新速度（09-03 的性能契约）。
    // 但回落旧壳意味着用户看到的是**上一个构建**的界面，而原实现只把新壳
    // 写进缓存等「下一次刷新」——用户会觉得部署根本没生效（2026-09-11
    // owner 报「前端 UI 没有任何改变」）。所以这里在发现「缓存壳 ≠ 新壳」
    // 时主动通知页面自我刷新一次；页面侧有一次性守卫（见 pwa.ts），
    // 结构上不可能形成刷新循环。真离线时 network 永不 resolve，退化为原行为。
    const cached = await cache.match('/')
    const background = network
      .then(async (response) => {
        if (!response || !response.ok) return
        // 必须先 put 再通知:页面收到消息立刻 reload,新导航 700ms 超时后回落
        // cache.match('/')——若通知先发出而 put 还没落地,自动刷新拿到的仍是
        // 旧壳,且 pwa.ts 的一次性守卫已烧掉,用户会停在旧壳(2026-09-11 review)。
        await cache.put('/', response.clone())
        if (cached) {
          const [cachedBody, freshBody] = await Promise.all([
            cached.clone().text(),
            response.clone().text(),
          ])
          if (cachedBody !== freshBody) {
            const clients = await self.clients.matchAll({ type: 'window' })
            for (const client of clients) client.postMessage({ type: 'hj:shell-updated' })
          }
        }
      })
      .catch(() => {})
    // 同样必须托底，否则通知逻辑跟上面的 cache.put 一样会被回收掉
    event.waitUntil(background)
    if (cached) return cached
    return network
  }
  return network
}

// 重建 Response 时剥掉传输层头：body 已解压为明文，保留 gzip 声明会在
// 部分 Chromium 上触发 ERR_CONTENT_DECODING_FAILED（审查 P2-1）
function rebuildHeaders(headers) {
  const clean = new Headers(headers)
  clean.delete('content-encoding')
  clean.delete('content-length')
  return clean
}

async function apiStrategy(request, url) {
  const cache = await caches.open(API_CACHE)
  // 历史回看（?date=YYYY-MM-DD）：内容不可变，只做 cache-first，
  // 不后台换新（每次跨洋 revalidation 对历史数据纯属浪费）。
  // 例外：date=今天——今日数据盘中各车道陆续公布/落库，cache-first 会把
  // 「尚未公布」的旧响应永久滞留（作战台切回今日、两点半精选消失的根因），
  // 属于今天的请求走下方 SWR，靠后台换新自愈。
  const dateParam = url.searchParams.get('date')
  if (dateParam && dateParam !== chinaToday()) {
    const cached = await cache.match(request)
    if (cached) return cached
    const response = await fetch(request)
    // 订阅过期/会话撤销同样要清缓存并广播(2026-09-07 审查 P2):
    // 此前该分支直接 return,历史回看首拉 401 只渲染 error 且缓存不清。
    if (response.status === 401 || response.status === 403) {
      await clearApiCache()
      const clients = await self.clients.matchAll()
      clients.forEach((client) => client.postMessage({ type: 'hj:auth-lost' }))
      return response
    }
    if (response.ok) {
      const text = await response.text()
      if ((response.headers.get('content-type') ?? '').includes('application/json')) {
        cache.put(request, new Response(text, { status: response.status, statusText: response.statusText, headers: rebuildHeaders(response.headers) }))
      }
      return new Response(text, { status: response.status, statusText: response.statusText, headers: rebuildHeaders(response.headers) })
    }
    return response
  }

  const cached = await cache.match(request)
  const generation = apiGeneration
  const fetchFresh = (async () => {
    try {
      const response = await fetch(request)
      if (response.status === 401 || response.status === 403) {
        // 订阅到期 / 会话撤销：清缓存 + 广播，页面收回数据面（审查 P1-1）
        await clearApiCache()
        const clients = await self.clients.matchAll()
        clients.forEach((client) => client.postMessage({ type: 'hj:auth-lost' }))
        return response
      }
      if (!response.ok) return response
      const text = await response.text()
      const contentType = response.headers.get('content-type') ?? ''
      if (contentType.includes('application/json')) {
        // 注意：给页面返回的 cached Response 体只能读一次；diff 比较必须
        // 重新 match 一份独立副本，绝不能直接读将返回的那份。
        const prev = await cache.match(request)
        const prevText = prev ? await prev.text() : null
        if (apiGeneration !== generation) return null // 清缓存发生在拉新途中，丢弃
        await cache.put(request, new Response(text, { status: response.status, statusText: response.statusText, headers: rebuildHeaders(response.headers) }))
        // 仅「已有旧快照且内容变化」才广播：首次填缓存页面已拿到 fresh，
        // 广播只会造成多余重拉；无变化广播会形成通知→重拉→再通知循环
        if (prevText !== null && prevText !== text) {
          const clients = await self.clients.matchAll()
          clients.forEach((client) => client.postMessage({ type: 'hj:api-updated', path: url.pathname }))
        }
      }
      return new Response(text, { status: response.status, statusText: response.statusText, headers: rebuildHeaders(response.headers) })
    } catch {
      return null
    }
  })()
  if (cached) {
    // 秒回本地快照，后台静默换新
    fetchFresh.catch(() => {})
    return cached
  }
  const fresh = await fetchFresh
  if (fresh) return fresh
  return new Response(
    JSON.stringify({ status: 'error', reason: '网络不可用，且本地无缓存快照' }),
    { status: 502, headers: { 'content-type': 'application/json' } },
  )
}
