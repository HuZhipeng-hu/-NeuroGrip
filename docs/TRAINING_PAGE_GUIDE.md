# Training 页面 WebSocket 协议文档

## 概述

Training页面通过WebSocket与后端进行实时通信，实现手势训练数据的实时显示、手势选择、训练控制等功能。

**端点**: `ws://YOUR_SERVER_IP:8080/ws/app`

---

## 数据流向

```
┌─────────────────┐         WebSocket          ┌─────────────────┐
│   Training      │◄────────────────────────────│  Spring Boot    │
│   (HarmonyOS)   │                             │   Backend       │
│                 │─────────────────────────────►│                 │
└─────────────────┘      控制指令 & 实时数据      └─────────────────┘
        │                                               │
        │                                               │
        └───────────────────┐                           │
                            ▼                           ▼
                    【实时波形显示】              【记录训练状态】
                    【手势库管理】                【数据广播】
                    【训练控制】                  【多客户端同步】
```

---

## 消息协议

### 1. 客户端 → 服务端（App 发送的消息）

#### 1.1 请求最新数据

用于初始连接时获取最新的EMG数据帧。

```json
{
  "action": "get_latest"
}
```

**响应**: 服务端返回最新的EMG数据帧（格式见下文"服务端推送数据"）

---

#### 1.2 选择训练手势 ⭐ 新增

用户在"手势库"页面选择要训练的手势时发送。

```json
{
  "action": "select_gesture",
  "gesture": "握拳"
}
```

**字段说明**:
- `action`: 固定为 `"select_gesture"`
- `gesture`: 手势名称，可以是：
  - 预设手势: `"握拳"`, `"张开"`, `"捏取"`, `"侧握"`, `"伸展"`, `"放松"`
  - 自定义手势: 用户添加的任意名称

**服务端响应**:
```json
{
  "type": "gesture_selected",
  "gesture": "握拳",
  "timestamp": 1709894400000
}
```

**HarmonyOS 代码示例**:
```typescript
private sendGestureSelect(gesture: string): void {
  if (!this.ws) {
    console.warn('⚠️ WebSocket 未初始化');
    return;
  }
  
  const msg = {
    action: 'select_gesture',
    gesture: gesture
  };
  
  this.ws.send(JSON.stringify(msg), (err: BusinessError) => {
    if (err) {
      console.error('❌ 发送手势选择失败:', err.message);
    } else {
      console.info(`✅ 已发送手势选择: ${gesture}`);
    }
  });
}
```

---

#### 1.3 开始训练 ⭐ 新增（可选）

用户点击"开始训练"按钮时发送，用于记录训练状态。

```json
{
  "action": "start_training",
  "gesture": "握拳",
  "targetReps": 50,
  "sensitivity": 50
}
```

**字段说明**:
- `gesture`: 当前训练的手势
- `targetReps`: 目标训练次数（可选）
- `sensitivity`: 灵敏度设置（可选）

---

#### 1.4 停止训练 ⭐ 新增（可选）

用户点击"停止训练"按钮时发送。

```json
{
  "action": "stop_training"
}
```

---

### 2. 服务端 → 客户端（后端推送的消息）

#### 2.1 实时 EMG 数据帧

后端持续推送最新的EMG数据，前端接收后更新波形图。

```json
{
  "deviceId": "EMG_WIN_001",
  "deviceTs": 1709894400000,
  "serverTime": "2024-03-08T12:00:00.000",
  "gesture": "FIST",
  "confidence": 0.92,
  "battery": 85,
  "emg": [
    [120, 130, 125, 118, 122, 128, 115, 119],  // 第1包（最旧）
    [121, 131, 126, 119, 123, 129, 116, 120],  // 第2包
    [122, 132, 127, 120, 124, 130, 117, 121],  // ...
    [123, 133, 128, 121, 125, 131, 118, 122],
    [124, 134, 129, 122, 126, 132, 119, 123],
    [125, 135, 130, 123, 127, 133, 120, 124],
    [126, 136, 131, 124, 128, 134, 121, 125],
    [127, 137, 132, 125, 129, 135, 122, 126],
    [128, 138, 133, 126, 130, 136, 123, 127],
    [129, 139, 134, 127, 131, 137, 124, 128]   // 第10包（最新）
  ],
  "acc": [0.05, 0.98, 0.15],
  "gyro": [0.02, -0.01, 0.03],
  "angle": [2.5, -1.2, 0.8]
}
```

