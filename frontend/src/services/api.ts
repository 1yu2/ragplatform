import { http } from './http';

export async function uploadPdf(file: File) {
  const form = new FormData();
  form.append('file', file);
  const resp = await http.post('/files/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } });
  return resp.data.data;
}

export async function listFiles() {
  const resp = await http.get('/files');
  return resp.data.data;
}

export async function listFilesPaged(limit = 10, offset = 0) {
  const resp = await http.get('/files', { params: { limit, offset } });
  return resp.data.data as {
    items: any[];
    total: number;
    limit: number;
    offset: number;
  };
}

export async function filePreview(fileId: string) {
  const resp = await http.get(`/files/${fileId}/preview`);
  return resp.data.data;
}

export async function reprocessFile(fileId: string) {
  const resp = await http.post(`/files/${fileId}/reprocess`);
  return resp.data.data;
}

export async function deleteFile(fileId: string) {
  const resp = await http.delete(`/files/${fileId}`);
  return resp.data.data;
}

export async function deleteFileChunk(fileId: string, chunkId: string) {
  const resp = await http.delete(`/files/${fileId}/chunks/${chunkId}`);
  return resp.data.data;
}

export async function layoutDebug(fileId: string, usePresigned?: boolean) {
  const suffix = usePresigned === undefined ? '' : `?use_presigned=${usePresigned}`;
  const resp = await http.post(`/files/${fileId}/layout-debug${suffix}`, undefined, {
    timeout: 10 * 60 * 1000
  });
  return resp.data;
}

export async function runEvaluation() {
  const resp = await http.post('/evaluation/run');
  return resp.data.data;
}

export async function latestEvaluation() {
  const resp = await http.get('/evaluation/latest');
  return resp.data.data;
}

export async function historyEvaluation() {
  const resp = await http.get('/evaluation/history');
  return resp.data.data;
}

export async function runtimeSettings() {
  const resp = await http.get('/settings/runtime');
  return resp.data.data;
}

export async function listChatHistory(limit = 50, offset = 0) {
  const resp = await http.get('/chat/history', { params: { limit, offset } });
  return resp.data.data;
}

export async function getChatHistory(chatId: string) {
  const resp = await http.get(`/chat/history/${chatId}`);
  return resp.data;
}

export async function deleteChatHistory(chatId: string) {
  const resp = await http.delete(`/chat/history/${chatId}`);
  return resp.data;
}

export async function clearChatHistory() {
  const resp = await http.delete('/chat/history');
  return resp.data;
}
