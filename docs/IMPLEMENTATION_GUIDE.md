# EMG手势识别系统 - 实施指南

## 📋 目录

- [系统概述](#系统概述)
- [快速开始](#快速开始)
- [详细实施步骤](#详细实施步骤)
- [测试验证](#测试验证)
- [常见问题](#常见问题)
- [参考文档](#参考文档)

---

## 系统概述

### 核心改进

本次架构升级实现了以下核心功能：

1. **数据采集与标注分离** ✅
   - KunpengPro采集的EMG数据默认**不保存**到MySQL
   - 数据在Spring Boot缓存10分钟
   - 用户通过App主动选择标注和保存

2. **灵活的数据标注** ✅
   - App端便捷标注界面
   - 支持预览缓存数据
   - 批量标注和质量控制

3. **自动化模型训练** ✅
   - App一键发起训练任务
   - 后台异步执行Python训练脚本
   - 实时进度更新和结果查询

4. **智能模型管理** ✅
   - 版本化管理所有训练模型
   - 支持边缘（KunpengPro）和云端部署
   - 模型自动更新机制

### 架构图

```
┌──────────┐       ┌──────────────┐       ┌───────────────┐       ┌──────────┐
│ EMG臂带  │──串口──│  KunpengPro    │──WS──│ Spring Boot   │──WS──│ HarmonyOS│
│          │       │              │      │  + MySQL      │      │   App    │
│          │       │ • 采集数据    │      │ • 缓存数据    │      │ • 标注   │
│          │       │ • 本地推理    │      │ • 训练管理    │      │ • 训练   │
│          │       │              │      │ • 模型管理    │      │ • 部署   │
└──────────┘       └──────────────┘       └───────────────┘       └──────────┘
                           ↓                      ↓
                   ┌──────────────┐       ┌──────────────┐
                   │  模型文件    │       │  Python训练  │
                   │  (ONNX)     │       │  服务        │
                   └──────────────┘       └──────────────┘
```

---

## 快速开始

### 前置条件

1. **硬件**
   - KunpengPro（已配置好开发环境）
   - EMG臂带
   - 开发PC（Windows/Linux/Mac）

2. **软件**
   - 华为云ECS（Spring Boot后端）
   - 华为云RDS MySQL
   - HarmonyOS开发环境（DevEco Studio）
   - Python 3.8+（用于训练）

3. **网络**
   - KunpengPro和ECS可以互相访问
   - App可以访问ECS公网IP

### 30分钟快速部署

#### 第1步：数据库升级（5分钟）

```bash
# 连接到华为云RDS MySQL
mysql -h your-rds-host -u root -p

# 执行数据库升级脚本
source docs/rds_mysql_schema_with_training.sql
```

#### 第2步：部署Spring Boot后端（10分钟）

```bash
# 1. 更新代码
cd springboot_backend
git pull  # 如果使用Git

# 2. 添加新的实体类、Mapper、Controller、Service
# （已在上面创建的文件中）

# 3. 修改配置文件
vim src/main/resources/application.yml
```

添加新的配置：

```yaml
training:
  workspace: /opt/emg/training
  python:
    executable: python3
  script:
    path: /opt/emg/scripts/training_server.py

model:
  storage:
    path: /opt/emg/models
```

```bash
# 4. 编译打包
mvn clean package -DskipTests

# 5. 重启服务
java -jar target/emg-backend.jar
```

#### 第3步：部署Python训练脚本（5分钟）

```bash
# 在ECS上创建目录
ssh your-ecs
sudo mkdir -p /opt/emg/scripts
sudo mkdir -p /opt/emg/training
sudo mkdir -p /opt/emg/models

# 上传训练脚本
scp code/scripts/training_server.py your-ecs:/opt/emg/scripts/

# 安装Python依赖
ssh your-ecs
pip3 install torch numpy scikit-learn
```

#### 第4步：更新KunpengPro采集程序（5分钟）

```bash
# 修改KunpengPro_emg_uploader.py
# 确保数据上传到Spring Boot的WebSocket接口
# （现有代码已经实现，无需修改）

# 重启KunpengPro服务
ssh KunpengPro
sudo systemctl restart emg-uploader
```

#### 第5步：部署HarmonyOS App（5分钟）

```bash
# 1. 在DevEco Studio中打开项目

# 2. 将新的页面文件添加到项目
# - AnnotationPage.ets
# - TrainingPage.ets  
# - ModelManagePage.ets

# 3. 修改 module.json5，添加网络权限（如果未添加）

# 4. 修改 SERVER_URL 为你的ECS公网IP
	
# 5. 编译并安装到HarmonyOS设备
```

---

## 详细实施步骤

### 阶段1：数据标注功能（1周）

#### 1.1 数据库准备

```sql
-- 1. 创建标注数据表
CREATE TABLE emg_labeled_data (...);

-- 2. 创建标注会话表
CREATE TABLE annotation_session (...);

-- 3. 创建统计视图
CREATE VIEW v_annotation_statistics AS ...;

-- 4. 验证表结构
SHOW TABLES;
DESC emg_labeled_data;
```

#### 1.2 Spring Boot后端开发

**创建的文件清单：**

- [x] `entity/EmgLabeledData.java` - 标注数据实体
- [x] `entity/AnnotationSession.java` - 标注会话实体
- [x] `mapper/EmgLabeledDataMapper.java` - Mapper接口
- [x] `dto/AnnotationRequest.java` - 请求DTO
- [x] `service/AnnotationService.java` - 业务逻辑
- [x] `controller/AnnotationController.java` - REST API
- [x] 修改 `service/EmgDataService.java` - 添加缓存功能

**关键改动：EmgDataService**

```java
// 原来：数据自动保存到MySQL
writeBuffer.add(frame);

// 现在：数据仅缓存在内存
dataCache.add(frameMap);  // 保留10分钟
// App发起标注请求后才保存到emg_labeled_data表
```

**测试API：**

```bash
# 1. 获取缓存数据
curl "http://localhost:8080/api/annotation/cache-data?device_id=KunpengPro_01"

# 2. 保存标注
curl -X POST http://localhost:8080/api/annotation/save \\
  -H "Content-Type: application/json" \\
  -d '{
    "device_id": "KunpengPro_01",
    "start_time": "2026-03-10T10:00:00",
    "end_time": "2026-03-10T10:00:05",
    "gesture_label": "fist",
    "annotator": "user01"
  }'

# 3. 查询统计
curl http://localhost:8080/api/annotation/statistics
```

#### 1.3 HarmonyOS App开发

**AnnotationPage.ets 核心功能：**

1. **手势选择**：6种手势类型（fist/ok/pinch/relax/sidegrip/ye）
2. **录制控制**：可配置录制时长（1-10秒）
3. **实时预览**：查看缓存数据
4. **标注统计**：显示各手势样本分布

**使用流程：**

```
用户操作 → 选择手势类型 → 点击"开始录制" → 做出手势动作 → 
自动停止 → 数据保存到MySQL → 查看统计信息
```

**测试步骤：**

1. 打开AnnotationPage
2. 选择手势"fist"
3. 设置录制时长为5秒
4. 点击"开始录制"
5. 戴上EMG臂带，做出握拳动作
6. 等待5秒自动停止
7. 查看"标注统计"，确认数据已保存

### 阶段2：训练功能（2周）

#### 2.1 Python训练脚本

**training_server.py 功能：**

- 从指定目录加载CSV格式的标注数据
- 使用滑动窗口和数据增强
- 训练CNN-LSTM模型
- 保存最佳模型和训练结果
- 实时输出进度（供Spring Boot解析）

**本地测试训练：**

```bash
# 准备测试数据
mkdir -p /tmp/training_test/fist
mkdir -p /tmp/training_test/ok

# 生成模拟数据
python3 generate_test_data.py

# 运行训练
python3 code/scripts/training_server.py \\
  --data /tmp/training_test \\
  --config /tmp/config.json \\
  --task-id 1

# 检查输出
cat /tmp/training_test/training.log
cat /tmp/training_test/result.json
```

#### 2.2 Spring Boot训练服务

**TrainingService.java 核心流程：**

```
1. 创建训练任务记录（状态：pending）
2. 从MySQL导出标注数据到CSV
3. 生成训练配置文件
4. 启动Python训练进程（异步）
5. 解析进度输出，更新数据库
6. 训练完成，保存模型和结果
7. 创建ModelVersion记录
8. 通过WebSocket通知App
```

**测试API：**

```bash
# 1. 创建训练任务
curl -X POST http://localhost:8080/api/training/create \\
  -H "Content-Type: application/json" \\
  -d '{
    "task_name": "测试训练_20260310",
    "config": {
      "epochs": 10,
      "batch_size": 32,
      "learning_rate": 0.001,
      "window_size": 150
    },
    "data_filter": {
      "gestures": ["fist", "ok"],
      "min_quality_score": 0.8
    },
    "created_by": "test_user"
  }'

# 2. 查询任务状态
curl http://localhost:8080/api/training/task/1

# 3. 获取训练日志
curl http://localhost:8080/api/training/task/1/logs?lines=50

# 4. 获取训练结果
curl http://localhost:8080/api/training/task/1/result
```

#### 2.3 HarmonyOS训练页面

**TrainingPage.ets 功能：**

- Tab 1: 新建训练
  - 配置训练参数（epochs、batch size等）
  - 发起训练任务
  - 实时显示训练进度
  
- Tab 2: 训练历史
  - 查看所有训练任务
  - 查看历史训练结果

**使用流程：**

```
打开TrainingPage → 配置参数 → 点击"开始训练" → 
等待训练完成（后台异步） → 查看准确率
```

### 阶段3：模型管理与部署（1周）

#### 3.1 模型版本管理

**ModelService.java 功能：**

- 从训练任务创建模型版本
- 自动生成版本号（v1.0.0, v1.0.1...）
- 记录模型性能指标
- 支持激活/停用模型
- 提供模型文件下载

**测试API：**

```bash
# 1. 获取所有模型版本
curl http://localhost:8080/api/model/versions

# 2. 获取当前激活的模型
curl http://localhost:8080/api/model/active

# 3. 下载模型文件
curl -O http://localhost:8080/api/model/download/v1.0.0

# 4. 激活模型
curl -X POST http://localhost:8080/api/model/v1.0.0/activate
```

#### 3.2 模型转换

```bash
# PyTorch → ONNX
python3 code/conversion/convert.py \\
  --input /opt/emg/training/task_1/best_model.pth \\
  --output /opt/emg/models/v1.0.0.onnx \\
  --format onnx

# 验证ONNX模型
python3 validate_onnx.py /opt/emg/models/v1.0.0.onnx
```

#### 3.3 部署到KunpengPro

**方案1：自动下载（推荐）**

```python
# KunpengPro上运行model_updater.py
python3 /opt/emg/model_updater.py

# 它会：
# 1. 定期检查Spring Boot的/api/model/active
# 2. 如果有新版本，自动下载
# 3. 更新软链接 /opt/emg/models/model.onnx
# 4. 推理引擎热加载新模型
```

**方案2：手动推送**

```bash
# 从App发起部署请求
curl -X POST http://localhost:8080/api/model/deploy \\
  -H "Content-Type: application/json" \\
  -d '{
    "version": "v1.0.0",
    "target_type": "KunpengPro",
    "target_device_id": "KunpengPro_01",
    "set_as_active": true
  }'
```

#### 3.4 推理引擎集成

修改 `KunpengPro_emg_uploader.py`：

```python
from inference_engine import GestureInferenceEngine

# 初始化
engine = GestureInferenceEngine('/opt/emg/models/model.onnx')

# 在数据采集循环中
def process_emg_frame(frame_data):
    emg = frame_data['emg'][0]  # 第一行8通道
    
    # 添加到推理缓冲区
    engine.add_frame(emg)
    
    # 推理
    if engine.is_ready():
        gesture, confidence = engine.predict()
        frame_data['gesture'] = gesture
        frame_data['confidence'] = float(confidence)
    
    # 上传到Spring Boot
    upload_to_server(frame_data)
```

### 阶段4：测试与优化（1周）

#### 4.1 端到端测试

**测试场景1：数据标注流程**

```
1. KunpengPro启动，开始采集数据
2. App打开实时监控页面，查看数据
3. App切换到标注页面
4. 用户选择手势"fist"，点击"开始录制"
5. 用户做出握拳动作5秒
6. 数据自动保存到MySQL
7. 查看统计信息，确认增加了150帧左右的数据
```

**测试场景2：模型训练流程**

```
1. 确保已标注至少500个样本（每个手势至少100个）
2. App打开训练页面
3. 配置训练参数：epochs=30, batch_size=32
4. 点击"开始训练"
5. 观察训练进度实时更新
6. 等待训练完成（约20-30分钟）
7. 查看准确率（应>85%）
```

**测试场景3：模型部署流程**

```
1. App打开模型管理页面
2. 查看最新训练的模型版本
3. 选择该版本，点击"部署"
4. 选择目标"KunpengPro"
5. 等待部署完成
6. 在实时监控页面观察推理结果
7. 做出不同手势，验证识别准确性
```

#### 4.2 性能优化

**后端优化：**

```java
// 1. 启用数据缓存压缩（Redis）
@Cacheable(value = "emg_cache", compression = true)

// 2. 批量写入优化
@Transactional(propagation = Propagation.REQUIRES_NEW)
public void batchInsert(List<EmgLabeledData> data) {
    labeledDataMapper.insertBatch(data);
}

// 3 . 异步任务线程池配置
@Bean
public Executor taskExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(4);
    executor.setMaxPoolSize(8);
    executor.setQueueCapacity(100);
    return executor;
}
```

**训练优化：**

```python
# 使用GPU加速（如果可用）
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 数据加载优化
train_loader = DataLoader(
    train_dataset, 
    batch_size=batch_size, 
    shuffle=True,
    num_workers=4,  # 多进程加载
    pin_memory=True  # GPU固定内存
)

# 混合精度训练
from torch.cuda.amp import autocast, GradScaler
scaler = GradScaler()

with autocast():
    output = model(data)
    loss = criterion(output, target)
```

**推理优化：**

```python
# 模型量化
quantized_model = quantize_dynamic(model, {nn.Linear, nn.LSTM}, dtype=torch.qint8)

# 批量推理
predictions = model(batch_data)  # 比逐个推理快3-5倍

# 使用ONNX Runtime
session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
```

---

## 测试验证

### 单元测试

```bash
# Spring Boot测试
cd springboot_backend
mvn test

# Python训练测试
cd code
pytest tests/
```

### 集成测试

```bash
# 启动所有服务
docker-compose up -d

# 运行集成测试
python3 tests/test_integration.py
```

### 压力测试

```bash
# 模拟100个并发用户
ab -n 1000 -c 100 http://localhost:8080/api/annotation/statistics

# WebSocket压力测试
python3 tests/test_websocket_load.py
```

---

## 常见问题

### Q1: KunpengPro上报的数据在Spring Boot中找不到？

**排查步骤：**
1. 检查WebSocket连接状态
2. 查看Spring Boot日志：`tail -f logs/emg-backend.log`
3. 检查防火墙设置
4. 验证dataCache是否正常工作

```java
// 添加调试日志
log.info("当前缓存大小: {}", dataCache.size());
```

### Q2: 训练任务一直pending，没有开始？

**可能原因：**
1. Python环境未安装
2. 训练脚本路径错误
3. 没有标注数据

**解决方法：**
```bash
# 检查Python
which python3
python3 --version

# 检查训练脚本
ls -l /opt/emg/scripts/training_server.py

# 检查数据
mysql> SELECT COUNT(*) FROM emg_labeled_data;
```

### Q3: 模型部署后推理结果不准确？

**可能原因：**
1. 模型未正确加载
2. 数据预处理不一致
3. 训练数据质量问题

**解决方法：**
```python
# 1. 验证模型
python3 validate_model.py --model /opt/emg/models/model.onnx

# 2. 检查数据预处理
# 确保训练和推理使用相同的归一化方法

# 3. 查看推理日志
tail -f /var/log/emg-inference.log
```

### Q4: App无法连接到Spring Boot？

**排查步骤：**
1. 检查ECS安全组，开放8080端口
2. 检查Spring Boot是否启动：`curl http://localhost:8080/api/model/versions`
3. 修改App中的SERVER_URL为正确的公网IP
4. 检查网络连接

---

## 参考文档

### 已创建的文档

1. **[架构设计文档](docs/ARCHITECTURE_DESIGN.md)**
   - 系统架构总览
   - 数据库设计
   - API接口设计
   - WebSocket协议
   - 训练流程设计

2. **[模型部署指南](docs/MODEL_DEPLOYMENT_GUIDE.md)**
   - 边缘部署方案
   - 云端部署方案
   - 模型转换与优化
   - 监控与运维

3. **[数据库Schema](docs/rds_mysql_schema_with_training.sql)**
   - 所有表结构
   - 视图和存储过程
   - 索引优化

### 代码文件清单

#### Spring Boot后端（新增/修改）

**实体类（Entity）：**
- `EmgLabeledData.java` - 标注数据
- `TrainingTask.java` - 训练任务
- `ModelVersion.java` - 模型版本
- `AnnotationSession.java` - 标注会话

**Mapper接口：**
- `EmgLabeledDataMapper.java`
- `TrainingTaskMapper.java`
- `ModelVersionMapper.java`

**DTO类：**
- `AnnotationRequest.java`
- `TrainingTaskCreateRequest.java`
- `ModelDeployRequest.java`

**Service服务：**
- `AnnotationService.java` - 标注业务逻辑
- `TrainingService.java` - 训练任务管理
- `ModelService.java` - 模型管理
- `EmgDataService.java` - 修改：添加缓存功能

**Controller控制器：**
- `AnnotationController.java` - 标注API
- `TrainingController.java` - 训练API
- `ModelController.java` - 模型API

#### Python训练模块

- `code/scripts/training_server.py` - 训练脚本
- `code/conversion/convert.py` - 模型转换（待完善）

#### HarmonyOS App

- `harmony_app/AnnotationPage.ets` - 数据标注页面
- `harmony_app/TrainingPage.ets` - 模型训练页面
- `harmony_app/ModelManagePage.ets` - 模型管理页面

#### KunpengPro脚本

- `inference_engine.py` - 推理引擎（见部署指南）
- `model_updater.py` - 模型更新服务（见部署指南）

---

## 下一步工作

### 短期（1-2周）

- [ ] 完善数据质量评估算法
- [ ] 实现训练进度实时WebSocket推送
- [ ] 优化缓存机制（考虑使用Redis）
- [ ] 完善错误处理和日志记录

### 中期（1个月）

- [ ] 实现A/B测试功能（同时测试多个模型）
- [ ] 添加数据增强功能
- [ ] 实现模型性能追踪和对比
- [ ] 开发Web管理后台

### 长期（3个月）

- [ ] 支持分布式训练
- [ ] 实现联邦学习（多设备协同训练）
- [ ] 模型自动调优（AutoML）
- [ ] 移动端模型优化（量化、剪枝）

---

## 技术支持

如有问题，请：

1. 查看日志文件
2. 参考[常见问题](#常见问题)
3. 查阅相关文档
4. 联系技术支持团队

---

**文档版本：** v1.0  
**最后更新：** 2026-03-10  
**作者：** EMG手势识别系统开发团队

