import { Component, StrictMode, useCallback, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './pwa.ts'
import { clearAgedApiCache, readAcctHint, writeAcctHint } from './accountHint.ts'
// 2026-09-07 审查 P1 根因修复：styles.css 必须在所有 *.mobile.css 之前。
// 各 view 内部 import 自己的 mobile css，此前 styles.css 排在最后，Vite 按
// 模块图顺序合并后所有 mobile 规则整体在前、styles.css 同名规则在后，
// 同 specificity 必输 → 88 个 !important 军备竞赛。基础样式先落地，mobile
// 覆盖后落地即自然生效。
import './styles.css'
import { Mainline, Auction, Workbench } from './views/ashare/index.js'
import { UsFullView, UsResearchView, UsTodayView, UsWorkbenchView } from './views/usViews.jsx'
import { UsMlStationView } from './views/us/mlStation.jsx'
import { UsMeihuaDaily, UsMeihuaQuestion } from './views/us/metaphysics.jsx'
import { ReviewView } from './views/review/index.jsx'
import { LandingView } from './views/landingView.jsx'
import { SettingsView } from './account/settingsView.jsx'
import { GateOverlay } from './account/gateOverlay.jsx'
import { Header, MarketStrip } from './views/chrome.jsx'
import { OnboardingModal } from './onboarding/OnboardingModal.jsx'
import { FRESH_LOGIN_KEY } from './onboarding/slides.js'

const PAGE_TITLES = {
  'a-mainline': 'A 股主线',
  'a-auction': 'A 股竞价',
  'us-discovery': '美股今日异动',
  'us-full': '全量',
  'us-research': '美股 Alpha 中枢',
  'us-mlstation': '花椒400ETF 4H 信号台',
  'us-meihua-daily': '美股日频',
  'us-meihua-question': '问事',
  workbench: '作战台',
  review: '复盘',
  landing: '花椒短线',
  'account-settings': '账户设置',
}
const VIEW_STATE = {
  LAND: { page: 'landing' },
  ACC: { page: 'account-settings' },
  AS1: { page: 'a-mainline' },
  AS2: { page: 'a-auction' },
  US1: { page: 'us-discovery' },
  US2: { page: 'us-full' },
  US3: { page: 'us-research' },
  US4: { page: 'us-mlstation' },
  US5: { page: 'us-meihua-daily' },
  US6: { page: 'us-meihua-question' },
  WB1: { page: 'workbench', workbenchMarket: 'A股' },
  WB2: { page: 'workbench', workbenchMarket: '美股' },
  RT1: { page: 'review', reviewMarket: 'A股' },
  RT2: { page: 'review', reviewMarket: '美股' },
}

let bootError = null
// dev 预览会话态：登录窗模拟成功后写入，刷新后保持登录预览。
// 生产构建恒为 guest——真实登录态只能来自 /api/me（auth-l1 Step1），不认此键。
function devAcctStateFromSession() {
  if (!import.meta.env.DEV) return 'guest'
  try {
    const value = window.sessionStorage.getItem('hj:acct-state')
    return ['subscribed', 'registered', 'expired'].includes(value) ? value : 'guest'
  } catch { return 'guest' }
}

function viewCodeFromLocation() {
  bootError = null
  // 空串也回落落地页：粘贴「?view=」结尾的 URL 时 get() 返回 ''，?? 对空串
  // 不触发，会走到未知码分支白屏（2026-09-07 审查 P1）。
  const code = new URLSearchParams(window.location.search).get('view')?.toUpperCase() || 'LAND'
  if (!VIEW_STATE[code]) {
    // 未知 ?view= 码不再于模块初始化时 throw 留下白屏；失败被记录并在
    // bootstrap 处渲染为可见错误后重新抛出（fail-fast 且可观测）。
    bootError = new Error(`Unknown Stage 2 view code: ${code}`)
    return 'AS1'
  }
  return code
}

function urlForView(code) {
  const url = new URL(window.location.href)
  // 站点根（D17）：落地页不带 ?view= 参数，保持根 URL 干净。
  if (code === 'LAND') url.searchParams.delete('view')
  else url.searchParams.set('view', code)
  return `${url.pathname}${url.search}${url.hash}`
}

const INITIAL_VIEW_CODE = viewCodeFromLocation()
const INITIAL_VIEW = VIEW_STATE[INITIAL_VIEW_CODE]

class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(error) { return { error } }
  componentDidCatch(error, info) { console.error('[ErrorBoundary] page render failed', error, info) }
  render() {
    if (this.state.error) {
      return <div className="error-card" role="alert"><strong>页面出了点问题</strong><small>请重新加载；技术详情见控制台</small><button onClick={() => window.location.reload()} type="button">重新加载</button></div>
    }
    return this.props.children
  }
}

