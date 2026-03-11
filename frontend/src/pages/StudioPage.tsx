import { useEffect, useMemo, useState } from 'react'
import { GenerationPreview } from '../components/GenerationPreview'
import { NewProductPreview } from '../components/NewProductPreview'
import { PromptEditor } from '../components/PromptEditor'
import { ReferenceTop3Panel } from '../components/ReferenceTop3Panel'
import { SseStatusTimeline } from '../components/SseStatusTimeline'
import { api } from '../lib/api'
import { useTaskSse } from '../lib/useSse'
import type { NewProductDetail, NewProductListItem, SearchItem } from '../lib/types'

function getSessionId() {
  const key = 'mvp_session_id'
  const ex = localStorage.getItem(key)
  if (ex) return ex
  const v = `sess_${Math.random().toString(36).slice(2, 10)}`
  localStorage.setItem(key, v)
  return v
}

export function StudioPage() {
  const [newId, setNewId] = useState('')
  const [newProducts, setNewProducts] = useState<NewProductListItem[]>([])
  const [aspectRatio, setAspectRatio] = useState('3:4')
  const [prompt, setPrompt] = useState('')
  const [refs, setRefs] = useState<SearchItem[]>([])
  const [newProduct, setNewProduct] = useState<NewProductDetail | null>(null)
  const [taskId, setTaskId] = useState('')
  const [busy, setBusy] = useState(false)
  const [info, setInfo] = useState('')
  const [error, setError] = useState('')

  const { states, error: sseError } = useTaskSse(taskId)
  const sessionId = useMemo(() => getSessionId(), [])

  async function refreshNewProducts(keepCurrent = true) {
    const list = await api.listNewProducts(300)
    setNewProducts(list.items)

    if (!keepCurrent || !newId || !list.items.some((x) => x.new_id === newId)) {
      const first = list.items[0]?.new_id || ''
      setNewId(first)
      return first
    }
    return newId
  }

  async function loadProductContext(id: string) {
    if (!id) {
      setNewProduct(null)
      setRefs([])
      return
    }

    const [detail, search] = await Promise.all([
      api.getNewProduct(id),
      api.searchByNewId(id, 3),
    ])
    setNewProduct(detail)
    setRefs(search.items)
  }

  useEffect(() => {
    let canceled = false

    const init = async () => {
      try {
        const id = await refreshNewProducts(false)
        if (!id || canceled) return
        await loadProductContext(id)
      } catch (e) {
        if (!canceled) {
          setError((e as Error).message)
        }
      }
    }

    init()
    return () => {
      canceled = true
    }
  }, [])

  useEffect(() => {
    let canceled = false
    const run = async () => {
      if (!newId) return
      try {
        await loadProductContext(newId)
        if (!canceled) {
          setError('')
        }
      } catch (e) {
        if (!canceled) {
          setError((e as Error).message)
        }
      }
    }
    run()
    return () => {
      canceled = true
    }
  }, [newId])

  async function prepareData() {
    setBusy(true)
    setError('')
    try {
      const status = await api.ingestStatus()
      if (status.ready) {
        const id = await refreshNewProducts(true)
        if (id) {
          await loadProductContext(id)
        }
        setInfo(
          `检测到已有数据（爆款 ${status.products_csv_rows}，新品 ${status.new_products_csv_rows}，Milvus ${status.milvus_entity_count}），已跳过重跑，直接加载 Top-3。当前新品 ${id || '-'}。`,
        )
        return
      }

      const [prod, np] = await Promise.all([
        api.ingestProducts(1000),
        api.ingestNewProducts(1000),
      ])
      await api.initMilvus()
      const vec = await api.ingestMilvusProducts(1000, 32)
      const id = await refreshNewProducts(true)
      if (id) {
        await loadProductContext(id)
      }
      setInfo(
        `导入完成：爆款 ${prod.written_rows} 条（扫描 ${prod.scanned_images}），新品 ${np.written_rows} 条；Milvus 向量入库 ${vec.upserted_rows || 0} 条，跳过 ${vec.skipped_rows || 0} 条未变化数据。当前新品 ${id || '-'} 已加载 Top-3 参考图。`,
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function generate() {
    if (!newId) {
      setError('请先选择新品')
      return
    }

    setBusy(true)
    setError('')
    try {
      const res = await api.generate({
        new_id: newId,
        aspect_ratio: aspectRatio,
        user_prompt_override: prompt || undefined,
        session_id: sessionId,
      })
      setTaskId(res.task_id)
      setInfo(`任务已创建：${res.task_id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="studio-grid">
      <section className="card">
        <h2>生成工作台</h2>
        <div className="form-row">
          <label>新品选择（new_id）</label>
          <select className="input" value={newId} onChange={(e) => setNewId(e.target.value)}>
            {newProducts.length === 0 && <option value="">暂无数据，请先准备数据</option>}
            {newProducts.map((item) => (
              <option key={item.new_id} value={item.new_id}>
                {item.new_id} | {item.category} | {item.style}
              </option>
            ))}
          </select>
          <div className="ref-meta">可选新品数量：{newProducts.length}</div>
        </div>

        <div className="form-row">
          <label>图片比例</label>
          <select className="input" value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
            <option>1:1</option>
            <option>3:4</option>
            <option>4:1</option>
            <option>9:16</option>
          </select>
        </div>

        <div className="button-row">
          <button className="btn" disabled={busy} onClick={prepareData}>准备数据（已存在则跳过重跑）</button>
          <button className="btn" disabled={busy} onClick={() => refreshNewProducts(true)}>刷新新品列表</button>
          <button className="btn primary" disabled={busy} onClick={generate}>开始生成</button>
        </div>

        {info && <p className="ok">{info}</p>}
        {error && <p className="err">{error}</p>}
        {sseError && <p className="err">{sseError}</p>}
      </section>

      <NewProductPreview product={newProduct} />
      <ReferenceTop3Panel items={refs} />
      <PromptEditor value={prompt} onChange={setPrompt} />
      <GenerationPreview taskId={taskId} />
      <SseStatusTimeline states={states} />
    </div>
  )
}
