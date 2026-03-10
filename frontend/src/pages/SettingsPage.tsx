import { Card, Descriptions, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { runtimeSettings } from '../services/api';

export default function SettingsPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    void runtimeSettings().then(setData);
  }, []);

  return (
    <div>
      <Typography.Title level={4}>系统配置</Typography.Title>
      <Card>
        <Descriptions column={1} bordered>
          <Descriptions.Item label="环境">{data?.env}</Descriptions.Item>
          <Descriptions.Item label="Milvus">{data?.milvus?.host}:{data?.milvus?.port} / {data?.milvus?.collection}</Descriptions.Item>
          <Descriptions.Item label="MinIO">{data?.minio?.endpoint} / {data?.minio?.bucket}</Descriptions.Item>
          <Descriptions.Item label="Layout API">{data?.layout_api?.url}</Descriptions.Item>
          <Descriptions.Item label="Embedding">{data?.embedding_api?.url} / {data?.embedding_api?.model_name}</Descriptions.Item>
          <Descriptions.Item label="LLM">{data?.llm_api?.url} / {data?.llm_api?.model_name}</Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
