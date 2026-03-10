import { Alert, Button, Card, Col, InputNumber, Modal, Popconfirm, Row, Select, Space, Statistic, Table, Tag, Typography, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { deleteFileChunk, filePreview, layoutDebug } from '../services/api';
import { markdownToHtml } from '../utils/markdown';

export default function PreviewPage() {
  const { fileId = '' } = useParams();
  const [blocks, setBlocks] = useState<any[]>([]);
  const [chunks, setChunks] = useState<any[]>([]);
  const [units, setUnits] = useState<any[]>([]);
  const [markdownPages, setMarkdownPages] = useState<any[]>([]);
  const [pageFilter, setPageFilter] = useState<number | 'all'>('all');
  const [mdPreviewPage, setMdPreviewPage] = useState<number | null>(null);
  const [debugLoading, setDebugLoading] = useState(false);
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const [debugData, setDebugData] = useState<any>(null);
  const [tinyOnly, setTinyOnly] = useState(false);
  const [tinyThreshold, setTinyThreshold] = useState(80);

  const refreshPreview = async () => {
    if (!fileId) return;
    const data = await filePreview(fileId);
    setBlocks(data.blocks || []);
    setChunks(data.chunks || []);
    setUnits(data.units || []);
    const mdPages = data.markdown_pages || [];
    setMarkdownPages(mdPages);
    setMdPreviewPage((prev) => (prev == null && mdPages.length > 0 ? Number(mdPages[0].page) : prev));
  };

  useEffect(() => {
    if (!fileId) return;
    void refreshPreview();
    const timer = setInterval(() => {
      void refreshPreview();
    }, 3000);
    return () => clearInterval(timer);
  }, [fileId]);

  const pageOptions = useMemo(() => {
    const pages = new Set<number>();
    blocks.forEach((b) => pages.add(Number(b.page || 1)));
    chunks.forEach((c) => pages.add(Number(c.page || 1)));
    markdownPages.forEach((m) => pages.add(Number(m.page || 1)));
    return Array.from(pages).sort((a, b) => a - b);
  }, [blocks, chunks, markdownPages]);

  const filteredBlocks = useMemo(() => {
    if (pageFilter === 'all') return blocks;
    return blocks.filter((x) => Number(x.page) === pageFilter);
  }, [blocks, pageFilter]);

  const filteredChunks = useMemo(() => {
    const byPage = pageFilter === 'all' ? chunks : chunks.filter((x) => Number(x.page) === pageFilter);
    if (!tinyOnly) return byPage;
    return byPage.filter((x) => String(x.chunk_text || '').trim().length <= tinyThreshold);
  }, [chunks, pageFilter, tinyOnly, tinyThreshold]);

  const filteredUnits = useMemo(() => {
    if (pageFilter === 'all') return units;
    return units.filter((x) => Number(x.page) === pageFilter);
  }, [units, pageFilter]);

  const filteredMarkdownPages = useMemo(() => {
    if (pageFilter === 'all') return markdownPages;
    return markdownPages.filter((x) => Number(x.page) === pageFilter);
  }, [markdownPages, pageFilter]);

  const mdPageOptions = useMemo(() => markdownPages.map((x) => Number(x.page)).sort((a, b) => a - b), [markdownPages]);
  const activeMdPage = useMemo(() => {
    if (pageFilter !== 'all') return Number(pageFilter);
    if (mdPreviewPage != null) return mdPreviewPage;
    return mdPageOptions[0] ?? null;
  }, [pageFilter, mdPreviewPage, mdPageOptions]);

  const activeMarkdown = useMemo(() => {
    if (activeMdPage == null) return '';
    const row = markdownPages.find((x) => Number(x.page) === activeMdPage);
    return row?.markdown || '';
  }, [markdownPages, activeMdPage]);

  const activeMarkdownHtml = useMemo(() => markdownToHtml(activeMarkdown), [activeMarkdown]);

  return (
    <div>
      <style>
        {`
          .md-render { line-height: 1.7; font-size: 14px; }
          .md-render h1, .md-render h2, .md-render h3 { margin: 0 0 8px; }
          .md-render p { margin: 0 0 8px; }
          .md-render table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 13px; }
          .md-render th, .md-render td { border: 1px solid #d9d9d9; padding: 6px 8px; vertical-align: top; }
          .md-render img { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 6px; }
          .md-render figure { margin: 8px 0; }
          .md-render .md-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; background: #f0f5ff; color: #1d39c4; margin-bottom: 6px; }
        `}
      </style>
      <Typography.Title level={4}>解析预览</Typography.Title>
      <Space style={{ marginBottom: 12 }}>
        <Button
          loading={debugLoading}
          onClick={async () => {
            if (!fileId) return;
            setDebugLoading(true);
            setDebugModalOpen(true);
            setDebugData({ code: -1, message: '请求中，请稍候...', data: null });
            try {
              const data = await layoutDebug(fileId);
              setDebugData(data);
              if (data.code !== 0) {
                message.error(`诊断失败: ${data.message || 'unknown error'}`);
              }
            } catch (err: any) {
              const msg = err?.response?.data?.message || err?.message || 'unknown error';
              setDebugData({
                code: 1003,
                message: 'layout debug request failed',
                data: { error: msg }
              });
              message.error(`诊断请求失败: ${msg}`);
            } finally {
              setDebugLoading(false);
            }
          }}
        >
          诊断解析返回
        </Button>
      </Space>

      <Card style={{ marginBottom: 12 }}>
        <Row gutter={16}>
          <Col span={4}><Statistic title="Blocks" value={blocks.length} /></Col>
          <Col span={4}><Statistic title="Units" value={units.length} /></Col>
          <Col span={4}><Statistic title="Chunks" value={chunks.length} /></Col>
          <Col span={6}><Statistic title="Parsed Pages" value={pageOptions.length} /></Col>
          <Col span={6}>
            <Space direction="vertical" size={4}>
              <div style={{ color: '#666' }}>页码过滤</div>
              <Select
                value={pageFilter}
                onChange={(v) => setPageFilter(v)}
                style={{ width: 180 }}
                options={[{ value: 'all', label: '全部页' }, ...pageOptions.map((p) => ({ value: p, label: `第 ${p} 页` }))]}
              />
            </Space>
          </Col>
        </Row>
        <div style={{ marginTop: 8 }}>
          {pageOptions.slice(0, 20).map((p) => <Tag key={p}>{p}</Tag>)}
          {pageOptions.length > 20 && <Tag>...共 {pageOptions.length} 页</Tag>}
        </div>
      </Card>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="版面块(blocks，已按页面逻辑排序)">
            <Table
              size="small"
              rowKey="id"
              dataSource={filteredBlocks}
              pagination={{ pageSize: 20 }}
              columns={[
                { title: '#', dataIndex: 'seq', width: 65 },
                { title: '页码', dataIndex: 'page', width: 70 },
                { title: '类型', dataIndex: 'block_type', width: 110 },
                { title: '标签', dataIndex: 'layout_label', width: 120 },
                { title: '文本', dataIndex: 'text', ellipsis: true }
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="逻辑单元(units，表题/图题合并后)">
            <Table
              size="small"
              rowKey={(r) => `${r.seq}_${r.page}`}
              dataSource={filteredUnits}
              pagination={{ pageSize: 20 }}
              columns={[
                { title: '#', dataIndex: 'seq', width: 65 },
                { title: '页码', dataIndex: 'page', width: 70 },
                { title: '单元类型', dataIndex: 'unit_type', width: 110 },
                { title: '图像类型', dataIndex: 'figure_type', width: 120, ellipsis: true },
                { title: '标题/图题', dataIndex: 'caption', width: 150, ellipsis: true },
                { title: 'Markdown', dataIndex: 'markdown', ellipsis: true }
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card title="向量切分结果(chunks)" style={{ marginTop: 16 }}>
        <Space style={{ marginBottom: 12 }} wrap>
          <Tag color="gold">手动清理小 chunk</Tag>
          <span style={{ color: '#666' }}>仅显示长度 ≤</span>
          <InputNumber min={1} max={1000} value={tinyThreshold} onChange={(v) => setTinyThreshold(Number(v || 80))} />
          <Select
            value={tinyOnly ? 'tiny' : 'all'}
            onChange={(v) => setTinyOnly(v === 'tiny')}
            style={{ width: 140 }}
            options={[
              { value: 'all', label: '显示全部' },
              { value: 'tiny', label: '仅小块' }
            ]}
          />
        </Space>
        <Table
          size="small"
          rowKey="id"
          dataSource={filteredChunks}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '页码', dataIndex: 'page', width: 70 },
            { title: '段落ID', dataIndex: 'paragraph_id', width: 130 },
            { title: '类型', dataIndex: 'block_type', width: 90 },
            {
              title: '长度',
              width: 80,
              render: (_, row) => String(row.chunk_text || '').trim().length
            },
            { title: '文本', dataIndex: 'chunk_text', ellipsis: true },
            {
              title: '操作',
              width: 100,
              render: (_, row) => (
                <Popconfirm
                  title="确认删除这个 chunk？"
                  description="会同步删除向量库中的对应向量。"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={async () => {
                    try {
                      if (!fileId) return;
                      await deleteFileChunk(fileId, row.id);
                      message.success('chunk 已删除');
                      await refreshPreview();
                    } catch (err: any) {
                      message.error(err?.response?.data?.message || '删除 chunk 失败');
                    }
                  }}
                >
                  <Button size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              )
            }
          ]}
        />
      </Card>

      <Card title="PDF -> Markdown 中间结果（原文对照）" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Space wrap>
            <span style={{ color: '#666' }}>Markdown预览页</span>
            <Select
              value={activeMdPage ?? undefined}
              onChange={(v) => setMdPreviewPage(v)}
              style={{ width: 220 }}
              options={mdPageOptions.map((p) => ({ value: p, label: `第 ${p} 页` }))}
            />
          </Space>
          {pageFilter === 'all' && filteredMarkdownPages.length > 30 && (
            <Alert type="info" showIcon message="当前是全部页模式，仅渲染所选页，避免页面卡顿。" />
          )}
          <Row gutter={16}>
            <Col span={12}>
              <Card size="small" title={`原始 Markdown（第 ${activeMdPage ?? '-'} 页）`}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: 520, overflow: 'auto' }}>
                  {activeMarkdown || '暂无内容'}
                </pre>
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" title={`渲染效果（第 ${activeMdPage ?? '-'} 页）`}>
                <div
                  className="md-render"
                  style={{ maxHeight: 520, overflow: 'auto' }}
                  dangerouslySetInnerHTML={{ __html: activeMarkdownHtml || '<p>暂无内容</p>' }}
                />
              </Card>
            </Col>
          </Row>
        </Space>
      </Card>

      <Modal
        title="Layout 诊断结果"
        open={debugModalOpen}
        onCancel={() => setDebugModalOpen(false)}
        footer={null}
        width={980}
      >
        <pre style={{ maxHeight: 560, overflow: 'auto', margin: 0 }}>
          {JSON.stringify(debugData, null, 2)}
        </pre>
      </Modal>
    </div>
  );
}
