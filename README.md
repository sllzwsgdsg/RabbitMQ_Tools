# RabbitMQ Web管理服务

基于Flask + RabbitMQ Management HTTP API实现的RabbitMQ Web管理工具，支持队列与连接的查询、清理等常用运维操作，接口RESTful，适合自动化运维和平台集成。

## 安装

建议使用Python 3.7+

```bash
pip install -r requirements.txt
```

## 启动

```bash
python tools.py
```

默认监听0.0.0.0:5000，可根据需要修改tools.py中的启动参数。

## 配置

编辑`tools.py`文件顶部的如下参数：

```python
RABBITMQ_API_HOST = 'your_rabbitmq_host'
RABBITMQ_API_PORT = 15672
RABBITMQ_API_USER = 'your_user'
RABBITMQ_API_PASS = 'your_pass'
RABBITMQ_VHOST    = '/'
```

## 接口说明

### 1. 查看所有队列
- **GET** `/queues`
- 返回所有队列的基本信息（名称、消息数、消费者数、状态等）

### 2. 查看并清空某队列未被消费的任务
- **GET** `/queue/<queue_name>`
- 返回队列状态、未消费消息数、部分消息内容，并自动清空该队列未被消费的任务

### 3. 查看指定worker IP的所有连接情况
- **GET** `/worker/connections/info?ip=xxx`
- 参数：`ip`（worker的IP地址）
- 返回该IP下所有连接的详细信息

### 4. 清理指定worker IP的所有连接（僵尸连接）
- **DELETE** `/worker/connections?ip=xxx`
- 参数：`ip`（worker的IP地址）
- 关闭该IP下所有连接，返回已关闭和失败的连接列表

## 示例

### 查看所有队列
```bash
curl http://localhost:5000/queues
```

### 查看并清空某队列未被消费的任务
```bash
curl http://localhost:5000/queue/my_queue
```

### 查询worker IP的所有连接
```bash
curl "http://localhost:5000/worker/connections/info?ip=192.168.1.100"
```

### 清理worker IP的所有连接
```bash
curl -X DELETE "http://localhost:5000/worker/connections?ip=192.168.1.100"
```

## 注意事项
- 需确保RabbitMQ已启用Management Plugin，且API端口可访问。
- 清理操作具有危险性，请谨慎使用。
- 建议仅在受信任的内网环境部署本服务。 