**字段说明**:
- `emg`: 10包 × 8通道的EMG数据矩阵
  - 每包代表1毫秒的8个通道数据
  - 数值范围: 0-255（原始ADC值）
  - **最后一包（`emg[9]`）是最新数据**
- `gesture`: 当前识别到的手势（由AI模型推理）
- `confidence`: 手势识别置信度（0.0-1.0）
- `battery`: 电池电量百分比

**HarmonyOS 处理示例**:
```typescript
this.ws.on('message', (err: BusinessError, data: string | ArrayBuffer) => {
  if (err) {
    console.error('❌ message error:', err.message);
    return;
  }

  let msg: string = '';
  if (typeof data === 'string') {
    msg = data;
  } else if (data instanceof ArrayBuffer) {
    const uint8Array = new Uint8Array(data);
    msg = String.fromCharCode(...uint8Array);
  }

  const jsonData = JSON.parse(msg);

  // ✅ 提取最新一包EMG数据（用于波形绘制）
  const latestEmgPacket: number[] = jsonData.emg.length > 0
    ? jsonData.emg[jsonData.emg.length - 1]  // 取最后一包
    : new Array(8).fill(0);

  // 更新波形（8个通道）
  this.updateWaveforms(latestEmgPacket);

  // 更新手势显示
  this.currentGesture = jsonData.gesture || 'RELAX';
  this.confidence = jsonData.confidence || 0;
  this.battery = jsonData.battery || 0;
});
```

---

#### 2.2 手势选择确认 ⭐ 新增

服务端收到 `select_gesture` 请求后的确认响应。

```json
{
  "type": "gesture_selected",
  "gesture": "握拳",
  "timestamp": 1709894400000
}
```

---

## Training 页面功能详解

### 1. 手势库管理

#### 1.1 预设手势

系统内置6种预设手势：

| 手势名称 | 英文标识 | 应用场景 |
|---------|---------|---------|
| 握拳 | FIST | 抓取物体 |
| 张开 | OPEN | 释放物体 |
| 捏取 | PINCH | 精细操作 |
| 侧握 | SIDEGRIP | 握住工具 |
| 伸展 | EXTEND | 展开动作 |
| 放松 | RELAX | 待机状态 |

#### 1.2 自定义手势

用户可以添加、编辑、删除自定义手势：

**数据结构**（前端本地管理）:
```typescript
@State customGestures: string[] = ['手势A', '手势B'];
```

**操作流程**:
1. 点击"+ 新增"按钮
2. 输入手势名称
3. 点击"确认添加"
4. 自动选中新手势并发送 `select_gesture` 消息

**改名流程**:
1. 点击手势的"改名"按钮
2. 修改名称
3. 点击"✓"确认
4. 如果该手势正在被选中，重新发送 `select_gesture`

**删除流程**:
1. 点击"删除"按钮
2. 确认删除
3. 如果删除的是当前选中手势，自动切换到"握拳"

---

### 2. 训练控制

#### 2.1 训练状态机

```
┌──────────────┐   开始训练   ┌──────────────┐
│ NOT_STARTED  │──────────────►│ IN_PROGRESS  │
│   未开始     │              │   训练中      │
└──────────────┘              └───────┬───────┘
      ▲                              │
      │                              │ 暂停
      │ 结束训练                      ▼
      │                       ┌──────────────┐
      │                       │   PAUSED     │
      │                       │   已暂停     │
      │                       └───────┬───────┘
      │                              │
      │                              │ 继续
      │                              ▼
      │                       ┌──────────────┐
      └───────────────────────│  COMPLETED   │
                             │   已完成     │
                             └──────────────┘
```

