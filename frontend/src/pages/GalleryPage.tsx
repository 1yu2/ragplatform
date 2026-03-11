import { useEffect, useState } from 'react'
import { api, apiBaseUrl } from '../lib/api'
import type { TaskDetail, TaskSummary } from '../lib/types'

export function GalleryPage() {
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [taskDetails, setTaskDetails] = useState<Record<string, TaskDetail>>({})
  const [error, setError] = useState('')
  const [feedbackText, setFeedbackText] = useState('')

  async function load() {
    try {
      const rows = await api.listTasks()
      setTasks(rows)
      setError('')

      const top = rows.slice(0, 20)
      const details = await Promise.all(top.map((x) => api.getTask(x.task_id).catch(() => null)))
      const map: Record<string, TaskDetail> = {}
      details.forEach((d, idx) => {
        if (!d) return
        map[top[idx].task_id] = d
      })
      setTaskDetails(map)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function submit(taskId: string, t: 'up' | 'down') {
    if (t === 'down' && feedbackText.trim().length < 10) {
      alert('点踩反馈至少需要 10 个字。')
      return
    }
    await api.submitFeedback(taskId, t, feedbackText)
    await load()
  }

  return (
    <div className="card">
      <h2>历史画廊</h2>
      <p className="muted">查看任务历史、结果图和反馈。</p>
      {error && <p className="err">{error}</p>}

      <div className="form-row">
        <label>反馈文本（点赞可选，点踩必填）</label>
        <textarea className="textarea" value={feedbackText} onChange={(e) => setFeedbackText(e.target.value)} />
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>结果图</th>
            <th>任务ID</th>
            <th>新品ID</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => {
            const detail = taskDetails[t.task_id]
            return (
              <tr key={t.task_id}>
                <td>
                  {detail?.generated_image_url ? (
                    <img className="gallery-thumb" src={`${apiBaseUrl}${detail.generated_image_url}`} alt={t.task_id} />
                  ) : (
                    <span className="muted">-</span>
                  )}
                </td>
                <td>{t.task_id}</td>
                <td>{t.new_id}</td>
                <td>{t.status}</td>
                <td>{new Date(t.created_at).toLocaleString()}</td>
                <td className="button-row">
                  <button className="btn" onClick={() => submit(t.task_id, 'up')}>点赞</button>
                  <button className="btn" onClick={() => submit(t.task_id, 'down')}>点踩</button>
                </td>
              </tr>
            )
          })}
          {tasks.length === 0 && (
            <tr>
              <td colSpan={6} className="muted">暂无任务记录。</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
