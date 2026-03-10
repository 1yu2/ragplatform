import { InboxOutlined } from '@ant-design/icons';
import { Alert, Typography, Upload, message } from 'antd';
import type { UploadProps } from 'antd';
import { uploadPdf } from '../services/api';

export default function UploadPage() {
  const props: UploadProps = {
    accept: '.pdf',
    maxCount: 1,
    customRequest: async ({ file, onSuccess, onError }) => {
      try {
        const result = await uploadPdf(file as File);
        message.success(`上传成功: ${result.file_id}`);
        onSuccess?.(result);
      } catch (err) {
        onError?.(err as Error);
      }
    }
  };

  return (
    <div>
      <Typography.Title level={4}>文件上传</Typography.Title>
      <Alert type="info" showIcon message="仅支持 PDF，最大 100MB；系统会自动进行去重与入库任务。" style={{ marginBottom: 16 }} />
      <Upload.Dragger {...props}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽 PDF 到此处上传</p>
      </Upload.Dragger>
    </div>
  );
}
