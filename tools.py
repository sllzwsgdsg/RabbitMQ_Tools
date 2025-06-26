# coding: utf-8
"""
RabbitMQ Web管理服务
----------------------
基于Flask + RabbitMQ Management HTTP API实现。

接口说明：
GET    /queues                        查看所有队列
GET    /queue/<queue_name>            查看同时清空某队列未被消费的任务
GET    /worker/connections/info?ip=xxx  查看指定worker IP的所有连接情况
DELETE /worker/connections?ip=xxx     清理指定worker IP的所有连接（僵尸连接）

配置：请在下方填写RabbitMQ管理API参数。
"""

from flask import Flask, jsonify, request
import requests
import base64
import os
from urllib.parse import quote
import logging

# 日志配置
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')

# RabbitMQ管理API参数（请根据实际情况填写）
RABBITMQ_API_HOST = '123.206.227.166'  # RabbitMQ管理API主机
RABBITMQ_API_PORT = 15672        # RabbitMQ管理API端口
RABBITMQ_API_USER = 'celery'      # 用户名
RABBITMQ_API_PASS = 'celery'      # 密码
RABBITMQ_VHOST    = '/'          # vhost

def get_api_url(path):
    """拼接RabbitMQ管理API完整URL"""
    return f"http://{RABBITMQ_API_HOST}:{RABBITMQ_API_PORT}/api{path}"


def get_auth():
    """返回HTTP Basic Auth元组"""
    return (RABBITMQ_API_USER, RABBITMQ_API_PASS)


def rabbitmq_api_get(path):
    url = get_api_url(path)
    try:
        resp = requests.get(url, auth=get_auth(), timeout=5)
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:
        return None, str(e)


def rabbitmq_api_delete(path):
    url = get_api_url(path)
    try:
        resp = requests.delete(url, auth=get_auth(), timeout=5)
        resp.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)


def rabbitmq_api_post(path, data=None):
    url = get_api_url(path)
    try:
        resp = requests.post(url, json=data, auth=get_auth(), timeout=5)
        resp.raise_for_status()
        return resp.json() if resp.content else {}, None
    except Exception as e:
        return None, str(e)

def get_vhost_enc():
    """返回URL编码后的vhost"""
    return quote(RABBITMQ_VHOST, safe='')

app = Flask(__name__)

@app.route('/queues', methods=['GET'])
def list_queues():
    """查看所有队列及其状态"""
    logging.info(f"[API] {request.method} {request.path} | args={dict(request.args)} | json={request.get_json(silent=True)}")
    vhost_enc = get_vhost_enc()
    data, err = rabbitmq_api_get(f"/queues/{vhost_enc}")
    if err:
        return jsonify({'success': False, 'error': err}), 500
    # 只返回部分关键信息
    queues = []
    if data:
        queues = [
            {
                'name': q['name'],
                'messages': q.get('messages', 0),
                'consumers': q.get('consumers', 0),
                'state': q.get('state', ''),
            } for q in data
        ]
    return jsonify({'success': True, 'queues': queues})

@app.route('/queue/<queue_name>', methods=['GET'])
def queue_detail(queue_name):
    """查看某队列未被消费的任务"""
    logging.info(f"[API] {request.method} {request.path} | args={dict(request.args)} | json={request.get_json(silent=True)}")
    vhost_enc = get_vhost_enc()
    # 获取队列信息
    data, err = rabbitmq_api_get(f"/queues/{vhost_enc}/{queue_name}")
    if err:
        return jsonify({'success': False, 'error': err}), 500
    if not data:
        result = {
            'name': queue_name,
            'messages': 0,
            'consumers': 0,
            'state': '',
        }
    else:
        result = {
            'name': data.get('name', queue_name),
            'messages': data.get('messages', 0),
            'consumers': data.get('consumers', 0),
            'state': data.get('state', ''),
        }
    # 尝试获取部分未被消费的消息（最多10条）
    get_body = {
        'count': 10,
        'ackmode': 'ack_requeue_false',
        'encoding': 'auto',
        'truncate': 256
    }
    msgs, msg_err = rabbitmq_api_post(f"/queues/{vhost_enc}/{queue_name}/get", get_body)
    if not msg_err and isinstance(msgs, list):
        result['peek_messages'] = [m.get('payload') for m in msgs]
    else:
        result['peek_messages'] = []
    return jsonify({'success': True, 'queue': result})


@app.route('/worker/connections', methods=['DELETE'])
def close_worker_connections():
    """清理指定worker IP的所有连接，参数ip=xxx"""
    logging.info(f"[API] {request.method} {request.path} | args={dict(request.args)} | json={request.get_json(silent=True)}")
    ip = request.args.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'Missing required parameter: ip'}), 400
    closed = []
    failed = []
    # 获取所有连接
    connections, err = rabbitmq_api_get('/connections')
    if err:
        return jsonify({'success': False, 'error': err}), 500
    for conn in connections or []:
        if conn.get('peer_host') == ip:
            conn_name = conn.get('name')
            if not conn_name:
                continue
            ok, del_err = rabbitmq_api_delete(f"/connections/{conn_name}")
            if ok:
                closed.append(conn_name)
            else:
                failed.append({'conn': conn_name, 'error': del_err})
    return jsonify({'success': True, 'closed': closed, 'failed': failed})

@app.route('/worker/connections/info', methods=['GET'])
def worker_connections_info():
    """查询指定worker IP的所有连接情况，参数ip=xxx"""
    logging.info(f"[API] {request.method} {request.path} | args={dict(request.args)} | json={request.get_json(silent=True)}")
    ip = request.args.get('ip')
    if not ip:
        return jsonify({'success': False, 'error': 'Missing required parameter: ip'}), 400
    result = []
    # 获取所有连接
    connections, err = rabbitmq_api_get('/connections')
    if err:
        return jsonify({'success': False, 'error': err}), 500
    for conn in connections or []:
        if conn.get('peer_host') == ip:
            info = {
                'connection_name': conn.get('name'),
                'client_properties': conn.get('client_properties', {}),
                'peer_host': conn.get('peer_host'),
                'peer_port': conn.get('peer_port'),
                'user': conn.get('user'),
                'state': conn.get('state'),
                'channels': conn.get('channels', []),
            }
            result.append(info)
    return jsonify({'success': True, 'connections': result})

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
