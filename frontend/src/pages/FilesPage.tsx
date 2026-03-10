import { Button, Popconfirm, Space, Table, Tag, Typography, message } from 'antd';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { deleteFile, listFilesPaged, reprocessFile } from '../services/api';

function statusColor(status: string): string {
  if (status === 'SUCCESS') return 'green';
  if (status === 'RUNNING') return 'blue';
  if (status === 'FAILED') return 'red';
  return 'default';
}

export default function FilesPage() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);

  async function load(targetPage = page, targetPageSize = pageSize) {
    setLoading(true);
    try {
      const offset = (targetPage - 1) * targetPageSize;
      const resp = await listFilesPaged(targetPageSize, offset);
      setData(resp.items || []);
      setTotal(Number(resp.total || 0));
    } catch (err: any) {
      message.error(err?.response?.data?.message || '加载文件列表失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(page, pageSize);
    const timer = setInterval(() => {
      void load(page, pageSize);
    }, 3000);
    return () => clearInterval(timer);
  }, [page, pageSize]);

  async function handleDelete(fileId: string) {
    try {
      await deleteFile(fileId);
      message.success('已删除文件');
      const shouldGoPrev = page > 1 && data.length <= 1;
      const nextPage = shouldGoPrev ? page - 1 : page;
      if (nextPage !== page) {
        setPage(nextPage);
        return;
      }
      await load(nextPage, pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.message || '删除失败');
    }
  }

  return (
    <div>
      <Typography.Title level={4}>文档列表</Typography.Title>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={data}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (v) => `共 ${v} 条`,
          pageSizeOptions: [10, 20, 50, 100],
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          }
        }}
        columns={[
          { title: '文件名', dataIndex: 'file_name' },
          { title: '大小(B)', dataIndex: 'size_bytes' },
          { title: 'SHA256', dataIndex: 'sha256', ellipsis: true },
          { title: '状态', dataIndex: 'status', render: (v: string) => <Tag color={statusColor(v)}>{v}</Tag> },
          {
            title: '操作',
            render: (_, row) => (
              <Space>
                <Link to={`/kb/files/${row.id}/preview`}>预览</Link>
                <Button
                  size="small"
                  onClick={async () => {
                    try {
                      await reprocessFile(row.id);
                      message.success('已触发重跑');
                      void load(page, pageSize);
                    } catch (err: any) {
                      message.error(err?.response?.data?.message || '重跑触发失败');
                    }
                  }}
                >
                  重跑
                </Button>
                <Popconfirm
                  title="确认删除该文件？"
                  description="会同步删除数据库、向量库和对象存储中的该文件数据。"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={() => void handleDelete(row.id)}
                >
                  <Button size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            )
          }
        ]}
      />
    </div>
  );
}
