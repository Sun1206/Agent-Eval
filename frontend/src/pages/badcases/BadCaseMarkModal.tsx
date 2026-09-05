/**
 * 标记 Bad Case Modal
 *
 * Trace 信息预览 + 标签选择 + 描述 + 负责人
 * 在 Trace 详情页点击"标记 Bad Case"时弹出
 */
import { useState } from 'react';
import { Modal, Form, Select, Input, Typography, message, Space, Button, Descriptions, Tag } from 'antd';
import {
  markBadCase,
  BadCaseTag,
  BAD_CASE_TAG_LABELS,
  BAD_CASE_TAG_COLORS,
} from '@/services/badcase';

const { Text } = Typography;
const { TextArea } = Input;

export interface BadCaseMarkModalProps {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  /** Trace 预览信息 */
  tracePreview: {
    trace_id: string;
    input?: string;
    output?: string;
    status?: string;
  };
}

export default function BadCaseMarkModal({
  projectId,
  open,
  onClose,
  onSuccess,
  tracePreview,
}: BadCaseMarkModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  async function handleSubmit(values: {
    tag: BadCaseTag;
    description?: string;
    assignee_id?: string;
  }) {
    setLoading(true);
    try {
      await markBadCase(projectId, {
        trace_id: tracePreview.trace_id,
        tag: values.tag,
        description: values.description || undefined,
        assignee_id: values.assignee_id || undefined,
      });
      message.success('Bad Case 标记成功');
      form.resetFields();
      onSuccess();
      onClose();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '标记失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      title="标记 Bad Case"
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
      destroyOnClose
    >
      <div style={{ marginTop: 16 }}>
        {/* Trace 预览 */}
        <div style={{ background: '#fafafa', borderRadius: 6, padding: 12, marginBottom: 20 }}>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            Trace 信息预览
          </Text>
          <Descriptions column={2} size="small" labelStyle={{ fontSize: 12, color: '#666' }} contentStyle={{ fontSize: 12 }}>
            <Descriptions.Item label="Trace ID">
              <Text code copyable={{ text: tracePreview.trace_id }} style={{ fontSize: 11 }}>
                {tracePreview.trace_id.slice(0, 12)}...
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              {tracePreview.status && (
                <Tag color={tracePreview.status === 'SUCCESS' ? 'success' : 'error'}>
                  {tracePreview.status === 'SUCCESS' ? '成功' : '失败'}
                </Tag>
              )}
            </Descriptions.Item>
            {tracePreview.input && (
              <Descriptions.Item label="输入" span={2}>
                <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
                  {tracePreview.input.length > 100
                    ? tracePreview.input.slice(0, 100) + '...'
                    : tracePreview.input}
                </Text>
              </Descriptions.Item>
            )}
            {tracePreview.output && (
              <Descriptions.Item label="输出" span={2}>
                <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
                  {tracePreview.output.length > 100
                    ? tracePreview.output.slice(0, 100) + '...'
                    : tracePreview.output}
                </Text>
              </Descriptions.Item>
            )}
          </Descriptions>
        </div>

        {/* 表单 */}
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="tag"
            label="标签"
            rules={[{ required: true, message: '请选择标签' }]}
          >
            <Select placeholder="选择 Bad Case 标签">
              {(Object.entries(BAD_CASE_TAG_LABELS) as [BadCaseTag, string][]).map(
                ([key, label]) => (
                  <Select.Option key={key} value={key}>
                    <Tag color={BAD_CASE_TAG_COLORS[key]}>{label}</Tag>
                    {({
                      hallucination: 'Agent 产生不存在/虚构的内容',
                      error: 'Agent 输出包含事实错误',
                      omission: 'Agent 遗漏了关键信息',
                      timeout: 'Agent 响应超时',
                      other: '其他类型问题',
                    })[key]}
                  </Select.Option>
                ),
              )}
            </Select>
          </Form.Item>

          <Form.Item name="description" label="问题描述">
            <TextArea placeholder="描述这个 Bad Case 的具体问题" rows={3} maxLength={2000} showCount />
          </Form.Item>

          <Form.Item
            name="assignee_id"
            label="负责人 ID"
            help="输入负责处理此 Bad Case 的用户 ID（UUID）"
          >
            <Input placeholder="输入用户 UUID（选填）" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={onClose}>取消</Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                确认标记
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </div>
    </Modal>
  );
}