# EMG手势识别系统 - 模型部署方案

## 目录
- [部署架构总览](#部署架构总览)
- [边缘部署（KunpengPro）](#边缘部署KunpengPro)
- [云端部署](#云端部署)
- [模型转换与优化](#模型转换与优化)
- [部署流程说明](#部署流程说明)
- [监控与运维](#监控与运维)

---

## 部署架构总览

### 1. 混合部署架构（推荐）

```
┌─────────────────────────────────────────────────┐
│              训练平台（云端）                    │
│    Spring Boot + Python Training Service       │
│                                                 │
│  训练完成 → 生成模型 → 版本管理                │
└────────────┬────────────────────────────────────┘
             │
             ├─────────────┬──────────────────┐
             │             │                  │
             ↓             ↓                  ↓
    ┌────────────┐  ┌─────────────┐  ┌──────────────┐
    │  边缘部署  │  │  云端备份   │  │  A/B测试    │
    │ (主推理)   │  │  (备用推理) │  │  (新模型)   │
    └────────────┘  └─────────────┘  └──────────────┘
         │
         ↓
    ┌─────────────────────┐
    │  KunpengPro + 模型     │
    │  - 本地推理        │
    │  - 低延迟(<10ms)   │
    │  - 离线可用        │
    └─────────────────────┘
```

### 2. 部署策略对比

| 维度 | 边缘部署（KunpengPro） | 云端部署 | 混合部署 |
|------|---------------------|---------|---------|
| **延迟** | ⭐⭐⭐⭐⭐ <5ms | ⭐⭐ 50-200ms | ⭐⭐⭐⭐ |
| **离线可用** | ✅ 完全支持 | ❌ 需要网络 | ✅ 边缘支持 |
| **资源消耗** | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 灵活 | ⭐⭐⭐⭐ |
| **模型更新** | ⭐⭐⭐ 需推送 | ⭐⭐⭐⭐⭐ 即时 | ⭐⭐⭐⭐ |
| **成本** | ⭐⭐⭐⭐ 一次性 | ⭐⭐ 持续费用 | ⭐⭐⭐ |
| **推荐场景** | 实时应用 | 集中管理 | 生产环境 |

---

## 边缘部署（KunpengPro）

### 1. 硬件要求

**最低配置：**
- CPU: ARM Cortex-A53 四核 1.5GHz
- RAM: 1GB
- 存储: 8GB（模型约2-5MB）

**推荐配置：**
- CPU: ARM Cortex-A55/A76
- RAM: 2GB+
- 存储: 16GB+
- 可选: NPU/GPU加速器

### 2. 软件环境

```bash
# KunpengPro上安装依赖
sudo apt-get update
sudo apt-get install python3 python3-pip

# 安装ONNX Runtime（ARM版本）
pip3 install onnxruntime

# 或安装TensorFlow Lite（更轻量）
pip3 install tflite-runtime

# 安装其他依赖
pip3 install numpy pyserial requests
```

### 3. 模型转换

#### 3.1 PyTorch → ONNX

```python
# convert_to_onnx.py
import torch
import onnx

# 加载训练好的模型
model = CNNLSTMModel(...)
checkpoint = torch.load('best_model.pth')
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

# 导出为ONNX
dummy_input = torch.randn(1, 8, 150)
torch.onnx.export(
    model,
    dummy_input,
    "model.onnx",
    export_params=True,
    opset_version=11,
    do_constant_folding=True,
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={
        'input': {0: 'batch_size'},
        'output': {0: 'batch_size'}
    }
)

# 验证ONNX模型
onnx_model = onnx.load("model.onnx")
onnx.checker.check_model(onnx_model)
print("✓ ONNX模型导出成功")
```

#### 3.2 ONNX → TensorFlow Lite（可选，进一步优化）

```python
# convert_to_tflite.py
import onnx
from onnx_tf.backend import prepare
import tensorflow as tf

# ONNX → TensorFlow
onnx_model = onnx.load("model.onnx")
tf_rep = prepare(onnx_model)
tf_rep.export_graph("model_tf")

# TensorFlow → TFLite
converter = tf.lite.TFLiteConverter.from_saved_model("model_tf")
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

with open("model.tflite", "wb") as f:
    f.write(tflite_model)

print("✓ TFLite模型转换成功")
```

### 4. KunpengPro推理引擎

创建：`/opt/emg/inference_engine.py`

```python
# -*- coding: utf-8 -*-
"""
inference_engine.py - KunpengPro边缘推理引擎
"""
import numpy as np
import onnxruntime as ort
from collections import deque
import time

class GestureInferenceEngine:
    """手势推理引擎"""
    
    def __init__(self, model_path, window_size=150):
        self.window_size = window_size
        self.buffer = deque(maxlen=window_size)
        
        # 加载ONNX模型
        self.session = ort.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name
        
        # 手势映射
        self.gesture_map = {
            0: 'fist',
            1: 'ok',
            2: 'pinch',
            3: 'relax',
            4: 'sidegrip',
            5: 'ye'
        }
        
        print(f"✓ 模型加载成功: {model_path}")
    
    def add_frame(self, emg_frame):
        """添加EMG帧（8通道）"""
        self.buffer.append(emg_frame)
    
    def is_ready(self):
        """缓冲区是否已满"""
        return len(self.buffer) == self.window_size
    
    def predict(self):
        """执行推理"""
        if not self.is_ready():
            return None, 0.0
        
        # 准备输入数据
        data = np.array(list(self.buffer))  # (150, 8)
        data = data.T  # (8, 150)
        data = data[np.newaxis, :, :]  # (1, 8, 150)
        data = data.astype(np.float32)
        
        # 归一化（如果训练时做了）
        data = (data - data.mean()) / (data.std() + 1e-8)
        
        # 推理
        start_time = time.time()
        output = self.session.run(None, {self.input_name: data})
        inference_time = (time.time() - start_time) * 1000
        
        # 解析结果
        logits = output[0][0]  # (6,)
        probs = self._softmax(logits)
        pred_class = np.argmax(probs)
        confidence = probs[pred_class]
        
        gesture = self.gesture_map.get(pred_class, 'unknown')
        
        return gesture, confidence
    
    def _softmax(self, x):
        exp_x = np.exp(x - np.max(x))
        return exp_x / exp_x.sum()


# 使用示例
if __name__ == '__main__':
    engine = GestureInferenceEngine('/opt/emg/models/model.onnx')
    
    # 模拟150帧数据
    for i in range(150):
        emg_frame = np.random.randint(0, 255, size=8)
        engine.add_frame(emg_frame)
    
    if engine.is_ready():
        gesture, confidence = engine.predict()
        print(f"手势: {gesture}, 置信度: {confidence:.2f}")
```

### 5. 集成到数据采集脚本

修改 `KunpengPro_emg_uploader.py`：

```python
from inference_engine import GestureInferenceEngine

# 初始化推理引擎
inference_engine = GestureInferenceEngine('/opt/emg/models/model.onnx')

# 在解析帧后添加推理逻辑
def process_frame(frame_data):
    emg = frame_data['emg'][0]  # 取第一行8通道
    
    # 添加到推理缓冲区
    inference_engine.add_frame(emg)
    
    # 执行推理
    if inference_engine.is_ready():
        gesture, confidence = inference_engine.predict()
        frame_data['gesture'] = gesture
        frame_data['confidence'] = float(confidence)
    else:
        frame_data['gesture'] = 'unknown'
        frame_data['confidence'] = 0.0
    
    # 上传到Spring Boot
    upload_frame(frame_data)
```

### 6. 模型自动更新

创建：`/opt/emg/model_updater.py`

```python
# -*- coding: utf-8 -*-
"""
model_updater.py - 模型自动更新服务
定期检查新版本并下载
"""
import requests
import os
import hashlib
import time

SERVER_URL = 'http://1.95.65.51:8080'
MODEL_DIR = '/opt/emg/models'
CHECK_INTERVAL = 300  # 5分钟检查一次

def get_active_model():
    """获取当前激活的模型版本"""
    resp = requests.get(f'{SERVER_URL}/api/model/active')
    if resp.status_code == 200:
        data = resp.json()
        if data['code'] == 200:
            return data['data']
    return None

def download_model(version):
    """下载模型"""
    url = f'{SERVER_URL}/api/model/download/{version}'
    model_path = os.path.join(MODEL_DIR, f'{version}.onnx')
    
    print(f"下载模型: {version}")
    resp = requests.get(url, stream=True)
    
    if resp.status_code == 200:
        with open(model_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✓ 模型下载成功: {model_path}")
        return model_path
    else:
        print(f"✗ 下载失败: {resp.status_code}")
        return None

def check_and_update():
    """检查并更新模型"""
    active_model = get_active_model()
    
    if not active_model:
        return
    
    version = active_model['version']
    model_path = os.path.join(MODEL_DIR, f'{version}.onnx')
    
    # 如果本地没有此版本，下载
    if not os.path.exists(model_path):
        download_model(version)
        
        # 创建软链接指向最新模型
        link_path = os.path.join(MODEL_DIR, 'model.onnx')
        if os.path.exists(link_path):
            os.remove(link_path)
        os.symlink(model_path, link_path)
        
        print(f"✓ 模型更新完成: {version}")
        
        # TODO: 通知推理引擎重新加载模型

if __name__ == '__main__':
    print("模型更新服务启动")
    
    while True:
        try:
            check_and_update()
        except Exception as e:
            print(f"更新失败: {e}")
        
        time.sleep(CHECK_INTERVAL)
```

---

## 云端部署

### 1. Docker容器化部署

创建 `Dockerfile`：

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir \\
    torch==1.12.0 \\
    onnxruntime==1.12.0 \\
    numpy \\
    flask \\
    gunicorn

# 复制模型和推理代码
COPY models/ /app/models/
COPY inference_server.py /app/

# 暴露端口
EXPOSE 8000

# 启动推理服务
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "inference_server:app"]
```

创建 `inference_server.py`：

```python
from flask import Flask, request, jsonify
from inference_engine import GestureInferenceEngine
import numpy as np

app = Flask(__name__)

# 加载模型
engine = GestureInferenceEngine('/app/models/model.onnx')

@app.route('/predict', methods=['POST'])
def predict():
    """推理接口"""
    data = request.json
    emg_window = np.array(data['emg_data'])  # (150, 8)
    
    # 填充推理引擎
    for frame in emg_window:
        engine.add_frame(frame)
    
    # 执行推理
    gesture, confidence = engine.predict()
    
    return jsonify({
        'gesture': gesture,
        'confidence': float(confidence)
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

构建和运行：

```bash
# 构建镜像
docker build -t emg-inference:latest .

# 运行容器
docker run -d \\
    --name emg-inference \\
    -p 8000:8000 \\
    -v /path/to/models:/app/models \\
    emg-inference:latest

# 测试
curl -X POST http://localhost:8000/predict \\
    -H "Content-Type: application/json" \\
    -d '{"emg_data": [[0,0,0,0,0,0,0,0], ...]}'
```

### 2. Kubernetes部署

创建 `deployment.yaml`：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: emg-inference-config
data:
  MODEL_PATH: "/app/models/model.onnx"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: emg-inference
  labels:
    app: emg-inference
spec:
  replicas: 3
  selector:
    matchLabels:
      app: emg-inference
  template:
    metadata:
      labels:
        app: emg-inference
    spec:
      containers:
      - name: inference
        image: emg-inference:latest
        ports:
        - containerPort: 8000
        env:
        - name: MODEL_PATH
          valueFrom:
            configMapKeyRef:
              name: emg-inference-config
              key: MODEL_PATH
        resources:
          requests:
            memory: "256Mi"
            cpu: "500m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: emg-inference-service
spec:
  selector:
    app: emg-inference
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

部署：

```bash
kubectl apply -f deployment.yaml
kubectl get pods -l app=emg-inference
kubectl get svc emg-inference-service
```

---

## 模型转换与优化

### 1. 模型量化（减小体积，提升速度）

```python
import torch
from torch.quantization import quantize_dynamic

# 加载模型
model = CNNLSTMModel(...)
model.load_state_dict(torch.load('best_model.pth')['model_state_dict'])
model.eval()

# 动态量化
quantized_model = quantize_dynamic(
    model,
    {torch.nn.Linear, torch.nn.LSTM},
    dtype=torch.qint8
)

# 保存量化模型
torch.save(quantized_model.state_dict(), 'quantized_model.pth')

# 体积对比
import os
print(f"原始模型: {os.path.getsize('best_model.pth') / 1024 / 1024:.2f} MB")
print(f"量化模型: {os.path.getsize('quantized_model.pth') / 1024 / 1024:.2f} MB")
```

### 2. 模型剪枝（减少参数）

```python
import torch.nn.utils.prune as prune

# 剪枝20%的权重
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Conv1d) or isinstance(module, torch.nn.Linear):
        prune.l1_unstructured(module, name='weight', amount=0.2)

# 永久移除剪枝的权重
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Conv1d) or isinstance(module, torch.nn.Linear):
        prune.remove(module, 'weight')

torch.save(model.state_dict(), 'pruned_model.pth')
```

---

## 部署流程说明

### 完整部署流程

```
1. 模型训练完成
   ↓
2. 在Spring Boot中创建模型版本记录
   ↓
3. 模型转换（PyTorch → ONNX）
   ↓
4. 模型优化（量化/剪枝，可选）
   ↓
5. 上传模型文件到存储（OSS/NFS）
   ↓
6. 选择部署目标
   ├─ KunpengPro边缘部署
   │  ├─ App发起部署请求
   │  ├─ Spring Boot推送模型信息
   │  ├─ KunpengPro下载模型文件
   │  ├─ 推理引擎热加载新模型
   │  └─ 验证推理结果
   │
   └─ 云端容器部署
      ├─ 构建Docker镜像
      ├─ 推送到镜像仓库
      ├─ Kubernetes滚动更新
      └─ 验证健康检查
   ↓
7. 激活模型版本
   ↓
8. 监控推理性能
```

### 部署脚本示例

```bash
#!/bin/bash
# deploy_model.sh

VERSION=$1
TARGET=$2  # KunpengPro / cloud

echo "部署模型: $VERSION 到 $TARGET"

# 1. 转换模型
python3 convert_to_onnx.py --input models/${VERSION}.pth --output models/${VERSION}.onnx

# 2. 验证模型
python3 validate_model.py --model models/${VERSION}.onnx

# 3. 根据目标部署
if [ "$TARGET" == "KunpengPro" ]; then
    # 上传到KunpengPro
    scp models/${VERSION}.onnx KunpengPro:/opt/emg/models/
    ssh KunpengPro "ln -sf /opt/emg/models/${VERSION}.onnx /opt/emg/models/model.onnx"
    ssh KunpengPro "systemctl restart emg-inference"
elif [ "$TARGET" == "cloud" ]; then
    # 构建Docker镜像
    docker build -t emg-inference:${VERSION} .
    docker push registry.example.com/emg-inference:${VERSION}
    
    # Kubernetes部署
    kubectl set image deployment/emg-inference inference=emg-inference:${VERSION}
    kubectl rollout status deployment/emg-inference
fi

echo "✓ 部署完成"
```

---

## 监控与运维

### 1. 推理性能监控

```python
# metrics.py
import time
from collections import deque

class InferenceMetrics:
    """推理指标监控"""
    
    def __init__(self, window_size=100):
        self.inference_times = deque(maxlen=window_size)
        self.gesture_counts = {}
        self.total_inferences = 0
    
    def record(self, gesture, inference_time):
        self.inference_times.append(inference_time)
        self.gesture_counts[gesture] = self.gesture_counts.get(gesture, 0) + 1
        self.total_inferences += 1
    
    def get_stats(self):
        if not self.inference_times:
            return {}
        
        times = list(self.inference_times)
        return {
            'avg_inference_time_ms': sum(times) / len(times),
            'max_inference_time_ms': max(times),
            'min_inference_time_ms': min(times),
            'total_inferences': self.total_inferences,
            'gesture_distribution': self.gesture_counts
        }
```

### 2. 健康检查

```python
@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    try:
        # 测试推理
        test_data = np.random.randn(1, 8, 150).astype(np.float32)
        start = time.time()
        engine.session.run(None, {engine.input_name: test_data})
        latency = (time.time() - start) * 1000
        
        return jsonify({
            'status': 'healthy',
            'latency_ms': latency,
            'model_loaded': True
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
```

### 3. 日志记录

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/var/log/emg-inference.log'),
        logging.StreamHandler()
    ]
)

log = logging.getLogger('inference')

# 记录推理日志
log.info(f"推理结果: gesture={gesture}, confidence={confidence:.2f}, " \\
         f"time={inference_time:.2f}ms")
```

### 4. 告警配置

```yaml
# Prometheus告警规则
groups:
- name: emg_inference
  rules:
  - alert: HighInferenceLatency
    expr: inference_latency_ms > 100
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "推理延迟过高"
      description: "推理延迟 {{ $value }}ms 超过阈值"
  
  - alert: LowAccuracy
    expr: inference_accuracy < 0.8
    for: 10m
    labels:
      severity: critical
    annotations:
      summary: "推理准确率下降"
      description: "准确率 {{ $value }} 低于80%"
```

---

## 总结

本部署方案提供了：

- ✅ **灵活的部署选项**：支持边缘、云端和混合部署
- ✅ **自动化流程**：模型转换、分发、更新全自动
- ✅ **高性能推理**：边缘部署延迟<10ms
- ✅ **可靠性保障**：健康检查、自动重试、故障转移
- ✅ **运维友好**：完善的监控、日志和告警

建议生产环境采用**混合部署**方案，主要在KunpengPro边缘推理，云端作为备份和新模型测试平台。

