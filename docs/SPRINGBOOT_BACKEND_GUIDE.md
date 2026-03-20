# Spring Boot 后端功能介绍

## 📋 目录

- [系统概述](#系统概述)
- [技术架构](#技术架构)
- [核心功能模块](#核心功能模块)
- [API接口文档](#api接口文档)
- [WebSocket协议](#websocket协议)
- [数据库设计](#数据库设计)
- [配置说明](#配置说明)
- [部署运维](#部署运维)
- [性能优化](#性能优化)

---

## 🎯 系统概述

### 项目定位

EMG 后端是华为 ICT 赛道肌电手势识别系统的**云端核心服务**，基于 **Spring Boot 2.7** 构建，提供 RESTful API 和 WebSocket 双通道实时通信能力，实现边缘设备数据采集、云端存储、AI 训练管理、模型版本控制等完整生命周期管理。

### 核心职责

```
┌─────────────────────────────────────────────────────────────────┐
│                    Spring Boot 后端核心职责                      │
└─────────────────────────────────────────────────────────────────┘

📊 数据管理
  ├── 接收 OrangePi/Windows 上报的 EMG 数据（1000Hz 采样率）
  ├── 实时存储至华为云 RDS MySQL
  ├── 缓存最新数据至内存（低延迟访问）
  └── 数据清理策略（默认保留7天）

🔄 实时通信
  ├── WebSocket /ws/emg：接收边缘设备数据流
  ├── WebSocket /ws/app：推送至 HarmonyOS 客户端
  ├── 双向消息路由与广播
  └── 断线重连与状态管理

🧠 AI 训练管理
  ├── 创建训练任务（支持多种模型架构）
  ├── 实时跟踪训练进度（epoch, loss, accuracy）
  ├── 训练日志存储与查询
  └── 训练结果评估与导出

📦 模型生命周期
  ├── 模型版本管理（MindIR, ONNX, TFLite等）
  ├── 模型激活/停用
  ├── 模型下载服务（边缘部署）
  └── 性能指标跟踪

🏷️ 数据标注
  ├── 时间段数据快速预览
  ├── 手势标注与保存
  ├── 标注统计与质量分析
  └── 导出训练数据集
```

---

## 🏗️ 技术架构

### 技术栈

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **核心框架** | Spring Boot | 2.7.18 | Web 应用框架 |
| **Web 层** | Spring MVC | - | RESTful API |
| **实时通信** | Spring WebSocket | - | 双向实时消息 |
| **持久层** | MyBatis Plus | 3.5.5 | ORM 框架 |
| **数据库** | MySQL | 8.0 | 关系型数据库 |
| **连接池** | Druid | 1.2.21 | 高性能连接池 |
| **JSON** | FastJSON2 | 2.0.43 | JSON 序列化 |
| **工具类** | Lombok | - | 简化 Java 代码 |

### 架构分层

```
┌─────────────────────────────────────────────────────────────────┐
│                         Presentation Layer                       │
│                          表现层（控制器）                         │
├───────────────┬───────────────┬───────────────┬─────────────────┤
│ EmgController │TrainingCtrl   │ ModelCtrl     │AnnotationCtrl   │
│ (数据管理)    │ (训练任务)    │ (模型管理)    │ (数据标注)      │
└───────┬───────┴───────┬───────┴───────┬───────┴─────────┬───────┘
        │               │               │                 │
┌───────▼─────────────────────────────────────────────────▼───────┐
│                         Business Layer                           │
│                          业务逻辑层（服务）                       │
├───────────────┬───────────────┬───────────────┬─────────────────┤
│EmgDataService │TrainingService│ ModelService  │AnnotationSvc    │
│ (数据处理)    │ (任务管理)    │ (版本管理)    │ (标注处理)      │
└───────┬───────┴───────┬───────┴───────┬───────┴─────────┬───────┘
        │               │               │                 │
┌───────▼─────────────────────────────────────────────────▼───────┐
│                         Persistence Layer                        │
│                          持久层（数据访问）                       │
├───────────────┬───────────────┬───────────────┬─────────────────┤
│ EmgFrameMapper│TrainingMapper │ModelVerMapper │LabeledDataMapper│
│ (原始数据)    │ (训练任务)    │ (模型版本)    │ (标注数据)      │
└───────┬───────┴───────┬───────┴───────┬───────┴─────────┬───────┘
        │               │               │                 │
        └───────────────┴───────────────┴─────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │  华为云 RDS MySQL    │
                    │  (ict_db 数据库)     │
                    └──────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        WebSocket Layer                           │
│                      WebSocket 通信层                            │
├───────────────────────────────────────────────────────────────┬─┤
│ EmgWebSocketHandler                                           │ │
│ - /ws/emg : 接收边缘设备数据                                  │ │
│ - /ws/app : 推送至移动应用                                    │ │
│ - 消息路由与广播                                              │ │
│ - 会话管理（手势选择、状态跟踪）                              │ │
└─────────────────────────────────────────────────────────────────┘
```

### 项目结构

```
springboot_backend/
├── src/main/
│   ├── java/com/huaweiict/emg/
│   │   ├── EmgBackendApplication.java    # 启动类
│   │   │
│   │   ├── config/                       # 配置类
│   │   │   ├── CorsConfig.java           # 跨域配置
│   │   │   └── WebSocketConfig.java      # WebSocket 配置
│   │   │
│   │   ├── controller/                   # REST 控制器
│   │   │   ├── EmgController.java        # EMG 数据 API
│   │   │   ├── TrainingController.java   # 训练任务 API
│   │   │   ├── ModelController.java      # 模型管理 API
│   │   │   └── AnnotationController.java # 数据标注 API
│   │   │
│   │   ├── service/                      # 业务逻辑层
│   │   │   ├── EmgDataService.java       # 数据处理服务
│   │   │   ├── TrainingService.java      # 训练管理服务
│   │   │   ├── ModelService.java         # 模型管理服务
│   │   │   └── AnnotationService.java    # 标注服务
│   │   │
│   │   ├── mapper/                       # MyBatis 映射器
│   │   │   ├── EmgFrameMapper.java       # EMG 数据 DAO
│   │   │   ├── TrainingTaskMapper.java   # 训练任务 DAO
│   │   │   ├── ModelVersionMapper.java   # 模型版本 DAO
│   │   │   └── EmgLabeledDataMapper.java # 标注数据 DAO
│   │   │
│   │   ├── entity/                       # JPA 实体类
│   │   │   ├── EmgFrame.java             # EMG 数据帧
│   │   │   ├── TrainingTask.java         # 训练任务
│   │   │   ├── ModelVersion.java         # 模型版本
│   │   │   └── EmgLabeledData.java       # 标注数据
│   │   │
│   │   ├── dto/                          # 数据传输对象
│   │   │   ├── EmgFrameDTO.java          # EMG 数据 DTO
│   │   │   ├── EmgBatchRequest.java      # 批量上报请求
│   │   │   ├── TrainingTaskCreateRequest.java
│   │   │   ├── ModelDeployRequest.java
│   │   │   └── AnnotationRequest.java
│   │   │
│   │   └── websocket/                    # WebSocket 处理器
│   │       └── EmgWebSocketHandler.java  # WebSocket 端点
│   │
│   └── resources/
│       ├── application.yml               # Spring Boot 配置
│       └── mapper/                       # MyBatis XML (可选)
│
└── pom.xml                               # Maven 依赖配置
```

---

## ⚙️ 核心功能模块

### 模型训练与更新（实现流程）

1) 训练任务创建：`TrainingService.createTask()` 保存任务、统计数据集、异步启动训练。
2) 数据导出：按筛选条件导出标注数据到 `training.workspace/task_{id}`，生成配置文件。
3) 训练执行：`executeTrainingProcess` 调用 Python 脚本（配置 `training.python.executable` 与 `training.script.path`）。
4) 结果处理：读取 `result.json`，写回精度、损失、模型路径，状态置为 completed。
5) 模型入库：`ModelService.createModelVersion()` 生成版本号、记录精度/大小/路径，默认不激活。
6) 部署与激活：`/api/model/deploy` 触发部署（cloud/orangepi），可选 `setAsActive`；`/api/model/{version}/activate` 切换激活版本。

关键配置（application.yml）：

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

API 入口：
- 创建任务：`POST /api/training/create`
- 查询任务：`GET /api/training/task/{taskId}`、`/logs`、`/result`
- 部署模型：`POST /api/model/deploy`
- 激活模型：`POST /api/model/{version}/activate`
- 下载模型：`GET /api/model/download/{version}`

### 0. 用户认证模块 (New)

#### 功能概述

提供基于 JWT (JSON Web Token) 的用户认证机制，保障系统安全性。

#### 核心能力

**✅ 用户注册**
- 密码加密存储 (BCrypt)
- 防止重复用户名注册

**✅ 用户登录**
- 验证用户名密码
- 颁发 JWT Token (包含 userId, username, role)
- Token 有效期管理

**✅ 安全拦截**
- Spring Security 全局拦截
- 开放接口：`/auth/**`, `/api/emg/**`, `/ws/**`
- 受保护接口：`/api/training/**`, `/api/model/**` 等需携带 `Authorization: Bearer <token>`

---

### 1. EMG 数据管理模块

#### 功能概述

负责接收、存储、查询 EMG 肌电数据，支持批量上报和单帧上报两种模式。

#### 核心能力

**✅ 数据接收**
- HTTP 批量上报：OrangePi 一次上传多帧数据（备用通道）
- WebSocket 实时流：低延迟的持续数据推送（主通道）
- 数据验证：检查数据完整性与合法性

**✅ 数据存储**
- MySQL 持久化：完整时序数据存储
- 内存缓存：最新 1 帧数据快速访问
- 批量写入优化：减少数据库 I/O

**✅ 数据查询**
- 最新数据：`/api/emg/latest` - 获取最新一帧
- 历史回溯：`/api/emg/history` - 按设备/时间查询
- 手势事件：`/api/gesture/events` - 查询识别历史

**✅ 数据清理**
- 自动清理策略：默认保留 7 天数据
- 手动清理接口：按时间段删除旧数据

#### 数据流向

```
┌─────────────┐
│  OrangePi   │
│  (边缘设备) │
└──────┬──────┘
       │
       ├─────► WebSocket /ws/emg (主通道, 实时推送)
       │       ↓
       │   ┌───────────────────────────────┐
       │   │ EmgWebSocketHandler           │
       │   │ - 接收 10×8 EMG 矩阵          │
       │   │ - 更新内存缓存                │
       │   │ - 广播至 App 客户端           │
       │   └───────────┬───────────────────┘
       │               │
       └─────► HTTP POST /api/emg/batch (备用通道)
                       │
                       ▼
               ┌───────────────┐
               │EmgDataService │
               │- processFrame │
               │- processBatch │
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │ EmgFrameMapper│
               │ (批量插入)    │
               └───────┬───────┘
                       │
                       ▼
               ┌───────────────┐
               │  MySQL RDS    │
               │ emg_frames 表 │
               └───────────────┘
```

#### 代码示例

```java
// 批量上报
@PostMapping("/api/emg/batch")
public Map<String, Object> batchUpload(@RequestBody EmgBatchRequest request) {
    emgDataService.processBatch(request.getDeviceId(), request.getFrames());
    return Map.of("code", 200, "received", request.getFrames().size());
}

// 获取最新数据
@GetMapping("/api/emg/latest")
public Map<String, Object> getLatest() {
    return emgDataService.getLatestFrame();
}
```

---

### 1.5 统计分析模块 (New)

#### 功能概述

记录用户的每日康复训练使用情况，为前端提供可视化报表数据。

#### 核心能力

**✅ 每日统计**
- 记录每日使用次数、舒适度评分
- 自动计算每日最大/平均使用量

**✅ 长期趋势**
- 查询最近 7 天的使用趋势
- 分析用户适应阶段（初期/适应期/稳定期）

#### API 示例

```java
// 上报使用记录
@PostMapping("/api/stats/update")
public ResponseEntity<String> updateUsage(@RequestParam Long userId) {
    dailyUsageStatsService.saveOrUpdateTodayStats(userId, 1, null);
    return ResponseEntity.ok("Updated");
}

// 获取今日统计
@GetMapping("/api/stats/today")
public ResponseEntity<?> getTodayStats(@RequestParam Long userId) {
    return ResponseEntity.ok(stats);
}
```

---

### 2. WebSocket 实时通信模块

#### 功能概述

提供低延迟的双向实时通信，支持边缘设备数据上报和移动应用数据订阅。

#### 端点说明

| 端点 | 客户端类型 | 用途 | 消息方向 |
|------|-----------|------|----------|
| `/ws/emg` | OrangePi/Windows | 边缘设备数据上报 | 设备 → 服务器 |
| `/ws/app` | HarmonyOS App | 移动应用实时订阅 | 服务器 ↔ 应用 |

#### 核心能力

**✅ 连接管理**
- 会话跟踪：为每个连接分配唯一 Session ID
- 心跳检测：定期检查连接健康状态
- 断线重连：客户端自动重连机制
- 并发控制：支持多设备同时连接

**✅ 消息路由**
- `/ws/emg` 接收数据 → 广播至所有 `/ws/app` 客户端
- 消息类型识别：`action` 字段路由不同处理逻辑
- 错误消息推送：格式错误时返回错误信息

**✅ 状态管理 ⭐ 新增（Training 页面支持）**
- 手势选择跟踪：记录每个 App 会话选择的训练手势
- 训练状态同步：开始/停止训练事件记录
- 会话隔离：多用户同时训练互不干扰

#### 消息协议

**客户端 → 服务端 (App 发送)**

```json
// 1. 请求最新数据
{
  "action": "get_latest"
}

// 2. 选择训练手势 (Training 页面)
{
  "action": "select_gesture",
  "gesture": "握拳"  // 或 "张开", "捏取", "侧握", "伸展", "放松"
}

// 3. 训练控制
{
  "action": "start_training",
  "gesture": "握拳",
  "targetReps": 50
}

{
  "action": "stop_training"
}
```

**服务端 → 客户端 (App 接收)**

```json
// 1. 手势选择确认
{
  "type": "gesture_selected",
  "gesture": "握拳",
  "timestamp": 1709894400000
}

// 2. 实时 EMG 数据帧（持续推送）
{
  "deviceId": "EMG_WIN_001",
  "deviceTs": 1709894400000,
  "serverTime": "2024-03-08T12:00:00.000",
  "gesture": "FIST",          // AI 识别结果
  "confidence": 0.92,
  "battery": 85,
  "emg": [
    [120, 130, 125, 118, 122, 128, 115, 119],  // 第1包
    [121, 131, 126, 119, 123, 129, 116, 120],  // 第2包
    // ... 共10包
    [129, 139, 134, 127, 131, 137, 124, 128]   // 第10包（最新）
  ],
  "acc": [0.05, 0.98, 0.15],  // 加速度
  "gyro": [0.02, -0.01, 0.03],  // 陀螺仪
  "angle": [2.5, -1.2, 0.8]   // 欧拉角
}
```

#### 实现细节

```java
@Component
public class EmgWebSocketHandler extends TextWebSocketHandler {
    
    // App 客户端当前选择的训练手势 (sessionId → gesture)
    private final Map<String, String> selectedGestures = new ConcurrentHashMap<>();
    
    // 连接建立
    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        if (isEmgSession(session)) {
            emgSessions.put(session.getId(), session);
        } else {
            appSessions.put(session.getId(), session);
        }
    }
    
    // 处理 App 消息
    private void handleAppMessage(WebSocketSession session, String payload) {
        JSONObject json = JSON.parseObject(payload);
        String action = json.getString("action");
        
        if ("select_gesture".equals(action)) {
            String gesture = json.getString("gesture");
            selectedGestures.put(session.getId(), gesture);
            
            // 发送确认消息
            JSONObject ack = new JSONObject();
            ack.put("type", "gesture_selected");
            ack.put("gesture", gesture);
            ack.put("timestamp", System.currentTimeMillis());
            session.sendMessage(new TextMessage(ack.toJSONString()));
        }
    }
    
    // 广播至所有 App 客户端
    public void broadcastToApp(String message) {
        for (WebSocketSession session : appSessions.values()) {
            if (session.isOpen()) {
                session.sendMessage(new TextMessage(message));
            }
        }
    }
}
```

---

### 3. 训练任务管理模块

#### 功能概述

管理 AI 模型训练的完整生命周期，支持任务创建、进度跟踪、结果查询等功能。

#### 核心能力

**✅ 任务创建**
- 支持参数配置：学习率、批次大小、训练轮数等
- 数据集选择：指定训练数据的时间范围或标注集
- 模型架构选择：CNN、LSTM、Transformer 等
- 资源分配：GPU/CPU、内存配置

**✅ 进度跟踪**
- 实时更新：当前 epoch、loss、accuracy
- 剩余时间估算：基于已完成 epoch 的平均耗时
- 日志记录：每个 epoch 的详细指标
- 状态管理：pending → running → completed/failed

**✅ 结果管理**
- 训练指标：训练集/验证集的 loss 和 accuracy
- 模型保存：自动保存最佳模型（best_model.ckpt）
- 评估报告：混淆矩阵、PR 曲线等
- 导出功能：导出为 ONNX、TFLite 等格式

#### 训练任务状态机

```
┌──────────────┐
│   pending    │  任务已创建，等待资源
│   (待执行)   │
└──────┬───────┘
       │ 资源就绪
       ▼
┌──────────────┐
│   running    │  正在训练中
│   (训练中)   │  - 更新进度
└──────┬───────┘  - 记录 loss/acc
       │
       ├────► completed (训练成功)
       ├────► failed (训练失败)
       └────► cancelled (用户取消)
```

#### API 示例

```java
// 创建训练任务
@PostMapping("/api/training/create")
public Map<String, Object> createTask(@RequestBody TrainingTaskCreateRequest request) {
    Long taskId = trainingService.createTask(request);
    return Map.of(
        "code", 200,
        "data", Map.of("task_id", taskId, "estimated_time_minutes", 30)
    );
}

// 查询任务状态
@GetMapping("/api/training/task/{taskId}")
public Map<String, Object> getTaskStatus(@PathVariable Long taskId) {
    TrainingTask task = trainingService.getTask(taskId);
    return Map.of(
        "code", 200,
        "data", Map.of(
            "status", task.getTaskStatus(),
            "progress", task.getProgressPercent(),
            "current_epoch", task.getCurrentEpoch(),
            "val_accuracy", task.getValAccuracy()
        )
    );
}

// 获取训练日志
@GetMapping("/api/training/logs/{taskId}")
public Map<String, Object> getLogs(@PathVariable Long taskId) {
    List<String> logs = trainingService.getTrainingLogs(taskId);
    return Map.of("code", 200, "data", logs);
}
```

---

### 4. 模型版本管理模块

#### 功能概述

管理 AI 模型的多版本迭代，支持模型激活/停用、下载部署、性能对比等功能。

#### 核心能力

**✅ 版本管理**
- 自动版本号：v1.0.0, v1.0.1, v1.1.0（语义化版本）
- 多格式支持：MindIR, ONNX, TFLite, TorchScript
- 元数据记录：训练任务关联、准确率、模型大小等
- 版本对比：横向对比多个版本的性能指标

**✅ 模型激活**
- 激活/停用：设置当前生产环境使用的模型
- 回滚机制：快速回退到上一个稳定版本
- 灰度发布：部分设备使用新模型（未来扩展）

**✅ 模型下载**
- 文件下载接口：边缘设备拉取模型文件
- 断点续传：支持大文件下载中断恢复
- 版本校验：MD5/SHA256 校验文件完整性

**✅ 性能监控**
- 推理延迟：记录模型在不同硬件上的推理时间
- 准确率跟踪：生产环境实际识别准确率
- 资源占用：CPU/内存/GPU 占用情况

#### API 示例

```java
// 获取所有模型版本
@GetMapping("/api/model/versions")
public Map<String, Object> getVersions(
    @RequestParam(required = false) String format,
    @RequestParam(defaultValue = "20") int limit) {
    List<ModelVersion> versions = modelService.listVersions(format, limit);
    return Map.of("code", 200, "data", versions);
}

// 激活模型
@PostMapping("/api/model/activate/{versionId}")
public Map<String, Object> activateModel(@PathVariable Long versionId) {
    modelService.activateModel(versionId);
    return Map.of("code", 200, "message", "模型已激活");
}

// 下载模型文件
@GetMapping("/api/model/download/{versionId}")
public ResponseEntity<Resource> downloadModel(@PathVariable Long versionId) {
    ModelVersion model = modelService.getVersion(versionId);
    File file = new File(model.getFilePath());
    Resource resource = new FileSystemResource(file);
    
    return ResponseEntity.ok()
        .header(HttpHeaders.CONTENT_DISPOSITION, 
                "attachment; filename=" + model.getFilename())
        .contentType(MediaType.APPLICATION_OCTET_STREAM)
        .body(resource);
}
```

---

### 5. 数据标注模块

#### 功能概述

为手势识别模型提供训练数据标注功能，支持时间段数据预览、快速标注、批量导出等。

#### 核心能力

**✅ 数据预览**
- 时间段查询：指定时间范围获取 EMG 数据
- 波形可视化：返回可绘制的数据格式
- 手势预测：显示当前模型的识别结果（辅助标注）

**✅ 标注保存**
- 批量标注：一次标注整个时间段的数据
- 标注者跟踪：记录标注人员信息
- 质量控制：重复标注检测、冲突解决

**✅ 统计与导出**
- 标注统计：各手势标注数量、标注人员工作量
- 数据集划分：自动划分训练集/验证集/测试集
- 格式导出：导出为 CSV、HDF5、TFRecord 等格式

#### API 示例

```java
// 获取缓存数据（预览）
@GetMapping("/api/annotation/cache-data")
public Map<String, Object> getCacheData(
    @RequestParam String deviceId,
    @RequestParam String startTime,
    @RequestParam String endTime) {
    
    Map<String, Object> data = annotationService.getCacheData(
        deviceId, 
        LocalDateTime.parse(startTime), 
        LocalDateTime.parse(endTime)
    );
    return Map.of("code", 200, "data", data);
}

// 保存标注
@PostMapping("/api/annotation/save")
public Map<String, Object> saveAnnotation(@RequestBody AnnotationRequest request) {
    Map<String, Object> result = annotationService.saveAnnotation(request);
    return Map.of(
        "code", 200,
        "message", "标注保存成功",
        "data", result  // { saved_count: 120, duplicate_count: 3 }
    );
}

// 标注统计
@GetMapping("/api/annotation/stats")
public Map<String, Object> getStats() {
    Map<String, Object> stats = annotationService.getAnnotationStats();
    return Map.of("code", 200, "data", stats);
}
```

---

## 📡 API 接口文档

### 0. 用户认证接口

**1. 用户注册**
- **端点**: `POST /auth/register`
- **请求体**: `{"username": "user1", "password": "123"}`
- **响应**: `{"message": "注册成功", "data": null}`

**2. 用户登录**
- **端点**: `POST /auth/login`
- **请求体**: `{"username": "user1", "password": "123"}`
- **响应**: `{"message": "登录成功", "data": "eyJhbGciOiJIUzI1Ni..."}` (data字段为Token)

### 1. EMG 数据接口

#### 1.1 批量上报 EMG 数据

**端点**: `POST /api/emg/batch`

**请求体**:
```json
{
  "deviceId": "orangepi_01",
  "frames": [
    {
      "deviceTs": 1709894400000,
      "emg": [[120,130,...], [121,131,...], ...],
      "acc": [0.05, 0.98, 0.15],
      "gyro": [0.02, -0.01, 0.03],
      "angle": [2.5, -1.2, 0.8],
      "gesture": "FIST",
      "confidence": 0.92,
      "battery": 85
    }
  ]
}
```

**响应**:
```json
{
  "code": 200,
  "msg": "ok",
  "received": 1
}
```

---

#### 1.2 获取最新数据

**端点**: `GET /api/emg/latest`

**响应**:
```json
{
  "deviceId": "orangepi_01",
  "deviceTs": 1709894400000,
  "serverTime": "2024-03-08T12:00:00",
  "emg": [[120,130,...], ...],
  "gesture": "FIST",
  "confidence": 0.92,
  "battery": 85
}
```

---

#### 1.3 查询历史数据

**端点**: `GET /api/emg/history?deviceId=orangepi_01&limit=100`

**参数**:
- `deviceId` (可选): 设备ID
- `limit` (可选, 默认100): 返回条数

**响应**:
```json
[
  {
    "id": 12345,
    "deviceId": "orangepi_01",
    "deviceTs": 1709894400000,
    "emgData": "[[120,130,...],...]",
    "gesture": "FIST",
    "createTime": "2024-03-08T12:00:00"
  }
]
```

---

#### 1.4 查询手势事件

**端点**: `GET /api/gesture/events?gesture=FIST&limit=50`

**参数**:
- `gesture` (可选): 手势类型筛选
- `limit` (可选, 默认50): 返回条数

**响应**:
```json
[
  {
    "id": 1001,
    "deviceId": "orangepi_01",
    "gesture": "FIST",
    "confidence": 0.95,
    "startTime": "2024-03-08T12:00:00",
    "endTime": "2024-03-08T12:00:02",
    "duration": 2.0
  }
]
```

---

#### 1.5 统计接口

**1. 上报使用数据**
- **端点**: `POST /api/stats/update?userId=1&count=1&tips=Test`
- **响应**: `Updated` (String)

**2. 获取今日统计**
- **端点**: `GET /api/stats/today?userId=1`
- **响应**:
```json
{
  "id": 1,
  "userId": 1,
  "statDate": "2024-03-18",
  "usageCount": 5,
  "comfortScore": 4.5,
  "adaptationStage": "初期"
}
```

**3. 获取近7天统计**
- **端点**: `GET /api/stats/last7days?userId=1`
- **响应**: `[{...}, {...}]`

---

### 2. 训练任务接口

#### 2.1 创建训练任务

**端点**: `POST /api/training/create`

**请求体**:
```json
{
  "taskName": "手势识别模型v2.0",
  "modelType": "CNN",
  "datasetPath": "/data/labeled/2024-03",
  "hyperparameters": {
    "learning_rate": 0.001,
    "batch_size": 64,
    "epochs": 100,
    "optimizer": "adam"
  },
  "useGpu": true
}
```

**响应**:
```json
{
  "code": 200,
  "message": "训练任务创建成功",
  "data": {
    "task_id": 42,
    "estimated_time_minutes": 30
  }
}
```

---

#### 2.2 查询任务状态

**端点**: `GET /api/training/task/{taskId}`

**响应**:
```json
{
  "code": 200,
  "data": {
    "task_id": 42,
    "task_name": "手势识别模型v2.0",
    "status": "running",
    "progress": 45,
    "current_epoch": 45,
    "total_epochs": 100,
    "train_accuracy": 0.92,
    "val_accuracy": 0.89,
    "train_loss": 0.25,
    "val_loss": 0.31,
    "estimated_remaining_seconds": 1200,
    "created_time": "2024-03-08T10:00:00",
    "start_time": "2024-03-08T10:05:00"
  }
}
```

---

#### 2.3 获取训练日志

**端点**: `GET /api/training/logs/{taskId}?tail=100`

**参数**:
- `tail` (可选, 默认100): 返回最后 N 行日志

**响应**:
```json
{
  "code": 200,
  "data": [
    "[2024-03-08 10:05:23] Epoch 1/100 - Loss: 1.234 - Acc: 0.456",
    "[2024-03-08 10:06:01] Epoch 2/100 - Loss: 0.987 - Acc: 0.567",
    "..."
  ]
}
```

---

#### 2.4 停止训练任务

**端点**: `POST /api/training/stop/{taskId}`

**响应**:
```json
{
  "code": 200,
  "message": "训练任务已停止"
}
```

---

### 3. 模型管理接口

#### 3.1 获取模型版本列表

**端点**: `GET /api/model/versions?format=onnx&limit=20`

**参数**:
- `format` (可选): 模型格式筛选 (onnx, mindir, tflite)
- `limit` (可选, 默认20): 返回条数

**响应**:
```json
{
  "code": 200,
  "data": [
    {
      "id": 5,
      "version": "v2.1.0",
      "modelFormat": "onnx",
      "accuracy": 96.8,
      "inferenceTimeMs": 8,
      "fileSizeMb": 12.5,
      "isActive": true,
      "trainingTaskId": 42,
      "createTime": "2024-03-08T15:30:00"
    }
  ]
}
```

---

#### 3.2 激活模型

**端点**: `POST /api/model/activate/{versionId}`

**响应**:
```json
{
  "code": 200,
  "message": "模型已激活"
}
```

---

#### 3.3 下载模型文件

**端点**: `GET /api/model/download/{versionId}`

**响应**: 二进制文件流（`application/octet-stream`）

**HTTP 头**:
```
Content-Disposition: attachment; filename="gesture_model_v2.1.0.onnx"
Content-Type: application/octet-stream
Content-Length: 13107200
```

---

#### 3.4 部署模型

**端点**: `POST /api/model/deploy`

**请求体**:
```json
{
  "version": "v2.1.0",
  "targetType": "edge",  // "cloud" | "edge" | "mobile"
  "targetDevice": "orangepi_01",
  "autoStart": true
}
```

**响应**:
```json
{
  "code": 200,
  "message": "模型部署成功"
}
```

---

### 4. 数据标注接口

#### 4.1 获取缓存数据

**端点**: `GET /api/annotation/cache-data?deviceId=orangepi_01&startTime=2024-03-08T12:00:00&endTime=2024-03-08T12:01:00`

**响应**:
```json
{
  "code": 200,
  "data": {
    "device_id": "orangepi_01",
    "frame_count": 60,
    "time_range": {
      "start": "2024-03-08T12:00:00",
      "end": "2024-03-08T12:01:00"
    },
    "frames": [
      {
        "timestamp": "2024-03-08T12:00:00.010",
        "emg": [[120,130,...], ...]
      }
    ]
  }
}
```

---

#### 4.2 保存标注

**端点**: `POST /api/annotation/save`

**请求体**:
```json
{
  "deviceId": "orangepi_01",
  "startTime": "2024-03-08T12:00:00",
  "endTime": "2024-03-08T12:01:00",
  "gestureLabel": "FIST",
  "annotator": "user001",
  "notes": "数据质量良好，动作标准"
}
```

**响应**:
```json
{
  "code": 200,
  "message": "标注保存成功",
  "data": {
    "saved_count": 60,
    "duplicate_count": 0,
    "label_id": 12345
  }
}
```

---

#### 4.3 标注统计

**端点**: `GET /api/annotation/stats`

**响应**:
```json
{
  "code": 200,
  "data": {
    "total_labels": 12450,
    "gesture_distribution": {
      "FIST": 2100,
      "OPEN": 2050,
      "PINCH": 1980,
      "OK": 2020,
      "YE": 2150,
      "SIDEGRIP": 2150
    },
    "annotators": {
      "user001": 5000,
      "user002": 7450
    },
    "date_range": {
      "earliest": "2024-03-01",
      "latest": "2024-03-08"
    }
  }
}
```

---

## 🗄️ 数据库设计

### 核心数据表

#### 1. emg_frames（EMG 数据帧表）

存储原始 EMG 数据流，是系统的核心数据表。

```sql
CREATE TABLE emg_frames (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    device_ts BIGINT NOT NULL COMMENT '设备时间戳（毫秒）',
    emg_data TEXT NOT NULL COMMENT 'EMG数据（JSON：10×8矩阵）',
    acc_x FLOAT COMMENT '加速度X轴',
    acc_y FLOAT COMMENT '加速度Y轴',
    acc_z FLOAT COMMENT '加速度Z轴',
    gyro_x FLOAT COMMENT '陀螺仪X轴',
    gyro_y FLOAT COMMENT '陀螺仪Y轴',
    gyro_z FLOAT COMMENT '陀螺仪Z轴',
    angle_roll FLOAT COMMENT '欧拉角Roll',
    angle_pitch FLOAT COMMENT '欧拉角Pitch',
    angle_yaw FLOAT COMMENT '欧拉角Yaw',
    gesture VARCHAR(20) COMMENT '识别手势',
    confidence FLOAT COMMENT '置信度',
    battery INT COMMENT '电池电量',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
    INDEX idx_device_time (device_id, device_ts),
    INDEX idx_create_time (create_time),
    INDEX idx_gesture (gesture)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='EMG原始数据帧';
```

**数据量级**: 约 1000 条/秒（1000Hz 采样率下）

---

#### 2. gesture_events（手势事件表）

存储识别到的手势事件，记录手势的开始/结束时间。

```sql
CREATE TABLE gesture_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    gesture VARCHAR(20) NOT NULL COMMENT '手势类型',
    confidence FLOAT COMMENT '平均置信度',
    start_time DATETIME NOT NULL COMMENT '手势开始时间',
    end_time DATETIME COMMENT '手势结束时间',
    duration FLOAT COMMENT '持续时长（秒）',
    frame_count INT COMMENT '帧数',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_device_gesture (device_id, gesture),
    INDEX idx_time (start_time, end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='手势事件记录';
```

**触发条件**: 当手势连续识别 > 0.5 秒时创建事件

---

#### 3. training_tasks（训练任务表）

管理模型训练任务的生命周期。

```sql
CREATE TABLE training_tasks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL COMMENT '任务名称',
    task_status VARCHAR(20) DEFAULT 'pending' COMMENT '状态',
    model_type VARCHAR(50) COMMENT '模型类型',
    dataset_path VARCHAR(255) COMMENT '数据集路径',
    hyperparameters TEXT COMMENT '超参数（JSON）',
    current_epoch INT COMMENT '当前轮次',
    total_epochs INT COMMENT '总轮次',
    progress_percent INT DEFAULT 0 COMMENT '进度百分比',
    train_accuracy FLOAT COMMENT '训练集准确率',
    val_accuracy FLOAT COMMENT '验证集准确率',
    final_train_loss FLOAT COMMENT '最终训练损失',
    final_val_loss FLOAT COMMENT '最终验证损失',
    duration_seconds INT COMMENT '耗时（秒）',
    log_path VARCHAR(255) COMMENT '日志文件路径',
    output_model_path VARCHAR(255) COMMENT '输出模型路径',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    start_time DATETIME COMMENT '开始时间',
    end_time DATETIME COMMENT '结束时间',
    INDEX idx_status (task_status),
    INDEX idx_create_time (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='训练任务';
```

---

#### 4. model_versions（模型版本表）

管理 AI 模型的多版本迭代。

```sql
CREATE TABLE model_versions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE COMMENT '版本号',
    model_format VARCHAR(20) NOT NULL COMMENT '模型格式',
    file_path VARCHAR(255) NOT NULL COMMENT '文件路径',
    file_size_mb FLOAT COMMENT '文件大小（MB）',
    accuracy FLOAT COMMENT '准确率',
    inference_time_ms INT COMMENT '推理耗时（毫秒）',
    training_task_id BIGINT COMMENT '关联训练任务',
    is_active TINYINT(1) DEFAULT 0 COMMENT '是否激活',
    description TEXT COMMENT '版本描述',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    deploy_time DATETIME COMMENT '部署时间',
    INDEX idx_version (version),
    INDEX idx_active (is_active),
    FOREIGN KEY (training_task_id) REFERENCES training_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型版本';
```

---

#### 5. emg_labeled_data（标注数据表）

存储人工标注的训练数据。

```sql
CREATE TABLE emg_labeled_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    emg_data TEXT NOT NULL COMMENT 'EMG数据（JSON）',
    label VARCHAR(20) NOT NULL COMMENT '手势标签',
    annotator VARCHAR(50) COMMENT '标注人员',
    annotation_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_quality INT COMMENT '数据质量评分（1-5）',
    notes TEXT COMMENT '备注',
    INDEX idx_label (label),
    INDEX idx_annotator (annotator)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标注数据';
```

---

### 索引优化策略

| 表 | 索引 | 用途 |
|------|------|------|
| `emg_frames` | `idx_device_time` | 按设备+时间查询历史数据 |
| `emg_frames` | `idx_create_time` | 数据清理（删除旧数据） |
| `gesture_events` | `idx_device_gesture` | 按设备+手势类型统计 |
| `training_tasks` | `idx_status` | 查询运行中的任务 |
| `model_versions` | `idx_active` | 快速查找激活模型 |

---

## ⚙️ 配置说明

### application.yml

```yaml
# ================================================================
# Spring Boot 配置 - EMG 数据后端
# ================================================================

server:
  port: 8080                # 服务端口
  tomcat:
    threads:
      max: 200              # 最大线程数
      min-spare: 10         # 最小空闲线程

spring:
  application:
    name: emg-backend

  # ============ 华为 RDS for MySQL 配置 ============
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://1.94.234.114:3306/ict_db?useUnicode=true&characterEncoding=UTF-8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true
    username: root
    password: xzhAa120119110
    type: com.alibaba.druid.pool.DruidDataSource
    
    # Druid 连接池配置
    druid:
      initial-size: 5       # 初始连接数
      min-idle: 5           # 最小空闲连接
      max-active: 20        # 最大活跃连接
      max-wait: 60000       # 最大等待时间（毫秒）
      test-on-borrow: false
      test-on-return: false
      test-while-idle: true
      validation-query: SELECT 1
      time-between-eviction-runs-millis: 60000
      min-evictable-idle-time-millis: 300000
      connection-properties: useSSL=false

# MyBatis Plus 配置
mybatis-plus:
  mapper-locations: classpath:mapper/*.xml
  type-aliases-package: com.huaweiict.emg.entity
  configuration:
    map-underscore-to-camel-case: true  # 驼峰命名转换
    log-impl: org.apache.ibatis.logging.stdout.StdOutImpl  # SQL 日志

# ============ 自定义配置 ============
emg:
  # 批量写入大小
  batch-insert-size: 50
  
  # 数据保留天数（自动清理）
  data-keep-days: 7
  
  # WebSocket 推送频率限制（毫秒）
  ws-push-interval-ms: 20
  
  # 模型存储路径
  model-storage-path: /data/models
  
  # 训练日志路径
  training-log-path: /var/log/emg-training

# ============ 日志配置 ============
logging:
  level:
    com.huaweiict.emg: INFO
    org.springframework.web.socket: DEBUG
  file:
    name: /var/log/emg-backend.log
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"
```

---

### CorsConfig.java（跨域配置）

```java
@Configuration
public class CorsConfig implements WebMvcConfigurer {
    
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOriginPatterns("*")  // 允许所有来源
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true)
                .maxAge(3600);
    }
}
```

---

### WebSocketConfig.java（WebSocket 配置）

```java
@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {
    
    @Autowired
    private EmgWebSocketHandler emgWebSocketHandler;
    
    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(emgWebSocketHandler, "/ws/emg", "/ws/app")
                .setAllowedOrigins("*");  // 允许所有来源连接
    }
}
```

---

## 🚀 部署运维

### 1. 本地开发环境

```bash
# 1. 克隆项目
git clone https://github.com/your-org/huawei-ict-emg.git
cd huawei-ict-emg/springboot_backend

# 2. 配置数据库
vim src/main/resources/application.yml
# 修改 spring.datasource.url/username/password

# 3. 启动服务
mvn spring-boot:run

# 或使用 IDE（推荐）
# - IntelliJ IDEA: 打开项目，运行 EmgBackendApplication.java
# - Eclipse: 导入 Maven 项目，运行 Main 类
```

---

### 2. 生产环境部署（华为云 ECS）

#### 2.1 环境准备

```bash
# 连接 ECS
ssh ubuntu@1.95.65.51

# 安装 JDK 11
sudo apt update
sudo apt install openjdk-11-jdk -y
java -version  # 验证安装
```

#### 2.2 打包部署

```bash
# 在本地打包
cd springboot_backend
mvn clean package -DskipTests

# 上传到服务器
scp target/emg-backend-1.0.0.jar ubuntu@1.95.65.51:~/

# 在服务器运行
ssh ubuntu@1.95.65.51
java -jar emg-backend-1.0.0.jar

# 后台运行
nohup java -jar emg-backend-1.0.0.jar > logs/app.log 2>&1 &
```

#### 2.3 systemd 守护进程

创建服务文件：

```bash
sudo vim /etc/systemd/system/emg-backend.service
```

内容：

```ini
[Unit]
Description=EMG Backend Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/bin/java -jar /home/ubuntu/emg-backend-1.0.0.jar
Restart=always
RestartSec=10
StandardOutput=append:/var/log/emg-backend.log
StandardError=append:/var/log/emg-backend-error.log

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable emg-backend
sudo systemctl start emg-backend
sudo systemctl status emg-backend

# 查看日志
sudo journalctl -u emg-backend -f
```

---

### 3. Docker 容器化部署（推荐）

#### 3.1 Dockerfile

```dockerfile
FROM openjdk:11-jre-slim

LABEL maintainer="emg-team@huawei.com"

WORKDIR /app

COPY target/emg-backend-1.0.0.jar app.jar

EXPOSE 8080

ENV JAVA_OPTS="-Xms256m -Xmx1024m"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
```

#### 3.2 docker-compose.yml

```yaml
version: '3.8'

services:
  emg-backend:
    build: .
    image: emg-backend:1.0.0
    container_name: emg-backend
    ports:
      - "8080:8080"
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://1.94.234.114:3306/ict_db
      SPRING_DATASOURCE_USERNAME: root
      SPRING_DATASOURCE_PASSWORD: xzhAa120119110
    volumes:
      - ./logs:/var/log
      - ./data:/data
    restart: always
    networks:
      - emg-network

networks:
  emg-network:
    driver: bridge
```

#### 3.3 部署命令

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

### 4. 监控与维护

#### 4.1 健康检查

```bash
# 检查服务状态
curl http://localhost:8080/api/emg/latest

# 检查数据库连接
curl http://localhost:8080/actuator/health
```

#### 4.2 日志管理

```bash
# 查看实时日志
tail -f /var/log/emg-backend.log

# 日志轮转配置
sudo vim /etc/logrotate.d/emg-backend
```

内容：

```
/var/log/emg-backend*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0640 ubuntu ubuntu
}
```

#### 4.3 性能监控

使用 Spring Boot Actuator + Prometheus + Grafana：

```xml
<!-- pom.xml 添加依赖 -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
  metrics:
    export:
      prometheus:
        enabled: true
```

---

## ⚡ 性能优化

### 1. 数据库优化

#### 1.1 批量写入

```java
@Service
public class EmgDataService {
    
    private List<EmgFrame> buffer = new CopyOnWriteArrayList<>();
    
    @Scheduled(fixedDelay = 1000)  // 每秒批量写入
    public void flushBuffer() {
        if (buffer.isEmpty()) return;
        
        List<EmgFrame> toInsert = new ArrayList<>(buffer);
        buffer.clear();
        
        emgFrameMapper.insertBatch(toInsert);
    }
}
```

#### 1.2 索引优化

```sql
-- 复合索引
CREATE INDEX idx_device_time ON emg_frames(device_id, device_ts);

-- 分析索引使用情况
EXPLAIN SELECT * FROM emg_frames 
WHERE device_id = 'orangepi_01' 
AND device_ts > 1709894400000;
```

#### 1.3 数据分区

```sql
-- 按月分区
ALTER TABLE emg_frames PARTITION BY RANGE (YEAR(create_time)*100 + MONTH(create_time)) (
    PARTITION p202401 VALUES LESS THAN (202402),
    PARTITION p202402 VALUES LESS THAN (202403),
    PARTITION p202403 VALUES LESS THAN (202404)
);
```

---

### 2. WebSocket 优化

#### 2.1 消息节流

```java
private long lastPushTime = 0;
private static final long PUSH_INTERVAL = 20; // 20ms

public void broadcastToApp(String message) {
    long now = System.currentTimeMillis();
    if (now - lastPushTime < PUSH_INTERVAL) {
        return;  // 跳过推送
    }
    lastPushTime = now;
    
    // 广播消息
    for (WebSocketSession session : appSessions.values()) {
        session.sendMessage(new TextMessage(message));
    }
}
```

#### 2.2 连接池管理

```java
@Configuration
public class WebSocketConfig {
    
    @Bean
    public ServletServerContainerFactoryBean createServletServerContainerFactoryBean() {
        ServletServerContainerFactoryBean container = new ServletServerContainerFactoryBean();
        container.setMaxTextMessageBufferSize(8192);
        container.setMaxBinaryMessageBufferSize(8192);
        container.setMaxSessionIdleTimeout(300000L);  // 5 分钟超时
        return container;
    }
}
```

---

### 3. JVM 调优

```bash
# 生产环境 JVM 参数
java -jar emg-backend-1.0.0.jar \
  -Xms512m \                  # 初始堆大小
  -Xmx1024m \                 # 最大堆大小
  -XX:+UseG1GC \              # 使用 G1 垃圾回收器
  -XX:MaxGCPauseMillis=200 \  # 最大 GC 停顿时间
  -XX:+HeapDumpOnOutOfMemoryError \
  -XX:HeapDumpPath=/var/log/heapdump.hprof
```

---

## 📚 相关文档

- 📖 [系统架构设计](ARCHITECTURE_DESIGN.md)
- 📖 [Training 页面 WebSocket 协议](TRAINING_PAGE_GUIDE.md)
- 📖 [WebSocket 完整应用指南](WEBSOCKET_APP_GUIDE.md)
- 📖 [模型部署指南](MODEL_DEPLOYMENT_GUIDE.md)
- 📖 [数据库 Schema](rds_mysql_schema.sql)

---

## 🤝 技术支持

- **GitHub Issues**: https://github.com/your-org/huawei-ict-emg/issues
- **邮件**: emg-support@huawei.com
- **文档**: https://docs.emg-project.com

---

**© 2024 华为 ICT 赛道 EMG 项目组**