#### 2.2 训练参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `targetReps` | number | 50 | 目标训练次数 |
| `completedReps` | number | 0 | 已完成次数 |
| `progress` | number | 0-100 | 训练进度百分比 |
| `sensitivity` | number | 0-100 | 灵敏度（影响波形显示缩放） |
| `formattedTime` | string | "00:00" | 训练计时（MM:SS格式） |

#### 2.3 训练建议

根据进度动态显示：
- **0-30%**: "刚开始，请保持节奏，注意动作的准确性。"
- **30-70%**: "表现不错！肌电信号稳定，继续保持当前强度。"
- **70-100%**: "即将完成目标！注意调整呼吸，避免肌肉过早疲劳。"

---

### 3. 实时波形显示

#### 3.1 波形缓冲区设计

```typescript
// 8个通道 × 100个采样点
@State waveformData: number[][] = (() => {
  const data: number[][] = [];
  for (let i = 0; i < 8; i++) {
    data.push(new Array(100).fill(50));  // 初始化为中线值
  }
  return data;
})();

private writeIndex: number = 0;  // 循环写入索引
```

**循环缓冲机制**:
- 不使用 `shift()` + `push()`（性能差）
- 使用固定索引循环写入
- 绘图时按正确顺序读取

#### 3.2 数据更新流程

```typescript
private updateWaveforms(newValues: number[]): void {
  if (newValues.length !== 8) return;

  const BASELINE = 127;            // EMG数据中线值
  const scale = this.sensitivity / 10;  // 灵敏度缩放

  for (let i = 0; i < 8; i++) {
    const raw = newValues[i];      // 原始值 0-255
    const delta = raw - BASELINE;  // 相对于中线的偏移
    let scaled = 50 + delta * scale;  // 转换为0-100范围
    scaled = Math.max(10, Math.min(90, scaled)); // 限制范围

    // 循环写入
    this.waveformData[i][this.writeIndex] = scaled;
  }

  this.writeIndex = (this.writeIndex + 1) % 100;
  this.drawWaveform();
}
```

#### 3.3 Canvas 绘制优化

**节流绘制**:
```typescript
private lastDrawTime: number = 0;
private drawInterval: number = 50;  // 每50ms绘制一次

private drawWaveform(): void {
  const now = Date.now();
  if (now - this.lastDrawTime < this.drawInterval) return;
  this.lastDrawTime = now;
  
  // 绘制逻辑...
}
```

**8通道颜色**:
```typescript
const colors: string[] = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444',
  '#8B5CF6', '#EC4899', '#06B6D4', '#F97316'
];
```

---

## 后端实现要点

### 1. WebSocket 处理器更新

**文件**: `EmgWebSocketHandler.java`

**新增功能**:
1. ✅ 存储每个App会话选择的手势
2. ✅ 处理 `select_gesture` 动作
3. ✅ 发送手势选择确认消息
4. ✅ 支持 `start_training` 和 `stop_training`（可选）
5. ✅ 连接断开时清理手势选择信息

**关键代码**:
```java
/** App 客户端当前选择的训练手势 (sessionId → gesture) */
private final Map<String, String> selectedGestures = new ConcurrentHashMap<>();

private void handleAppMessage(WebSocketSession session, String payload) {
    JSONObject json = JSON.parseObject(payload);
    String action = json.getString("action");

    if ("select_gesture".equals(action)) {
        String gesture = json.getString("gesture");
        String sessionId = session.getId();
        selectedGestures.put(sessionId, gesture);
        log.info("[WS] App [{}] 选择手势: {}", sessionId, gesture);
        
        // 发送确认
        JSONObject ack = new JSONObject();
        ack.put("type", "gesture_selected");
        ack.put("gesture", gesture);
        ack.put("timestamp", System.currentTimeMillis());
        session.sendMessage(new TextMessage(ack.toJSONString()));
    }
}
```

