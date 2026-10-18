import { useEffect, useState } from 'react'

function Cell({ item }) {
  if (!item || item.status === 'missing' || item.tier === '缺价') {
    return <article className="error-card"><strong>{item?.symbol || '标的'}</strong><small>缺价</small></article>
  }
  return <article className="error-card">
    <strong>{item.symbol} · {item.hexagram}</strong>
    <small>起势 {item.qishi_tier}，{item.qishi_phrase}</small>
    <small>收势 {item.shoushi_tier}，{item.shoushi_phrase}</small>
    <small>{item.qi_detail}</small>
    <small>互卦 {item.mutual}{item.reversal ? ' · 变盘日' : ''}</small>
  </article>
}

export function UsMeihuaDaily() {
  const [body, setBody] = useState(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    fetch('/api/us/metaphysics/daily', { credentials: 'include' })
      .then((response) => response.json())
      .then(setBody)
      .catch(() => setFailed(true))
  }, [])
  if (failed) return <p>数据读取失败</p>
  if (!body) return <p>读取中</p>
  if (body.status !== 'ok') return <p>{body.reason || '不可用'}</p>
  const data = body.data || {}
  return <section>
    <Cell item={{ ...data.index, symbol: '标普' }} />
    <h2>板块</h2>
    {(data.sectors || []).map((item) => <Cell item={item} key={item.symbol} />)}
    <h2>AI 分组</h2>
    {(data.ai || []).map((item) => <Cell item={item} key={item.symbol} />)}
  </section>
}

export function UsMeihuaQuestion() {
  const [symbol, setSymbol] = useState('SPX')
  const [note, setNote] = useState('')
  const [when, setWhen] = useState('')
  const [body, setBody] = useState(null)
  const [failed, setFailed] = useState(false)
  const submit = (event) => {
    event.preventDefault()
    setFailed(false)
    const asked = when ? new Date(when).toISOString() : new Date().toISOString()
    fetch('/api/us/metaphysics/question', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, note, asked_at: asked }),
    }).then((response) => response.json()).then(setBody).catch(() => setFailed(true))
  }
  return <section>
    <form onSubmit={submit}>
      <label>代码 <input value={symbol} onChange={(event) => setSymbol(event.target.value)} /></label>
      <label>事项 <input value={note} onChange={(event) => setNote(event.target.value)} /></label>
      <label>时间 <input type="datetime-local" value={when} onChange={(event) => setWhen(event.target.value)} /></label>
      <button type="submit">起卦</button>
    </form>
    {failed ? <p>数据读取失败</p> : null}
    {body && body.status !== 'ok' ? <p>{body.reason || '不可用'}</p> : null}
    {body && body.status === 'ok' ? <Cell item={body.data} /> : null}
  </section>
}
