/**
 * 数据集详情页
 *
 * 基本信息卡片 + 操作栏（添加条目 / 导入 / 导出） + 条目表格（分页）
 * 支持：添加条目 Modal / 编辑条目 Modal / 导入文件 Modal（上传 + 预览 + 确认）
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Upload,
  Descriptions,
  Tag,
  Typography,
  message,
  Space,
  Popconfirm,
  Radio,
} from 'antd';
import {
  PlusOutlined,
  ImportOutlined,
  ExportOutlined,
  InboxOutlined,
  ReloadOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  getDataset,
  listDatasetItems,
  addDatasetItem,
  updateDatasetItem,
  deleteDatasetItem,
  batchDeleteDatasetItems,
  importDatasetFile,
  getExportUrl,
  DatasetInfo,
  DatasetItem,
} from '@/services/dataset';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { Dragger } = Upload;

// ---------- 条目表单 ----------

interface ItemFormValues {
  input: string;
  expected_output?: string;
  context?: string;
  sort_order?: number;
}

export default function DatasetDetailPage() {
  const { projectId, datasetId } = useParams<{ projectId: string; datasetId: string }>();

  // 数据集信息
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);

  // 条目表格
  const [items, setItems] = useState<DatasetItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  // 添加/编辑 Modal
  const [itemModalOpen, setItemModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<DatasetItem | null>(null);
  const [itemSaving, setItemSaving] = useState(false);
  const [itemForm] = Form.useForm<ItemFormValues>();

  // 导入 Modal
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);

  // 导出
  const [exportFormat, setExportFormat] = useState<'json' | 'csv'>('json');

  // 批量选择
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchDeleting, setBatchDeleting] = useState(false);

  // ---------- 加载 ----------

  const fetchDataset = useCallback(async () => {
    if (!projectId || !datasetId) return;
    try {
      const data = await getDataset(projectId, datasetId);
      setDataset(data);
    } catch {
      message.error('加载数据集信息失败');
    }
  }, [projectId, datasetId]);

  const fetchItems = useCallback(async () => {
    if (!projectId || !datasetId) return;
    setLoading(true);
    try {
      const res = await listDatasetItems(projectId, datasetId, page, pageSize);
      setItems(res.items);
      setTotal(res.total);
    } catch {
      message.error('加载条目失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, datasetId, page, pageSize]);

  useEffect(() => {
    fetchDataset();
    fetchItems();
  }, [fetchDataset, fetchItems]);

  // ---------- 添加 / 编辑条目 ----------

  function openAddItem() {
    setEditingItem(null);
    itemForm.resetFields();
    itemForm.setFieldsValue({ sort_order: items.length + 1 });
    setItemModalOpen(true);
  }

  function openEditItem(item: DatasetItem) {
    setEditingItem(item);
    itemForm.setFieldsValue({
      input: item.input,
      expected_output: item.expected_output,
      context: item.context,
      sort_order: item.sort_order,
    });
    setItemModalOpen(true);
  }

  async function handleItemSubmit(values: ItemFormValues) {
    if (!projectId || !datasetId) return;
    setItemSaving(true);
    try {
      if (editingItem) {
        await updateDatasetItem(projectId, datasetId, editingItem.id, values);
        message.success('条目更新成功');
      } else {
        await addDatasetItem(projectId, datasetId, {
          ...values,
          sort_order: values.sort_order ?? 0,
        });
        message.success('条目添加成功');
      }
      setItemModalOpen(false);
      itemForm.resetFields();
      await fetchItems();
      await fetchDataset(); // 刷新 item_count
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '操作失败');
    } finally {
      setItemSaving(false);
    }
  }

  // ---------- 删除条目 ----------

  async function handleDeleteItem(itemId: string) {
    if (!projectId || !datasetId) return;
    try {
      await deleteDatasetItem(projectId, datasetId, itemId);
      message.success('条目已删除');
      await fetchItems();
      await fetchDataset();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '删除失败');
    }
  }

  // ---------- 批量删除 ----------

  async function handleBatchDelete() {
    if (!projectId || !datasetId || selectedRowKeys.length === 0) return;
    setBatchDeleting(true);
    try {
      const result = await batchDeleteDatasetItems(
        projectId,
        datasetId,
        selectedRowKeys as string[],
      );
      message.success(`已删除 ${result.deleted} 条条目`);
      setSelectedRowKeys([]);
      await fetchItems();
      await fetchDataset();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '批量删除失败');
    } finally {
      setBatchDeleting(false);
    }
  }

  // ---------- 导入 ----------

  function handleFileSelect(file: File) {
    const name = file.name.toLowerCase();
    if (!name.endsWith('.json') && !name.endsWith('.csv')) {
      message.warning('仅支持 .json 和 .csv 文件');
      return false;
    }
    setImportFile(file);
    return false; // 阻止 antd Upload 自动上传
  }

  async function handleImport() {
    if (!importFile || !projectId || !datasetId) return;
    setImporting(true);
    try {
      const result = await importDatasetFile(projectId, datasetId, importFile);
      message.success(
        `导入完成: 成功 ${result.imported} 条` +
          (result.skipped > 0 ? `, 跳过 ${result.skipped} 条` : ''),
      );
      if (result.errors.length > 0) {
        message.warning(`导入警告: ${result.errors.slice(0, 3).join('; ')}`);
      }
      setImportModalOpen(false);
      setImportFile(null);
      await fetchItems();
      await fetchDataset();
    } catch (err: unknown) {
      message.error((err as { message?: string })?.message ?? '导入失败');
    } finally {
      setImporting(false);
    }
  }

  // ---------- 导出 ----------

  function handleExport() {
    if (!projectId || !datasetId) return;
    const url = getExportUrl(projectId, datasetId, exportFormat);
    const token = localStorage.getItem('agentscope_token');
    // 带 token 下载文件
    if (token) {
      const sep = url.includes('?') ? '&' : '?';
      fetch(`${url}${sep}_token=${encodeURIComponent(token)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => res.blob())
        .then((blob) => {
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = `dataset_${datasetId}.${exportFormat}`;
          a.click();
          URL.revokeObjectURL(a.href);
        })
        .catch(() => message.error('导出失败'));
    }
  }

  // ---------- 表格列 ----------

  const columns: ColumnsType<DatasetItem> = [
    {
      title: '#',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 50,
      align: 'center',
    },
    {
      title: '输入(input)',
      dataIndex: 'input',
      key: 'input',
      ellipsis: true,
      width: 300,
    },
    {
      title: '期望输出',
      dataIndex: 'expected_output',
      key: 'expected_output',
      ellipsis: true,
      width: 250,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: '上下文',
      dataIndex: 'context',
      key: 'context',
      ellipsis: true,
      width: 200,
      render: (v: string | undefined) => v || '-',
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags: string[]) =>
        tags?.length ? tags.map((t) => <Tag key={t}>{t}</Tag>) : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_: unknown, record: DatasetItem) => (
        <Space size="small">
          <a onClick={() => openEditItem(record)}>编辑</a>
          <Popconfirm title="确定删除此条目？" onConfirm={() => handleDeleteItem(record.id)}>
            <a style={{ color: '#ff4d4f' }}>删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* 基本信息卡片 */}
      <Card style={{ marginBottom: 16 }}>
        <Descriptions title="数据集信息" column={3} size="small">
          <Descriptions.Item label="名称">{dataset?.name ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="描述">{dataset?.description || '-'}</Descriptions.Item>
          <Descriptions.Item label="条目总数">{dataset?.item_count ?? 0}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {dataset ? dayjs(dataset.created_at).format('YYYY-MM-DD HH:mm') : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="标签">
            {dataset?.tags?.length
              ? dataset.tags.map((t) => <Tag key={t}>{t}</Tag>)
              : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 操作栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Title level={5} style={{ margin: 0 }}>条目列表（共 {total} 条）</Title>
          {selectedRowKeys.length > 0 && (
            <Popconfirm
              title={`确定删除选中的 ${selectedRowKeys.length} 条条目？`}
              description="删除后数据将无法恢复"
              onConfirm={handleBatchDelete}
            >
              <Button
                danger
                icon={<DeleteOutlined />}
                loading={batchDeleting}
              >
                批量删除（{selectedRowKeys.length}）
              </Button>
            </Popconfirm>
          )}
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchItems}>刷新</Button>
          <Button icon={<PlusOutlined />} type="primary" onClick={openAddItem}>
            添加条目
          </Button>
          <Button icon={<ImportOutlined />} onClick={() => setImportModalOpen(true)}>
            导入
          </Button>
          <Space.Compact>
            <Button icon={<ExportOutlined />} onClick={handleExport}>
              导出
            </Button>
            <Radio.Group
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value)}
              optionType="button"
              size="small"
              style={{ marginLeft: 8 }}
            >
              <Radio.Button value="json">JSON</Radio.Button>
              <Radio.Button value="csv">CSV</Radio.Button>
            </Radio.Group>
          </Space.Compact>
        </Space>
      </div>

      {/* 条目表格 */}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        scroll={{ x: 1200 }}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />

      {/* 添加/编辑条目 Modal */}
      <Modal
        title={editingItem ? '编辑条目' : '添加条目'}
        open={itemModalOpen}
        onCancel={() => { setItemModalOpen(false); itemForm.resetFields(); }}
        footer={null}
        destroyOnClose
        width={640}
      >
        <Form
          form={itemForm}
          layout="vertical"
          onFinish={handleItemSubmit}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="input"
            label="输入（用户问题）"
            rules={[{ required: true, message: '请输入 input' }]}
          >
            <Input.TextArea placeholder="输入给 Agent 的用户问题" rows={3} />
          </Form.Item>
          <Form.Item name="expected_output" label="期望输出（参考答案）">
            <Input.TextArea placeholder="期望的参考答案（选填）" rows={3} />
          </Form.Item>
          <Form.Item name="context" label="上下文">
            <Input.TextArea placeholder="额外上下文信息（选填）" rows={2} />
          </Form.Item>
          <Form.Item name="sort_order" label="排序序号">
            <Input type="number" placeholder="排序序号，默认为条目数量" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => { setItemModalOpen(false); itemForm.resetFields(); }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={itemSaving}>
                {editingItem ? '保存' : '添加'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 导入 Modal */}
      <Modal
        title="导入数据集"
        open={importModalOpen}
        onCancel={() => { setImportModalOpen(false); setImportFile(null); }}
        footer={null}
        width={520}
        destroyOnClose
      >
        <div style={{ marginTop: 16 }}>
          <Dragger
            accept=".json,.csv"
            maxCount={1}
            beforeUpload={handleFileSelect}
            onRemove={() => setImportFile(null)}
            fileList={importFile ? [{ uid: '-1', name: importFile.name, status: 'done' } as UploadFile] : []}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">支持 .json 和 .csv 格式</p>
          </Dragger>

          {importFile && (
            <div style={{ marginTop: 16, textAlign: 'right' }}>
              <Space>
                <Button onClick={() => { setImportModalOpen(false); setImportFile(null); }}>
                  取消
                </Button>
                <Button type="primary" onClick={handleImport} loading={importing}>
                  确认导入
                </Button>
              </Space>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}