### 2. 未来扩展：训练数据自动标注

**概念**:
当用户选择手势并开始训练时，可以自动将收到的EMG数据标注为该手势，存入数据库。

**伪代码**:
```java
if ("start_training".equals(action)) {
    String gesture = selectedGestures.get(sessionId);
    // 启用自动标注模式
    enableAutoLabeling(sessionId, gesture);
}

// 在 processFrame() 中
if (isAutoLabelingEnabled(sessionId)) {
    String gesture = getTrainingGesture(sessionId);
    saveToDatabase(emgData, gesture);
}
```

---

## 测试方法

### 1. WebSocket 功能测试

使用 Python 测试选择手势功能：

```python
import asyncio
import websockets
import json

async def test_training():
    uri = "ws://1.95.65.51:8080/ws/app"
    
    async with websockets.connect(uri) as ws:
        print("✅ WebSocket 已连接")
        
        # 1. 选择手势
        select_msg = {
            "action": "select_gesture",
            "gesture": "握拳"
        }
        await ws.send(json.dumps(select_msg))
        print("📤 已发送手势选择")
        
        # 2. 接收确认消息
        response = await ws.recv()
        data = json.loads(response)
        print(f"📥 收到响应: {data}")
        
        # 3. 持续接收EMG数据
        async for message in ws:
            emg_data = json.loads(message)
            if 'emg' in emg_data:
                latest_packet = emg_data['emg'][-1]
                print(f"EMG: {latest_packet[:4]}... | 手势: {emg_data['gesture']}")

asyncio.run(test_training())
```

### 2. 前端集成测试

在 HarmonyOS App 中：

1. **连接测试**: 启动App，观察日志是否显示 "✅ WebSocket connected"
2. **手势选择测试**: 点击不同手势，观察后端日志是否记录
3. **波形显示测试**: 观察8条波形是否实时更新
4. **训练控制测试**: 测试开始/暂停/继续/结束按钮
5. **自定义手势测试**: 添加、改名、删除自定义手势

---

## 常见问题

### Q1: 波形显示不流畅怎么办？

**原因**: 更新频率过高，导致UI重绘过于频繁

**解决**:
1. 降低波形更新频率（例如每10帧更新一次）
2. 使用节流机制（`drawInterval = 50ms`）
3. 检查灵敏度设置是否过高

### Q2: 手势选择后波形没有变化？

**原因**: 前端只更新了UI显示的手势名称，波形数据来自后端推送

**说明**: 这是正常的。手势选择是用于标记"我正在训练这个手势"，不影响实时推送的EMG数据和AI识别结果。

### Q3: 如何实现训练数据自动保存？

**方案**:
1. 前端在开始训练时发送 `start_training` 消息
2. 后端记录训练状态和选择的手势
3. 后端在接收到EMG数据时自动标注并保存
4. 训练结束时发送 `stop_training` 停止自动标注

**参考**: [标注页面实现](ANNOTATION_PAGE_GUIDE.md)

---

## 相关文档

- [WebSocket `/ws/app` 完整指南](WEBSOCKET_APP_GUIDE.md)
- [标注页面指南](ANNOTATION_PAGE_GUIDE.md)
- [系统架构设计](ARCHITECTURE_DESIGN.md)
- [模型训练流程](MODEL_DEPLOYMENT_GUIDE.md)

---

## 更新日志

- **2024-03-11**: 初始版本，支持手势选择、训练控制、实时波形显示
- **2024-03-11**: 后端增加 `select_gesture` 动作处理
- **2024-03-11**: 添加自定义手势管理功能说明

---

**© 2024  赛道 EMG 项目组**

