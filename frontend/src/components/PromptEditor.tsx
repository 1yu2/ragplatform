export function PromptEditor({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="card">
      <h3>提示词编辑</h3>
      <textarea
        className="textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="可编辑风格提示词或补充约束..."
      />
    </div>
  )
}
