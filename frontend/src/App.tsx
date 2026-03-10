import { Layout, Menu } from 'antd';
import { Link, Route, Routes, useLocation } from 'react-router-dom';
import UploadPage from './pages/UploadPage';
import FilesPage from './pages/FilesPage';
import PreviewPage from './pages/PreviewPage';
import ChatPage from './pages/ChatPage';
import EvaluationPage from './pages/EvaluationPage';
import SettingsPage from './pages/SettingsPage';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/kb/upload', label: <Link to="/kb/upload">文件上传</Link> },
  { key: '/kb/files', label: <Link to="/kb/files">文档列表</Link> },
  { key: '/chat', label: <Link to="/chat">聊天问答</Link> },
  { key: '/evaluation', label: <Link to="/evaluation">评估</Link> },
  { key: '/settings', label: <Link to="/settings">系统配置</Link> }
];

export default function App() {
  const location = useLocation();
  const selectedKey = menuItems.find((x) => location.pathname.startsWith(x.key))?.key ?? '/kb/upload';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={220}>
        <div style={{ color: '#fff', padding: 16, fontWeight: 700 }}>RAG 管理系统</div>
        <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]} items={menuItems} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', fontWeight: 600 }}>MVP 开发版</Header>
        <Content style={{ margin: 16, padding: 16, background: '#fff' }}>
          <Routes>
            <Route path="/kb/upload" element={<UploadPage />} />
            <Route path="/kb/files" element={<FilesPage />} />
            <Route path="/kb/files/:fileId/preview" element={<PreviewPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/evaluation" element={<EvaluationPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<UploadPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
