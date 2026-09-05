/**
 * 新建评测 Modal
 *
 * 选择数据集 + 选择 Agent + 配置评分策略
 * 评分配置包含：维度、权重、Prompt 模板、并发数
 */
import { useEffect, useState } from 'react';
import { Modal, Form, Select, Input, InputNumber, Button, Divider, Typography, message, Space } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { listDatasets, DatasetInfo } from '@/services/dataset';
import { listAgents, AgentInfo } from '@/services/agent';
import { createEvalRun, JudgeConfig } from '@/services/evaluation';

const { Text } = Typography;

export interface EvalCreateModalProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

// 默认评分配置
const DEFAULT_JUDGE_CONFIG: JudgeConfig = {
  provider: 'openai',
  model: 'gpt-4o-mini',
  prompt_template: '请根据以下维度对 Agent 输出进行评分：\n{dimensions}\n\n用户输入：{input}\nAgent 输出：{output}\n期望输出：{expected_output}\n\n请对每个维度给出 0-100 的评分并说明理由。',
  dimensions: ['准确性', '完整性', '相关性'],
  weights: {},
};

export default function EvalCreateModal({ projectId, open, onClose, onSuccess }: EvalCreateModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  // 下拉选项
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);

  // 加载数据集和 Agent 列表
  useEffect(() => {
    if (!open || !projectId) return;
    (async () => {
      setOptionsLoading(true);
      try {
        const [dsList, agList] = await Promise.all([
          listDatasets(projectId),
          listAgents(projectId),
        ]);
        setDatasets(dsList);
        setAgents(agList);
      } catch {
        message.error('加载数据集/Agent 列表失败');
      } finally {
        setOptionsLoading(false);
      }
    })();
  }, [open, projectId]);

  // 初始化默认评分配置
  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        concurrency: 5,
        judge_config: DEFAULT_JUDGE_CONFIG,
      });
    }
  }, [open, form]);

  async function handleSubmit(values: {
    dataset_id: string;
    agent_id: string;
    name?: string;
    judge_config?: JudgeConfig;
    concurrency?: number;
  }) {
    if (!projectId) return;
    setLoading(true);
    try {
      const { dataset_id, agent_id, name, judge_config, concurrency } = values;

      // 构建权重：默认均分
      const dimensions = judge_config?.dimensions ?? DEFAULT_JUDGE_CONFIG.dimensions;
      const weight = 1 / dimensions.length;
      const weights: Record<string, number> = {};
      dimensions.forEach((d) => { weights[d] = Math.round(weight * 100) / 100; });

      await createEvalRun(projectId, {
        dataset_id,
        agent_id,
        name: name || undefined,
        judge_config: {
          ...DEFAULT_JUDGE_CONFIG,
          ...judge_config,
          dimensions,
          weights,
        },
        concurrency: concurrency ?? 5,
      });
      message.success('评测任务创建成功');
      onSuccess();
      onClose();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '创建失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      title="新建评测任务"
      open={open}
      onCancel={onClose}
      footer={null}
      width={640}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        style={{ marginTop: 16 }}
      >
        <Form.Item
          name="dataset_id"
          label="选择数据集"
          rules={[{ required: true, message: '请选择数据集' }]}
        >
          <Select
            placeholder="选择数据集"
            loading={optionsLoading}
            showSearch
            optionFilterProp="label"
            options={datasets.map((d) => ({
              value: d.id,
              label: d.name,
            }))}
          />
        </Form.Item>

        <Form.Item
          name="agent_id"
          label="选择 Agent"
          rules={[{ required: true, message: '请选择 Agent' }]}
        >
          <Select
            placeholder="选择 Agent"
            loading={optionsLoading}
            showSearch
            optionFilterProp="label"
            options={agents.map((a) => ({
              value: a.id,
              label: `${a.name} (v${a.version})`,
            }))}
          />
        </Form.Item>

        <Form.Item name="name" label="任务名称（选填）">
          <Input placeholder="自定义评测任务名称" maxLength={200} />
        </Form.Item>

        <Form.Item name="concurrency" label="并发数">
          <InputNumber min={1} max={20} style={{ width: '100%' }} />
        </Form.Item>

        <Divider orientation="left" style={{ fontSize: 13 }}>评分配置</Divider>

        {/* 嵌套 judge_config */}
        <Form.Item name={['judge_config', 'provider']} label="评分 LLM 提供商">
          <Select
            options={[
              { value: 'openai', label: 'OpenAI' },
              { value: 'azure', label: 'Azure OpenAI' },
              { value: 'deepseek', label: 'DeepSeek' },
              { value: 'zhipu', label: '智谱 GLM' },
            ]}
          />
        </Form.Item>

        <Form.Item name={['judge_config', 'model']} label="评分模型">
          <Select
            showSearch
            options={[
              { value: 'gpt-4o-mini', label: 'gpt-4o-mini (推荐)' },
              { value: 'gpt-4o', label: 'gpt-4o' },
              { value: 'gpt-3.5-turbo', label: 'gpt-3.5-turbo' },
              { value: 'deepseek-chat', label: 'deepseek-chat' },
              { value: 'glm-4', label: 'glm-4' },
            ]}
          />
        </Form.Item>

        <Form.Item
          name={['judge_config', 'prompt_template']}
          label={
            <span>评分 Prompt 模板 <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>（支持 {'{input}'}, {'{output}'}, {'{expected_output}'} 占位）</Text></span>
          }
        >
          <Input.TextArea rows={6} style={{ fontFamily: 'monospace', fontSize: 12 }} />
        </Form.Item>

        {/* 评分维度动态表单 */}
        <Form.Item label="评分维度">
          <div style={{ background: '#fafafa', borderRadius: 6, padding: 12 }}>
            <Form.List name={['judge_config', 'dimensions']}>
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...rest }) => (
                    <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                      <Form.Item {...rest} name={[name]} style={{ marginBottom: 0, flex: 1 }}>
                        <Input placeholder="维度名称" />
                      </Form.Item>
                      {fields.length > 1 && (
                        <MinusCircleOutlined
                          onClick={() => remove(name)}
                          style={{ color: '#ff4d4f', cursor: 'pointer' }}
                        />
                      )}
                    </Space>
                  ))}
                  <Button type="dashed" onClick={() => add('')} block icon={<PlusOutlined />}>
                    添加维度
                  </Button>
                </>
              )}
            </Form.List>
          </div>
        </Form.Item>

        <Form.Item style={{ marginBottom: 0, marginTop: 24, textAlign: 'right' }}>
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" htmlType="submit" loading={loading}>
              创建评测任务
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}