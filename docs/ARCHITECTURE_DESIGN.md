# EMG手势识别系统架构设计文档

## 1. 系统概述

### 1.1 核心需求
- **数据采集控制**：OrangePi采集的EMG数据默认不保存到MySQL，由App控制保存
- **数据标注**：保存的数据需要通过App进行手势标注
- **模型训练**：App可以主动触发使用MySQL中的标注数据训练模型
- **模型部署**：训练完成的模型可部署到OrangePi或云端进行实时推理

### 1.2 技术栈
- **硬件层**：OrangePi + EMG臂带
- **后端**：Spring Boot + MySQL（华为云RDS）
- **前端**：HarmonyOS App（ArkTS）
- **训练**：Python + PyTorch/MindSpore
- **部署**：Docker + 模型服务

---

## 2. 整体架构图

```
┌─────────────────┐
│  EMG 臂带       │
└────────┬────────┘
         │ 串口
         ↓
┌─────────────────────────────────────────────────────────┐
│                    OrangePi                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │  orangepi_emg_uploader.py                        │  │
│  │  - 采集EMG数据                                    │  │
│  │  - 实时推送到Spring Boot（WebSocket）            │  │
│  │  - 数据不直接保存到MySQL                         │  │
│  │  - 可选：加载模型进行本地推理                    │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ WebSocket/HTTP
                         ↓
┌─────────────────────────────────────────────────────────┐
│              Spring Boot 后端（华为云ECS）               │
│  ┌───────────────────────────────────────────────────┐ │
│  │  📡 实时数据流服务                                 │ │
│  │  - WebSocket Hub（接收OrangePi，广播给App）       │ │
│  │  - 数据缓存（Redis）                               │ │
│  │  - 默认不保存到MySQL                              │ │
│  └───────────────────────────────────────────────────┘ │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │  📝 数据标注服务                                   │ │
│  │  - App发起"保存数据"请求                          │ │
│  │  - 从缓存中提取指定时间段的数据                   │ │
│  │  - 标注手势类型                                   │ │
│  │  - 保存到 emg_labeled_data 表                    │ │
│  └───────────────────────────────────────────────────┘ │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │  🧠 训练任务服务                                   │ │
│  │  - App发起训练请求                                │ │
│  │  - 创建训练任务（异步）                           │ │
│  │  - 从MySQL导出标注数据                            │ │
│  │  - 调用Python训练脚本                             │ │
│  │  - 保存训练好的模型                               │ │
│  │  - 通知App训练完成                                │ │
│  └───────────────────────────────────────────────────┘ │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │  📦 模型管理服务                                   │ │
│  │  - 模型版本管理                                   │ │
│  │  - 模型下载/部署                                  │ │
│  │  - 模型性能指标查询                               │ │
│  └───────────────────────────────────────────────────┘ │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │  🗄️ MySQL (RDS)                                    │ │
│  │  - emg_labeled_data（标注数据）                   │ │
│  │  - training_task（训练任务）                      │ │
│  │  - model_version（模型版本）                      │ │
│  └───────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │ WebSocket/REST API
                         ↓
┌─────────────────────────────────────────────────────────┐
│              HarmonyOS App                               │
│  ┌───────────────────────────────────────────────────┐ │
│  │  📊 实时监控页面                                   │ │
│  │  - 接收实时EMG数据                                │ │
│  │  - 波形可视化                                     │ │
│  │  - 手势识别结果展示                               │ │
│  └───────────────────────────────────────────────────┘ │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │  ✏️ 数据标注页面                                   │ │
│  │  - 选择时间段                                     │ │
│  │  - 预览数据                                       │ │
│  │  - 标注手势类型（fist, ok, pinch, relax等）       │ │
│  │  - 提交保存                                       │ │
│  └───────────────────────────────────────────────────┘ │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │  🎓 模型训练页面                                   │ │
│  │  - 查看已标注数据统计                             │ │
│  │  - 配置训练参数（epoch、batch size等）            │ │
│  │  - 发起训练任务                                   │ │
│  │  - 查看训练进度和日志                             │ │
│  │  - 查看训练结果（准确率、损失曲线）               │ │
│  └───────────────────────────────────────────────────┘ │
│                                                          │
│  ┌───────────────────────────────────────────────────┐ │
│  │  📦 模型管理页面                                   │ │
│  │  - 查看所有模型版本                               │ │
│  │  - 部署模型到OrangePi                             │ │
│  │  - 切换使用的模型版本                             │ │
│  │  - 查看模型性能指标                               │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 数据库设计

### 3.1 标注数据表 (emg_labeled_data)

```sql
CREATE TABLE emg_labeled_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    device_id VARCHAR(50) NOT NULL,
    
    -- 时间信息
    capture_time DATETIME NOT NULL COMMENT '采集时间',
    device_ts BIGINT COMMENT '设备时间戳',
    
    -- EMG数据（JSON存储）
    emg_data JSON NOT NULL COMMENT 'EMG原始数据 10x8',
    acc_data JSON COMMENT '加速度数据 [x,y,z]',
    gyro_data JSON COMMENT '陀螺仪数据 [x,y,z]',
    angle_data JSON COMMENT '角度数据 [pitch,roll,yaw]',
    
    -- 标注信息
    gesture_label VARCHAR(50) NOT NULL COMMENT '手势标签',
    annotator VARCHAR(100) COMMENT '标注人',
    annotation_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '标注时间',
    
    -- 训练相关
    is_used_for_training BOOLEAN DEFAULT FALSE COMMENT '是否已用于训练',
    split_type VARCHAR(20) COMMENT 'train/val/test',
    
    -- 数据质量
    quality_score FLOAT COMMENT '数据质量分数',
    is_valid BOOLEAN DEFAULT TRUE COMMENT '是否有效',
    
    INDEX idx_gesture (gesture_label),
    INDEX idx_device (device_id),
    INDEX idx_time (capture_time),
    INDEX idx_training (is_used_for_training, split_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3.2 训练任务表 (training_task)

```sql
CREATE TABLE training_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_name VARCHAR(100) NOT NULL,
    task_status VARCHAR(20) NOT NULL COMMENT 'pending/running/completed/failed',
    
    -- 训练参数
    config JSON COMMENT '训练配置参数',
    data_filter JSON COMMENT '数据筛选条件',
    
    -- 数据集统计
    total_samples INT COMMENT '总样本数',
    train_samples INT,
    val_samples INT,
    test_samples INT,
    gesture_distribution JSON COMMENT '手势分布统计',
    
    -- 训练结果
    model_path VARCHAR(500) COMMENT '模型文件路径',
    train_accuracy FLOAT,
    val_accuracy FLOAT,
    test_accuracy FLOAT,
    train_loss FLOAT,
    val_loss FLOAT,
    metrics JSON COMMENT '详细指标',
    
    -- 时间信息
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    start_time DATETIME,
    end_time DATETIME,
    duration_seconds INT,
    
    -- 日志
    log_file VARCHAR(500) COMMENT '训练日志文件路径',
    error_message TEXT,
    
    created_by VARCHAR(100),
    
    INDEX idx_status (task_status),
    INDEX idx_time (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3.3 模型版本表 (model_version)

```sql
CREATE TABLE model_version (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    version VARCHAR(50) NOT NULL UNIQUE,
    model_name VARCHAR(100) NOT NULL,
    
    -- 模型信息
    model_path VARCHAR(500) NOT NULL COMMENT '模型文件路径',
    model_format VARCHAR(20) COMMENT 'pytorch/mindspore/onnx/tflite',
    model_size_mb FLOAT,
    
    -- 训练信息
    training_task_id BIGINT,
    trained_samples INT COMMENT '训练样本数',
    gesture_classes JSON COMMENT '支持的手势类别',
    
    -- 性能指标
    accuracy FLOAT,
    precision_score FLOAT,
    recall_score FLOAT,
    f1_score FLOAT,
    inference_time_ms FLOAT COMMENT '推理时间（毫秒）',
    
    -- 部署状态
    is_active BOOLEAN DEFAULT FALSE COMMENT '是否为当前激活版本',
    deployed_to VARCHAR(500) COMMENT '部署位置',
    deploy_time DATETIME,
    
    -- 元数据
    description TEXT,
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    FOREIGN KEY (training_task_id) REFERENCES training_task(id),
    INDEX idx_version (version),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 4. REST API 设计

### 4.1 数据标注相关 API

#### 4.1.1 获取缓存数据（用于预览）
```http
GET /api/annotation/cache-data
Query Parameters:
  - start_time: 开始时间（ISO格式）
  - end_time: 结束时间
  - device_id: 设备ID
Response:
{
  "code": 200,
  "data": {
    "frames": [...],  // EMG数据帧列表
    "count": 150
  }
}
```

#### 4.1.2 保存标注数据
```http
POST /api/annotation/save
Request Body:
{
  "device_id": "orangepi_01",
  "start_time": "2026-03-10T10:00:00",
  "end_time": "2026-03-10T10:00:05",
  "gesture_label": "fist",
  "annotator": "user01"
}
Response:
{
  "code": 200,
  "message": "已保存150帧数据",
  "data": {
    "saved_count": 150,
    "annotation_id": 12345
  }
}
```

#### 4.1.3 查询标注数据统计
```http
GET /api/annotation/statistics
Response:
{
  "code": 200,
  "data": {
    "total_samples": 5000,
    "gesture_distribution": {
      "fist": 1200,
      "ok": 1000,
      "pinch": 800,
      "relax": 2000
    },
    "annotators": ["user01", "user02"],
    "date_range": {
      "start": "2026-03-01",
      "end": "2026-03-10"
    }
  }
}
```

### 4.2 训练任务相关 API

#### 4.2.1 创建训练任务
```http
POST /api/training/create
Request Body:
{
  "task_name": "训练任务_20260310",
  "config": {
    "epochs": 50,
    "batch_size": 32,
    "learning_rate": 0.001,
    "window_size": 150,
    "model_type": "cnn_lstm"
  },
  "data_filter": {
    "gestures": ["fist", "ok", "pinch", "relax"],
    "min_quality_score": 0.8,
    "date_from": "2026-03-01",
    "date_to": "2026-03-10"
  }
}
Response:
{
  "code": 200,
  "data": {
    "task_id": 101,
    "estimated_time_minutes": 30
  }
}
```

#### 4.2.2 查询训练任务状态
```http
GET /api/training/task/{task_id}
Response:
{
  "code": 200,
  "data": {
    "task_id": 101,
    "status": "running",
    "progress": 45.5,
    "current_epoch": 23,
    "total_epochs": 50,
    "current_loss": 0.234,
    "current_accuracy": 0.892,
    "elapsed_seconds": 850,
    "estimated_remaining_seconds": 1020
  }
}
```

#### 4.2.3 获取训练日志
```http
GET /api/training/task/{task_id}/logs
Response:
{
  "code": 200,
  "data": {
    "logs": [
      "[10:00:01] 加载数据集...",
      "[10:00:05] 数据集加载完成，共5000个样本",
      "[10:00:10] Epoch 1/50 - Loss: 1.234, Acc: 0.456",
      ...
    ]
  }
}
```

#### 4.2.4 获取训练结果
```http
GET /api/training/task/{task_id}/result
Response:
{
  "code": 200,
  "data": {
    "task_id": 101,
    "status": "completed",
    "model_version": "v1.0.5",
    "accuracy": 0.952,
    "metrics": {
      "precision": 0.948,
      "recall": 0.950,
      "f1_score": 0.949
    },
    "confusion_matrix": [[...], [...], ...],
    "training_curve": {
      "epochs": [1, 2, 3, ...],
      "train_loss": [1.2, 0.8, 0.6, ...],
      "val_loss": [1.3, 0.9, 0.7, ...],
      "train_acc": [0.5, 0.7, 0.8, ...],
      "val_acc": [0.48, 0.68, 0.79, ...]
    }
  }
}
```

### 4.3 模型管理相关 API

#### 4.3.1 获取所有模型版本
```http
GET /api/model/versions
Response:
{
  "code": 200,
  "data": [
    {
      "version": "v1.0.5",
      "model_name": "NeuroGrip_CNN_LSTM",
      "accuracy": 0.952,
      "is_active": true,
      "created_time": "2026-03-10T12:00:00",
      "model_size_mb": 2.5
    },
    ...
  ]
}
```

#### 4.3.2 部署模型
```http
POST /api/model/deploy
Request Body:
{
  "version": "v1.0.5",
  "target": "orangepi",  // orangepi/cloud
  "device_id": "orangepi_01"
}
Response:
{
  "code": 200,
  "message": "模型部署成功"
}
```

#### 4.3.3 下载模型文件
```http
GET /api/model/download/{version}
Response: 模型文件（二进制流）
```

---

## 5. WebSocket 协议设计

### 5.1 OrangePi → Spring Boot

#### 连接端点
```
ws://backend:8080/ws/emg
```

#### 消息格式
```json
{
  "type": "emg_data",
  "device_id": "orangepi_01",
  "device_ts": 1234567890,
  "data": {
    "emg": [[ch1_1, ch2_1, ...], ...],  // 10x8
    "acc": [x, y, z],
    "gyro": [x, y, z],
    "angle": [pitch, roll, yaw],
    "battery": 85
  }
}
```

### 5.2 App ← Spring Boot

#### 连接端点
```
ws://backend:8080/ws/app
```

#### 消息类型

**1. 实时EMG数据**
```json
{
  "type": "emg_data",
  "device_id": "orangepi_01",
  "timestamp": "2026-03-10T10:00:00",
  "data": { ... }
}
```

**2. 训练进度更新**
```json
{
  "type": "training_progress",
  "task_id": 101,
  "progress": 45.5,
  "current_epoch": 23,
  "current_loss": 0.234,
  "current_accuracy": 0.892
}
```

**3. 训练完成通知**
```json
{
  "type": "training_completed",
  "task_id": 101,
  "model_version": "v1.0.5",
  "accuracy": 0.952
}
```

**4. 模型部署通知**
```json
{
  "type": "model_deployed",
  "version": "v1.0.5",
  "target": "orangepi_01",
  "status": "success"
}
```

---

## 6. 训练流程设计

### 6.1 训练流程图

```
┌─────────────────────────────────────────────────────┐
│  1. App 发起训练请求                                 │
│     - 选择训练参数                                   │
│     - 选择数据筛选条件                               │
└────────────────┬────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────┐
│  2. Spring Boot 创建训练任务                         │
│     - 保存任务到数据库                               │
│     - 状态：pending                                  │
│     - 返回 task_id 给 App                           │
└────────────────┬────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────┐
│  3. 异步执行训练任务（后台线程/容器）                │
│     - 从MySQL导出标注数据到CSV                      │
│     - 数据预处理（滑动窗口、归一化）                │
│     - 数据集分割（train/val/test）                  │
│     - 状态更新：running                             │
└────────────────┬────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────┐
│  4. 模型训练                                         │
│     - 加载 CNN-LSTM 模型                            │
│     - 训练循环（每个epoch更新进度）                 │
│     - 记录训练指标（loss、accuracy）                │
│     - 保存最佳模型checkpoint                        │
└────────────────┬────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────┐
│  5. 模型评估                                         │
│     - 在测试集上评估                                 │
│     - 计算指标（accuracy, precision, recall, F1）   │
│     - 生成混淆矩阵                                   │
│     - 生成训练曲线图                                 │
└────────────────┬────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────┐
│  6. 保存结果                                         │
│     - 更新训练任务状态：completed                    │
│     - 保存模型文件                                   │
│     - 创建模型版本记录                               │
│     - 通过WebSocket通知App                          │
└─────────────────────────────────────────────────────┘
```

### 6.2 训练脚本集成

在Spring Boot中通过`ProcessBuilder`调用Python训练脚本：

```java
ProcessBuilder pb = new ProcessBuilder(
    "python", "/path/to/training_script.py",
    "--config", configPath,
    "--data", dataPath,
    "--output", outputPath,
    "--task-id", String.valueOf(taskId)
);
pb.directory(new File("/path/to/training/"));
pb.redirectErrorStream(true);
Process process = pb.start();
// 读取输出，更新进度
```

---

## 7. 模型部署方案

### 7.1 部署架构

```
┌────────────────────────────────────────────────┐
│  模型训练平台（Spring Boot + Python）           │
│  - 训练完成后生成模型文件                       │
│  - 模型格式：PyTorch (.pth) / ONNX / TFLite   │
└──────────────────┬─────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ↓                     ↓
┌───────────────┐    ┌────────────────────┐
│ OrangePi部署  │    │  云端部署          │
│ (边缘推理)    │    │  (中心推理)        │
└───────────────┘    └────────────────────┘
```

### 7.2 OrangePi 边缘部署（推荐）

**优点**：
- 低延迟（本地推理，无网络往返）
- 离线可用
- 降低云端服务器负载

**实现方案**：

1. **模型转换**
   ```python
   # PyTorch → ONNX
   torch.onnx.export(model, dummy_input, "model.onnx")
   
   # ONNX → TensorRT (for GPU)
   # ONNX → NCNN (for ARM CPU)
   ```

2. **OrangePi推理脚本**
   ```python
   # orangepi_emg_uploader.py 增加推理模块
   import onnxruntime as ort
   
   class GestureInferenceEngine:
       def __init__(self, model_path):
           self.session = ort.InferenceSession(model_path)
       
       def predict(self, emg_window):
           input_data = preprocess(emg_window)
           output = self.session.run(None, {
               'input': input_data
           })
           return postprocess(output)
   ```

3. **模型自动更新**
   - OrangePi定期检查新模型版本
   - 从Spring Boot下载最新模型
   - 热加载新模型

### 7.3 云端推理部署（备选）

**适用场景**：
- OrangePi性能不足
- 需要集中管理推理资源
- 需要A/B测试不同模型

**实现方案**：

1. **模型服务容器化**
   ```dockerfile
   FROM python:3.9
   RUN pip install torch onnxruntime flask
   COPY model.onnx /app/
   COPY inference_server.py /app/
   CMD ["python", "/app/inference_server.py"]
   ```

2. **REST API推理服务**
   ```python
   @app.route('/predict', methods=['POST'])
   def predict():
       emg_data = request.json['emg_data']
       result = model.predict(emg_data)
       return jsonify(result)
   ```

3. **OrangePi调用云端推理**
   ```python
   response = requests.post(
       'http://backend:8080/api/inference/predict',
       json={'emg_data': emg_window}
   )
   gesture = response.json()['gesture']
   ```

### 7.4 混合部署（最佳方案）

- **主推理**：OrangePi本地推理（低延迟）
- **备用推理**：云端推理（OrangePi离线或模型未部署时）
- **模型验证**：新模型先在云端测试，稳定后部署到OrangePi

---

## 8. 数据流程总结

### 8.1 实时监控流程（不保存）
```
EMG臂带 → OrangePi → WebSocket → Spring Boot → WebSocket → App显示
（数据在Spring Boot缓存中保留10分钟，然后丢弃）
```

### 8.2 数据标注流程（保存+标注）
```
1. 用户在App上观察实时数据
2. 用户决定"这段数据要保存"
3. 用户选择时间段（如最近5秒）
4. 用户标注手势类型
5. App发送标注请求到Spring Boot
6. Spring Boot从缓存中提取数据
7. 保存到MySQL的emg_labeled_data表
```

### 8.3 模型训练流程
```
1. App发起训练请求
2. Spring Boot创建任务，导出MySQL数据
3. Python训练脚本训练模型
4. 保存模型文件，创建模型版本记录
5. WebSocket通知App训练完成
```

### 8.4 模型部署流程
```
1. App选择模型版本，发起部署请求
2. Spring Boot准备模型文件
3. 模型推送到OrangePi
4. OrangePi加载新模型
5. 开始使用新模型进行推理
```

---

## 9. 关键技术点

### 9.1 数据缓存策略

**使用Redis作为缓存：**
```java
// 缓存Key格式: emg:buffer:{device_id}:{timestamp}
// 过期时间: 10分钟

redisTemplate.opsForValue().set(
    "emg:buffer:" + deviceId + ":" + timestamp,
    jsonData,
    10, TimeUnit.MINUTES
);
```

**或使用内存环形缓冲区：**
```java
// 保留最近10分钟的数据（假设50fps，60秒×10分钟×50=30000帧）
private final RingBuffer<EmgFrame> buffer = 
    new RingBuffer<>(30000);
```

### 9.2 训练任务异步执行

**方案1：Spring异步任务**
```java
@Async
public void executeTraining(Long taskId) {
    // 执行训练逻辑
}
```

**方案2：消息队列**
```java
@RabbitListener(queues = "training.queue")
public void handleTrainingTask(TrainingTask task) {
    // 执行训练
}
```

**方案3：Kubernetes Job**
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: training-job-101
spec:
  template:
    spec:
      containers:
      - name: trainer
        image: emg-trainer:latest
        env:
        - name: TASK_ID
          value: "101"
```

### 9.3 实时进度更新

通过定期解析Python训练脚本的输出更新进度：

```java
BufferedReader reader = new BufferedReader(
    new InputStreamReader(process.getInputStream())
);
String line;
while ((line = reader.readLine()) != null) {
    // 解析输出行："Epoch 23/50 - Loss: 0.234 - Acc: 0.892"
    if (line.contains("Epoch")) {
        updateProgress(taskId, parseEpoch(line));
        webSocketHandler.broadcastTrainingProgress(taskId, ...);
    }
}
```

---

## 10. 安全性考虑

### 10.1 认证授权
- App访问API需要JWT Token
- OrangePi使用设备密钥认证
- 数据标注记录标注人信息

### 10.2 数据隐私
- EMG数据传输使用TLS加密
- 敏感数据脱敏处理
- 遵守数据保护法规

### 10.3 权限控制
- 普通用户：查看、标注
- 管理员：训练模型、部署模型
- 系统：自动化任务

---

## 11. 性能优化

### 11.1 数据传输优化
- WebSocket消息压缩（Gzip）
- 批量传输（降低消息频率）
- 数据降采样（可选）

### 11.2 数据库优化
- 索引优化（时间、手势、状态）
- 分表策略（按月分表）
- 读写分离

### 11.3 训练优化
- 数据预加载（减少I/O）
- GPU加速
- 分布式训练（多设备）

---

## 12. 监控与日志

### 12.1 系统监控
- OrangePi上报健康状态
- Spring Boot Actuator监控
- MySQL性能监控

### 12.2 训练监控
- TensorBoard可视化
- 训练日志持久化
- 异常告警

### 12.3 业务监控
- 数据标注量统计
- 模型推理准确率统计
- 用户活跃度统计

---

## 13. 部署清单

### 13.1 OrangePi
- [x] orangepi_emg_uploader.py（数据采集）
- [ ] inference_engine.py（边缘推理，新增）
- [ ] model_updater.py（模型更新，新增）

### 13.2 Spring Boot后端
- [ ] AnnotationController（数据标注API，新增）
- [ ] TrainingController（训练任务API，新增）
- [ ] ModelController（模型管理API，新增）
- [ ] TrainingService（训练逻辑，新增）
- [ ] CacheService（数据缓存，新增）
- [ ] WebSocket增强（进度推送）

### 13.3 Python训练模块
- [ ] training_server.py（训练任务执行器，新增）
- [ ] export_data_from_mysql.py（数据导出，新增）
- [ ] model_converter.py（模型转换，新增）

### 13.4 HarmonyOS App
- [ ] AnnotationPage.ets（数据标注页面，新增）
- [ ] TrainingPage.ets（训练管理页面，新增）
- [ ] ModelManagePage.ets（模型管理页面，新增）
- [ ] EmgRealtimePage.ets（增强功能）

### 13.5 MySQL
- [ ] emg_labeled_data表
- [ ] training_task表
- [ ] model_version表

---

## 14. 开发计划

**阶段1：数据标注功能（1周）**
- [ ] MySQL表创建
- [ ] Spring Boot标注API
- [ ] 数据缓存实现
- [ ] App标注页面

**阶段2：训练功能（2周）**
- [ ] Python训练脚本改造
- [ ] Spring Boot训练任务管理
- [ ] 异步任务执行
- [ ] App训练页面

**阶段3：模型管理与部署（1周）**
- [ ] 模型版本管理
- [ ] 模型转换（ONNX）
- [ ] OrangePi推理引擎
- [ ] 模型自动更新

**阶段4：测试与优化（1周）**
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 文档完善

---

## 15. 总结

这个架构设计实现了：
- ✅ **数据采集与监控分离**：实时数据不自动保存，由用户控制
- ✅ **灵活的数据标注**：App端便捷标注，支持预览和批量操作
- ✅ **自动化训练**：App一键触发，后台异步执行
- ✅ **智能模型管理**：版本化管理，支持多种部署方式
- ✅ **边缘推理优化**：OrangePi本地推理，低延迟高可用
- ✅ **可扩展架构**：支持多设备、多用户、分布式训练

建议优先实现**阶段1和阶段2**，确保数据标注和训练流程打通，再逐步完善模型部署功能。
