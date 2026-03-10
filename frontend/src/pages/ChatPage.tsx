import { Alert, Button, Card, Col, Collapse, Empty, Input, List, Popconfirm, Row, Space, Tag, Typography, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { clearChatHistory, deleteChatHistory, getChatHistory, listChatHistory } from '../services/api';
import { markdownToHtml } from '../utils/markdown';

interface Citation {
  ref: string;
  snippet: string;
  markdown?: string;
  score?: number;
}

interface ChatHistoryItem {
  id: string;
  question: string;
  rewritten_question?: string;
  answer: string;
  is_refused: boolean;
  top1_score: number;
  latency_first_token_ms?: number;
  created_at: string;
  citations?: Citation[];
}

function formatTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export default function ChatPage() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [citations, setCitations] = useState<Citation[]>([]);
  const [activeCitationKeys, setActiveCitationKeys] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [streamError, setStreamError] = useState('');
  const [history, setHistory] = useState<ChatHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string>('');
  const [historyActionLoading, setHistoryActionLoading] = useState(false);

  const answerHtml = useMemo(() => markdownToHtml(answer, { citationSup: true }), [answer]);

  async function refreshHistory(autoSelectNewest = false) {
    setHistoryLoading(true);
    try {
      const data = await listChatHistory(100, 0);
      const items: ChatHistoryItem[] = data?.items || [];
      setHistory(items);
      if (autoSelectNewest && items.length > 0) {
        setSelectedHistoryId(items[0].id);
      }
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    void refreshHistory();
  }, []);

  async function openHistory(chatId: string) {
    setHistoryActionLoading(true);
    try {
      const resp = await getChatHistory(chatId);
      if (resp?.code !== 0 || !resp?.data) {
        message.error(resp?.message || '读取历史失败');
        return;
      }
      const item = resp.data as ChatHistoryItem;
      setSelectedHistoryId(item.id);
      setQuestion(item.question || '');
      setAnswer(item.answer || '');
      setCitations(item.citations || []);
      if (!item.citations || item.citations.length === 0) {
        message.info('该历史记录暂无可回显的引用片段');
      }
      setActiveCitationKeys([]);
      setStreamError('');
    } finally {
      setHistoryActionLoading(false);
    }
  }

  async function handleDeleteHistory(chatId: string) {
    setHistoryActionLoading(true);
    try {
      const resp = await deleteChatHistory(chatId);
      if (resp?.code !== 0) {
        message.error(resp?.message || '删除失败');
        return;
      }
      if (selectedHistoryId === chatId) {
        setSelectedHistoryId('');
        setAnswer('');
        setCitations([]);
        setActiveCitationKeys([]);
      }
      await refreshHistory();
      message.success('已删除');
    } finally {
      setHistoryActionLoading(false);
    }
  }

  async function handleClearHistory() {
    setHistoryActionLoading(true);
    try {
      const resp = await clearChatHistory();
      if (resp?.code !== 0) {
        message.error(resp?.message || '清空失败');
        return;
      }
      setHistory([]);
      setSelectedHistoryId('');
      setAnswer('');
      setCitations([]);
      setActiveCitationKeys([]);
      message.success('聊天历史已清空');
    } finally {
      setHistoryActionLoading(false);
    }
  }

  async function ask() {
    if (!question.trim()) return;
    setLoading(true);
    setSelectedHistoryId('');
    setAnswer('');
    setCitations([]);
    setActiveCitationKeys([]);
    setStreamError('');

    try {
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });

      if (!resp.ok) {
        const text = await resp.text();
        setStreamError(`请求失败: HTTP ${resp.status} ${text || ''}`.trim());
        return;
      }

      const reader = resp.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      if (!reader) {
        setStreamError('流式响应不可用');
        return;
      }

      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        const events = buf.split('\n\n');
        buf = events.pop() || '';

        for (const evt of events) {
          const line = evt.trim();
          if (!line.startsWith('data:')) continue;
          try {
            const payload = JSON.parse(line.slice(5).trim());
            if (payload.type === 'token') {
              setAnswer((prev) => prev + payload.data);
            } else if (payload.type === 'final') {
              setAnswer(payload.data.answer || '');
              setCitations(payload.data.citations || []);
              if (payload.data.error) {
                setStreamError(String(payload.data.error));
              }
            }
          } catch {
            // ignore malformed event
          }
        }
      }
    } catch (err: any) {
      setStreamError(err?.message || '请求失败');
    } finally {
      setLoading(false);
      await refreshHistory(true);
    }
  }

  return (
    <div>
      <style>
        {`
          .chat-md { line-height: 1.75; font-size: 14px; }
          .chat-md h1, .chat-md h2, .chat-md h3 { margin: 0 0 8px; }
          .chat-md p { margin: 0 0 8px; }
          .chat-md table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 13px; }
          .chat-md th, .chat-md td { border: 1px solid #d9d9d9; padding: 6px 8px; vertical-align: top; }
          .chat-md img { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 6px; }
        `}
      </style>
      <Typography.Title level={4}>聊天问答</Typography.Title>

      <Row gutter={16}>
        <Col span={8}>
          <Card
            title="聊天历史"
            extra={
              <Popconfirm
                title="确认清空全部聊天历史？"
                okButtonProps={{ danger: true, loading: historyActionLoading }}
                onConfirm={() => void handleClearHistory()}
              >
                <Button size="small" danger loading={historyActionLoading}>
                  清空
                </Button>
              </Popconfirm>
            }
          >
            <List
              loading={historyLoading}
              locale={{ emptyText: <Empty description="暂无历史" /> }}
              dataSource={history}
              renderItem={(item) => (
                <List.Item
                  style={{
                    cursor: 'pointer',
                    background: selectedHistoryId === item.id ? '#f0f5ff' : undefined,
                    borderRadius: 6,
                    paddingInline: 8
                  }}
                  onClick={() => void openHistory(item.id)}
                  actions={[
                    <Popconfirm
                      key={`del_${item.id}`}
                      title="确认删除这条历史？"
                      okButtonProps={{ danger: true, loading: historyActionLoading }}
                      onConfirm={() => void handleDeleteHistory(item.id)}
                    >
                      <Button size="small" type="link" danger onClick={(e) => e.stopPropagation()}>
                        删除
                      </Button>
                    </Popconfirm>
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space size={6}>
                        <Typography.Text ellipsis style={{ maxWidth: 180 }}>
                          {item.question}
                        </Typography.Text>
                        {item.is_refused ? <Tag color="red">无法回答</Tag> : <Tag color="green">已回答</Tag>}
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={2}>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {formatTime(item.created_at)}
                        </Typography.Text>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          top1={Number(item.top1_score || 0).toFixed(3)}
                        </Typography.Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col span={16}>
          <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="输入你的问题"
              onPressEnter={() => void ask()}
            />
            <Button type="primary" loading={loading} onClick={() => void ask()}>
              发送
            </Button>
          </Space.Compact>

          {!!streamError && <Alert type="warning" showIcon message={streamError} style={{ marginBottom: 12 }} />}

          <Card title="回答 (Markdown)" style={{ marginBottom: 12 }} loading={historyActionLoading}>
            {answer ? (
              <>
                <div className="chat-md" dangerouslySetInnerHTML={{ __html: answerHtml }} />
                {citations.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Typography.Text type="secondary">引用角标：</Typography.Text>
                    <Space size={4}>
                      {citations.map((_, idx) => {
                        const key = String(idx + 1);
                        const opened = activeCitationKeys.includes(key);
                        return (
                          <Button
                            key={key}
                            size="small"
                            type={opened ? 'primary' : 'default'}
                            onClick={() => {
                              setActiveCitationKeys((prev) =>
                                prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
                              );
                            }}
                            style={{ paddingInline: 6 }}
                          >
                            <sup>[{key}]</sup>
                          </Button>
                        );
                      })}
                    </Space>
                  </div>
                )}
              </>
            ) : (
              <Alert type="info" showIcon message="等待提问或从左侧选择历史记录" />
            )}
          </Card>

          <Card title="引用原文（Markdown，可展开）">
            <Collapse
              activeKey={activeCitationKeys}
              onChange={(keys) => setActiveCitationKeys((keys as string[]) || [])}
              items={citations.map((item, idx) => {
                const content = item.markdown || item.snippet || '';
                return {
                  key: String(idx + 1),
                  label: (
                    <span>
                      <sup>[{idx + 1}]</sup> {item.ref}
                    </span>
                  ),
                  children: (
                    <div className="chat-md" dangerouslySetInnerHTML={{ __html: markdownToHtml(content, { citationSup: true }) }} />
                  )
                };
              })}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
