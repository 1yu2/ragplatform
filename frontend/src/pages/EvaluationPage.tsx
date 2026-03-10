import { Button, Card, Col, Row, Statistic, Table, Typography } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useEffect, useMemo, useState } from 'react';
import { historyEvaluation, latestEvaluation, runEvaluation } from '../services/api';

export default function EvaluationPage() {
  const [latest, setLatest] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  async function load() {
    const [l, h] = await Promise.all([latestEvaluation(), historyEvaluation()]);
    setLatest(l);
    setHistory(h || []);
  }

  useEffect(() => {
    void load();
  }, []);

  const option = useMemo(() => {
    const rows = [...history].reverse();
    return {
      tooltip: { trigger: 'axis' },
      legend: { data: ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall'] },
      xAxis: { type: 'category', data: rows.map((x) => x.created_at?.slice(5, 16) || '-') },
      yAxis: { type: 'value', min: 0, max: 1 },
      series: [
        { name: 'faithfulness', type: 'line', data: rows.map((x) => x.faithfulness) },
        { name: 'answer_relevancy', type: 'line', data: rows.map((x) => x.answer_relevancy) },
        { name: 'context_precision', type: 'line', data: rows.map((x) => x.context_precision) },
        { name: 'context_recall', type: 'line', data: rows.map((x) => x.context_recall) }
      ]
    };
  }, [history]);

  return (
    <div>
      <Typography.Title level={4}>评估</Typography.Title>
      <Button
        type="primary"
        style={{ marginBottom: 16 }}
        onClick={async () => {
          await runEvaluation();
          await load();
        }}
      >
        运行评估
      </Button>

      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="Faithfulness" value={latest?.faithfulness ?? 0} precision={3} /></Card></Col>
        <Col span={6}><Card><Statistic title="Answer Relevancy" value={latest?.answer_relevancy ?? 0} precision={3} /></Card></Col>
        <Col span={6}><Card><Statistic title="Context Precision" value={latest?.context_precision ?? 0} precision={3} /></Card></Col>
        <Col span={6}><Card><Statistic title="Context Recall" value={latest?.context_recall ?? 0} precision={3} /></Card></Col>
      </Row>

      <Card title="指标趋势" style={{ marginTop: 16 }}>
        <ReactECharts option={option} style={{ height: 320 }} />
      </Card>

      <Card title="历史记录" style={{ marginTop: 16 }}>
        <Table
          rowKey="id"
          dataSource={history}
          columns={[
            { title: '时间', dataIndex: 'created_at' },
            { title: 'Faith', dataIndex: 'faithfulness' },
            { title: 'Rel', dataIndex: 'answer_relevancy' },
            { title: 'P', dataIndex: 'context_precision' },
            { title: 'R', dataIndex: 'context_recall' },
            { title: 'Overall', dataIndex: 'overall_score' }
          ]}
        />
      </Card>
    </div>
  );
}
