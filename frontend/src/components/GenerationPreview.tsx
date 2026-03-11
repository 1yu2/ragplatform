import { useEffect, useState } from 'react'
import { api, apiBaseUrl } from '../lib/api'
import type { TaskDetail } from '../lib/types'

export function GenerationPreview({ taskId }: { taskId: string }) {
  const [task, setTask] = useState<TaskDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!taskId) {
      setTask(null)
      setError('')
      return
    }

    let timer: number | null = null
    let stopped = false

    const load = async () => {
      try {
        const row = await api.getTask(taskId)
        if (stopped) return
        setTask(row)
        setError('')

        if (row.status !== 'done' && row.status !== 'failed') {
          timer = window.setTimeout(load, 1500)
        }
      } catch (e) {
        if (!stopped) {
          setError((e as Error).message)
        }
      }
    }

    load()

    return () => {
      stopped = true
      if (timer) {
        window.clearTimeout(timer)
      }
    }
  }, [taskId])

  return (
    <div className="card">
      <h3>生成预览</h3>
      <div className="ref-meta">任务ID: {taskId || '-'}</div>
      {!taskId && <p className="muted">当前还没有生成任务，请先点击“开始生成”。</p>}
      {error && <p className="err">{error}</p>}
      {task && (
        <>
          <div className="ref-meta">状态: {task.status}</div>
          <div className="ref-meta">选中参考: {task.selected_ref_id || '-'}</div>
          <div className="ref-meta">最终提示词: {task.final_prompt || '-'}</div>
          {task.generated_image_url ? (
            <div>
              <img className="product-preview" src={`${apiBaseUrl}${task.generated_image_url}`} alt={task.task_id} />
              <a className="inline-link" href={`${apiBaseUrl}${task.generated_image_url}`} target="_blank" rel="noreferrer">打开原图</a>
            </div>
          ) : (
            <p className="muted">生成完成后会在这里显示图片。</p>
          )}
        </>
      )}
    </div>
  )
}