function App() {
  const [page, setPage] = useState(INITIAL_VIEW.page)
  const [workbenchMarket, setWorkbenchMarket] = useState(INITIAL_VIEW.workbenchMarket ?? 'A股')
  const [reviewMarket, setReviewMarket] = useState(INITIAL_VIEW.reviewMarket ?? 'A股')
  const [aMainlineMode, setAMainlineMode] = useState('sector-live')
  // 账号态（auth-l1）：/api/me 上线前由 AccountSlot 的 dev 预览驱动；
  // onStateChange 是 AccountSlot 内部预览状态的上抛通道，顶栏图标与设置页共用。
  const [acctState, setAcctState] = useState(() => {
    const dev = devAcctStateFromSession()
    if (dev !== 'guest') return dev
    return readAcctHint() ? 'subscribed' : 'guest'
  })
  const [acctUser, setAcctUser] = useState(null)
  // 乐观渲染（sessionStorage 提示 subscribed）时立即放行数据面；否则等
  // /api/auth/me 完成（既不闪遮罩也不发注定 401 的请求，保持 D17 语义）。
  const [authReady, setAuthReady] = useState(() => !import.meta.env.DEV && readAcctHint())
  // 登录后新功能引导：登录成功 + 未看过 → 弹一次（设置页可手动重看）
  const [showOnboarding, setShowOnboarding] = useState(false)
  // 本标签页是否已成功核实过登录态：区分「乐观渲染（hint，未经核实）」与
  // 「已核实会话」。网络失败的降级只针对前者——已核实用户不该被瞬时断网
  // 盖上 GateOverlay；乐观态 fail-open 会造成「伪造 hint+断网=无限离线浏览」。
  const acctVerifiedRef = useRef(false)
  // 「待确认」态的可见信号：/me 连续传输层失败后，把「正在验证访问权限…」
  // 换成「网络异常，正在重试…」并给出手动重试按钮。
  const [authNetError, setAuthNetError] = useState(false)
  // 未确认时的快速重试退避（5s → 15s → 45s → 2min）；拿到明确答复即复位。
  // 5 分钟周期复核是兜底，快退避让「早上网络卡一下/部署窗口」几秒内自愈。
  const authRetryRef = useRef(5000)
  const fetchMeRef = useRef(() => {})
  const scheduleAuthRetry = useCallback(() => {
    const delay = authRetryRef.current
    authRetryRef.current = Math.min(delay * 3, 120000)
    window.setTimeout(() => fetchMeRef.current(), delay)
  }, [])
  // 启动时恢复真实登录态。2026-09-08「登录老是断掉」事故修复：
  // 只有 401/403（后端明确宣告会话作废）才把用户降级为 guest；429/5xx/502
  // 与网络失败是传输层问题、会话生死未明——已核实会话保持现状，未核实的
  // 停留「待确认」态自动重试，绝不误降级把用户赶去重新邮箱验证。
  const fetchMe = useCallback(() => {
    let settled = false
    fetch('/api/auth/me', { credentials: 'include' }).then(async (response) => {
      if (response.status === 401 || response.status === 403) {
        // 会话明确失效：收回数据面，清提示与 SW 的 API 缓存。
        // dev 预览态除外——vite 代理下无真实 cookie，401 是常态，不收回预览。
        settled = true
        authRetryRef.current = 5000
        if (import.meta.env.DEV) return
        acctVerifiedRef.current = false
        writeAcctHint(false)
        clearAgedApiCache()
        setAcctState('guest')
        return
      }
      if (!response.ok) {
        // 限频/服务端瞬时故障：未核实会话停留待确认态等快退避重试；
        // 已核实会话保持现状，5 分钟周期复核兜底收敛。
        if (!acctVerifiedRef.current && !import.meta.env.DEV) {
          setAuthNetError(true)
          scheduleAuthRetry()
        }
        return
      }
      const me = await response.json()
      settled = true
      authRetryRef.current = 5000
      setAuthNetError(false)
      setAcctUser({ email: me.email, tier: me.tier, expiresAt: me.expires_at })
      const expires = me.expires_at ? new Date(me.expires_at).getTime() : 0
      const nextState = !expires ? 'registered' : expires <= Date.now() ? 'expired' : 'subscribed'
      acctVerifiedRef.current = true
      if (nextState !== 'subscribed') {
        writeAcctHint(false)
        clearAgedApiCache()
      } else {
        writeAcctHint(true)
      }
      setAcctState(nextState)
      // 「新鲜登录」事件触发引导：landingView.onLoginSuccess 写 FRESH_LOGIN_KEY，
      // 这里读到就弹一次并清掉。普通 reload / 页面切换 / 打开新 tab（cookie 还有效）不弹。
      try {
        if (window.sessionStorage.getItem(FRESH_LOGIN_KEY) === '1') {
          window.sessionStorage.removeItem(FRESH_LOGIN_KEY)
          setShowOnboarding(true)
        }
      } catch { /* sessionStorage 不可用就当没标记 */ }
    }).catch(() => {
      // 网络失败既不伪造登录也不伪造登出：已核实会话保持现状（瞬时断网
      // 不盖遮罩）；从未核实的停留待确认态自动重试——把断网显示成「请重新
      // 登录」正是「登录老是断掉」的根因。
      if (acctVerifiedRef.current) return
      const dev = devAcctStateFromSession()
      if (dev !== 'guest') { setAcctState(dev); return }
      if (!import.meta.env.DEV) {
        setAuthNetError(true)
        scheduleAuthRetry()
      }
    })
    .finally(() => {
      // 只有拿到明确答复（成功或 401/403）才结束启动等待；传输层失败保持
      // authReady=false，页面继续显示「验证中/重试」而非登录遮罩。
      if (settled || import.meta.env.DEV) setAuthReady(true)
    })
  }, [scheduleAuthRetry])
  useEffect(() => { fetchMeRef.current = fetchMe }, [fetchMe])
  useEffect(() => { fetchMe() }, [fetchMe])
  // SW 撞到 401/403（订阅到期/会话撤销，pwa.ts 桥接 hj:auth-lost）立即复核；
  // 5 分钟周期复核兜底长开页面（订阅中途到期的最终防线）
  useEffect(() => {
    window.addEventListener('hj:auth-lost', fetchMe)
    const timer = window.setInterval(fetchMe, 300000)
    return () => { window.removeEventListener('hj:auth-lost', fetchMe); window.clearInterval(timer) }
  }, [fetchMe])
  // dev 登出：清 dev 会话态 → guest → 回落地页（guest 的唯一合法默认面）。
  // all=true 时打 /api/auth/logout-all——「登出所有设备」此前误接单设备
  // 登出端点，公共电脑上的 30 天滑动会话不会被撤销（审查 P1-3）。
  const handleDevLogout = (all = false) => {
    fetch(all ? '/api/auth/logout-all' : '/api/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {})
    acctVerifiedRef.current = false
    try { window.sessionStorage.removeItem('hj:acct-state') } catch { /* 同上 */ }
    writeAcctHint(false)
    clearAgedApiCache()
    // 不动引导触发标记——下次登录由 landingView.onLoginSuccess 重新写，弹窗会再弹一次
    setAcctUser(null)
    setAcctState('guest')
    selectView('LAND')
  }

  const market = page.startsWith('us-') ? '美股' : page.startsWith('a-') ? 'A股' : page === 'workbench' ? workbenchMarket : reviewMarket

  const applyView = (code) => {
    const view = VIEW_STATE[code]
    if (!view) throw new Error(`Unknown Stage 2 view code: ${code}`)
    setPage(view.page)
    if (view.workbenchMarket) setWorkbenchMarket(view.workbenchMarket)
    if (view.reviewMarket) setReviewMarket(view.reviewMarket)
  }

  const selectView = (code, historyMode = 'push') => {
    applyView(code)
    window.history[historyMode === 'replace' ? 'replaceState' : 'pushState']({ view: code }, '', urlForView(code))
  }

  useEffect(() => {
    window.history.replaceState({ view: INITIAL_VIEW_CODE }, '', urlForView(INITIAL_VIEW_CODE))
    // popstate 回调里的异常没有 React 层捕获者，throw 会变成无提示白屏；
    // 降级为可见的 console.error + 回落默认视图，保持可观测且可恢复。
    const restoreView = () => { const next = viewCodeFromLocation(); if (bootError) { console.error('[restoreView] rejecting stale view code', bootError); applyView('AS1'); return } applyView(next) }
    window.addEventListener('popstate', restoreView)
    return () => window.removeEventListener('popstate', restoreView)
  }, [])

  // 页面切换后回到顶部：视图高度各异，残留的滚动位会把新页落在半空，
  // 与「加载→内容」的弹出叠加成卡顿感，回顶让每次跳转落点稳定。
  useEffect(() => { window.scrollTo(0, 0) }, [page])

  const navigate = (next) => {
    // Cross-section navigation follows the market the user is currently
    // viewing. Keeping separate workbench/review memories made WB2 → 复盘
    // jump to RT1 (and RT2 → 作战台 jump to WB1) on a fresh session.
    const code = next === 'workbench' ? (market === '美股' ? 'WB2' : 'WB1')
      : next === 'review' ? (market === '美股' ? 'RT2' : 'RT1')
        : Object.entries(VIEW_STATE).find(([, view]) => view.page === next)?.[0]
    if (!code) throw new Error(`Page has no registered Stage 2 view code: ${next}`)
    selectView(code)
  }

  // 公开落地页是匿名访客的唯一默认面（D17）：自带终端壳，不渲染数据面 chrome。
  // 注意：早退必须放在全部 hooks 之后——之前放在 useEffect 之前，任何
  // 数据面 → 落地页的 SPA 切换（如账号位「登录」）都会触发
  // "Rendered fewer hooks than expected" 崩溃白屏（React hooks 规则）。
  if (page === 'landing') return <LandingView />

  return <>
    <div className={`app ${market === '美股' ? 'market-us' : ''}`}>
    <Header page={page} workbenchMarket={workbenchMarket} reviewMarket={reviewMarket} acctState={acctState} acctUser={acctUser} onAcctStateChange={setAcctState} onAcctLogout={handleDevLogout} onMarket={(next) => selectView(page === 'workbench' ? (next === '美股' ? 'WB2' : 'WB1') : (next === '美股' ? 'RT2' : 'RT1'))} onNavigate={navigate} onOpenSettings={() => selectView('ACC')} />
      <MarketStrip market={market} />
    <main aria-label={PAGE_TITLES[page]} className="workspace">
      <h1 className="sr-only">{PAGE_TITLES[page]}</h1>
      <ErrorBoundary key={page}>
      {page === 'account-settings' ? <SettingsView state={acctState} user={acctUser} onGoSubscribe={() => selectView('LAND')} onRedeemed={fetchMe} onLogout={() => handleDevLogout(false)} onLogoutAll={() => handleDevLogout(true)} onReplayOnboarding={() => setShowOnboarding(true)} /> : null}
      {page !== 'account-settings' && !authReady ? (
        <div className="gate-loading">
          {authNetError ? (
            <>
              <span>网络异常，正在重试…</span>
              <button
                className="gate-loading-retry"
                type="button"
                onClick={() => { authRetryRef.current = 5000; setAuthNetError(false); fetchMe() }}
              >
                立即重试
              </button>
            </>
          ) : (
            <span>正在验证访问权限…</span>
          )}
        </div>
      ) : null}
      {page !== 'account-settings' && authReady && acctState !== 'subscribed' ? (
        <GateOverlay
          acctState={acctState}
          onLogin={() => {
            // 复用 accountChrome 约定：回落地页，随后广播打开登录弹窗。
            selectView('LAND')
            setTimeout(() => window.dispatchEvent(new CustomEvent('hj:open-login')), 150)
          }}
          onSubscribe={() => selectView('ACC')}
        />
      ) : null}
      {page !== 'account-settings' && authReady && acctState === 'subscribed' ? (
        <>
          {page === 'a-mainline' ? <Mainline mode={aMainlineMode} onMode={setAMainlineMode} /> : null}
          {page === 'a-auction' ? <Auction /> : null}
          {page === 'us-discovery' ? <UsTodayView /> : null}
          {page === 'us-full' ? <UsFullView /> : null}
          {page === 'us-research' ? <UsResearchView /> : null}
          {page === 'us-mlstation' ? <UsMlStationView /> : null}
          {page === 'us-meihua-daily' ? <UsMeihuaDaily /> : null}
          {page === 'us-meihua-question' ? <UsMeihuaQuestion /> : null}
          {page === 'workbench' ? (workbenchMarket === '美股'
            ? <UsWorkbenchView key="us" />
            : <Workbench key="a" />) : null}
          {page === 'review' ? <ReviewView market={reviewMarket} onMarket={(next) => selectView(next === '美股' ? 'RT2' : 'RT1')} /> : null}
        </>
      ) : null}
      </ErrorBoundary>
    </main>
  </div>
    <OnboardingModal open={showOnboarding} onClose={() => setShowOnboarding(false)} />
  </>
}

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root mount element')
try {
  if (bootError) throw bootError
  // Vite re-evaluates this entry on hot updates. Keep one React root per page
  // so the development console remains signal-only instead of emitting a false
  // duplicate-root error after a stylesheet or component refresh.
  const appRoot = globalThis.__huajiaoAppRoot ??= createRoot(root)
  appRoot.render(<StrictMode><App /></StrictMode>)
} catch (error) {
  // ponytail: bootstrap 失败过去只留空白 #root（白屏，不可观测）；现在把
  // 错误信息渲染为可见面板后重新抛出，失败仍然爆炸。textContent 避免把
  // URL 参数注入 DOM。升级路径：换成带返回首页动作的专用错误视图。
  console.error(error)
  const panel = document.createElement('div')
  panel.className = 'drawer-empty'
  panel.setAttribute('role', 'alert')
  panel.style.height = '100vh'
  panel.textContent = '应用启动失败，请重新加载（详情见控制台）'
  root.replaceChildren(panel)
  throw error
}
