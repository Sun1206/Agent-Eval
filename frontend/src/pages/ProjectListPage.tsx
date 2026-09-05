/**
 * 项目列表页
 *
 * 顶部搜索栏 + 卡片网格(3列) + 新建项目 Modal + 空态引导
 */
import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Input,
  Modal,
  Form,
  Typography,
  message,
  Empty,
  Space,
  Row,
  Col,
  Popconfirm,
  Dropdown,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  ProjectOutlined,
  ClockCircleOutlined,
  EditOutlined,
  DeleteOutlined,
  MoreOutlined,
} from '@ant-design/icons';
import { listProjects, createProject, updateProject, deleteProject, ProjectInfo } from '@/services/project';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { Meta } = Card;

interface CreateFormValues {
  name: string;
  description?: string;
}

interface EditFormValues {
  name: string;
  description?: string;
}

export default function ProjectListPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<CreateFormValues>();

  // 编辑 Modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<ProjectInfo | null>(null);
  const [editSaving, setEditSaving] = useState(false);
  const [editForm] = Form.useForm<EditFormValues>();

  // 加载项目列表
  const fetchProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listProjects();
      setProjects(data);
    } catch {
      message.error('加载项目列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // 搜索过滤
  const filtered = useMemo(() => {
    if (!search.trim()) return projects;
    const keyword = search.toLowerCase();
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(keyword) ||
        (p.description ?? '').toLowerCase().includes(keyword),
    );
  }, [projects, search]);

  // 新建项目
  async function handleCreate(values: CreateFormValues) {
    setCreating(true);
    try {
      await createProject(values);
      message.success('项目创建成功');
      setModalOpen(false);
      form.resetFields();
      await fetchProjects();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '创建失败，请重试';
      message.error(msg);
    } finally {
      setCreating(false);
    }
  }

  // 点击卡片进入项目
  function enterProject(projectId: string) {
    navigate(`/projects/${projectId}`);
  }

  // 编辑项目
  function openEditModal(project: ProjectInfo, e?: React.MouseEvent) {
    e?.stopPropagation();
    setEditingProject(project);
    editForm.setFieldsValue({ name: project.name, description: project.description });
    setEditModalOpen(true);
  }

  async function handleEdit(values: EditFormValues) {
    if (!editingProject) return;
    setEditSaving(true);
    try {
      await updateProject(editingProject.id, values);
      message.success('项目更新成功');
      setEditModalOpen(false);
      editForm.resetFields();
      setEditingProject(null);
      await fetchProjects();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '更新失败';
      message.error(msg);
    } finally {
      setEditSaving(false);
    }
  }

  // 删除项目
  async function handleDelete(projectId: string, e?: React.MouseEvent) {
    e?.stopPropagation();
    try {
      await deleteProject(projectId);
      message.success('项目已删除');
      await fetchProjects();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as { message?: string })?.message ??
        '删除失败';
      message.error(msg);
    }
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px' }}>
      {/* 顶部 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <Title level={3} style={{ margin: 0 }}>
            我的项目
          </Title>
          <Text type="secondary">管理和查看您的 AI Agent 评测项目</Text>
        </div>
        <Space>
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索项目名称或描述"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            allowClear
            style={{ width: 260 }}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建项目
          </Button>
        </Space>
      </div>

      {/* 项目卡片网格 */}
      {loading ? (
        <Row gutter={[16, 16]}>
          {[1, 2, 3].map((i) => (
            <Col key={i} xs={24} sm={12} lg={8}>
              <Card loading style={{ height: 160 }} />
            </Col>
          ))}
        </Row>
      ) : filtered.length === 0 ? (
        <Empty
          style={{ marginTop: 80 }}
          description={
            <div>
              <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                {search ? '没有匹配的项目' : '暂无项目'}
              </Text>
              {!search && (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
                  创建第一个项目
                </Button>
              )}
            </div>
          }
        />
      ) : (
        <Row gutter={[16, 16]}>
          {filtered.map((project) => (
            <Col key={project.id} xs={24} sm={12} lg={8}>
              <Card
                hoverable
                onClick={() => enterProject(project.id)}
                style={{ height: 160 }}
                actions={[
                  <EditOutlined key="edit" onClick={(e) => openEditModal(project, e)} />,
                  <Popconfirm
                    key="delete"
                    title="确定删除此项目？"
                    description="删除后数据将无法恢复"
                    onConfirm={(e) => handleDelete(project.id, e as React.MouseEvent)}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <DeleteOutlined onClick={(e) => e.stopPropagation()} style={{ color: '#ff4d4f' }} />
                  </Popconfirm>,
                ]}
              >
                <Meta
                  avatar={
                    <ProjectOutlined
                      style={{ fontSize: 28, color: '#1677FF', marginTop: 4 }}
                    />
                  }
                  title={
                    <Text ellipsis style={{ maxWidth: 200 }}>
                      {project.name}
                    </Text>
                  }
                  description={
                    <div>
                      <Paragraph
                        ellipsis={{ rows: 2 }}
                        type="secondary"
                        style={{ marginBottom: 8, minHeight: 44 }}
                      >
                        {project.description || '暂无描述'}
                      </Paragraph>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        <ClockCircleOutlined style={{ marginRight: 4 }} />
                        {dayjs(project.created_at).format('YYYY-MM-DD HH:mm')}
                      </Text>
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* 新建项目 Modal */}
      <Modal
        title="新建项目"
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        destroyOnClose
        width={480}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[
              { required: true, message: '请输入项目名称' },
              { max: 100, message: '项目名称不超过 100 个字符' },
            ]}
          >
            <Input placeholder="输入项目名称" maxLength={100} />
          </Form.Item>

          <Form.Item
            name="description"
            label="项目描述"
            rules={[{ max: 2000, message: '项目描述不超过 2000 个字符' }]}
          >
            <Input.TextArea
              placeholder="输入项目描述（选填）"
              rows={3}
              maxLength={2000}
              showCount
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  setModalOpen(false);
                  form.resetFields();
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={creating}>
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑项目 Modal */}
      <Modal
        title="编辑项目"
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false);
          editForm.resetFields();
          setEditingProject(null);
        }}
        footer={null}
        destroyOnClose
        width={480}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleEdit}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[
              { required: true, message: '请输入项目名称' },
              { max: 100, message: '项目名称不超过 100 个字符' },
            ]}
          >
            <Input placeholder="输入项目名称" maxLength={100} />
          </Form.Item>

          <Form.Item
            name="description"
            label="项目描述"
            rules={[{ max: 2000, message: '项目描述不超过 2000 个字符' }]}
          >
            <Input.TextArea
              placeholder="输入项目描述（选填）"
              rows={3}
              maxLength={2000}
              showCount
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  setEditModalOpen(false);
                  editForm.resetFields();
                  setEditingProject(null);
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={editSaving}>
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}