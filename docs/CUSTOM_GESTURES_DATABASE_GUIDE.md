# 自定义手势持久化实现指南

## 📋 功能概述

用户可以在App中创建自定义手势，自定义手势会自动保存到用户设备端的本地存储，**同时也会上传到服务器数据库**中，实现数据的云端持久化。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    HarmonyOS App                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │  AnnotationPage.ets                                      │ │
│ │  - deviceId: 用户标识符                                   │ │
│ │  - customGestures: 本地列表                              │ │
│ │  - uploadCustomGestureToServer(): 上传到服务器           │ │
│ │  - loadCustomGestures(): 从本地加载                      │ │
│ └───────────────────────┬──────────────────────────────────┘ │
└───────────────────────┼──────────────────────────────────────┘
                        │ HTTP API
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Spring Boot Backend                              │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ AnnotationController.java                               │ │
│ │ - POST   /api/annotation/custom-gestures                │ │
│ │ - GET    /api/annotation/custom-gestures                │ │
│ │ - DELETE /api/annotation/custom-gestures                │ │
│ └───────────────────────┬──────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ CustomGestureService.java                               │ │
│ │ - saveCustomGesture()                                   │ │
│ │ - getActiveCustomGestures()                             │ │
│ │ - deleteCustomGesture()                                 │ │
│ │ - incrementUseCount()                                   │ │
│ └───────────────────────┬──────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ CustomGestureRepository.java (JPA)                       │ │
│ └───────────────────────┬──────────────────────────────────┘ │
└───────────────────────┼──────────────────────────────────────┘
                        │ JDBC
                        ▼
┌─────────────────────────────────────────────────────────────┐
│            MySQL Database (华为云RDS)                        │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ app_user                  custom_gesture                 │ │
│ ├────────────────────────┬──────────────────────────────────┤ │
│ │ id                     │ id                               │ │
│ │ device_id (UK)         │ device_id (FK)                   │ │
│ │ user_name              │ gesture_id (UK)                  │ │
│ │ created_at             │ gesture_label                    │ │
│ │                        │ gesture_icon                     │ │
│ │                        │ use_count                        │ │
│ │                        │ is_active                        │ │
│ │                        │ created_at                       │ │
│ └────────────────────────┴──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 部署步骤

### 步骤1：数据库迁移

在华为云RDS MySQL中执行以下SQL脚本：

```bash
# 连接到数据库
mysql -h <RDS_HOST> -u <USERNAME> -p<PASSWORD>

# 执行迁移脚本
source docs/add_custom_gestures_table.sql
```

或者在华为云RDS控制台SQL编辑器中粘贴脚本内容执行。

**创建的表：**
- `app_user`: 用户表
- `custom_gesture`: 自定义手势表

### 步骤2：后端编译和打包

```bash
cd springboot_backend

# 编译
mvn clean package

# 结果
# target/emg-backend-1.0.0.jar
```

### 步骤3：部署到华为云ECS

```bash
# 上传JAR文件到ECS
scp target/emg-backend-1.0.0.jar root@<ECS_IP>:/home/springboot/

# SSH连接到ECS
ssh root@<ECS_IP>

# 在ECS上运行
cd /home/springboot
nohup java -jar emg-backend-1.0.0.jar &
```

### 步骤4：前端编译

```bash
cd app

# 构建HarmonyOS应用
hvigor build
```

## 📱 前端使用流程

### 1. 添加自定义手势

```
用户点击"+"按钮 
  ↓
对话框弹出，要求输入：
  - 手势名称（如："胜利"）
  - 手势图标（从24个emoji中选择）
  ↓
用户填写信息并点击"添加手势"
  ↓
前端执行：
  1. 生成手势ID（slug格式：victory_peace）
  2. 保存到本地AppStorage
  3. 调用API上传到服务器
  ↓
后端执行：
  1. 验证参数
  2. 检查重复（唯一键：device_id + gesture_id）
  3. 保存到MySQL
  4. 返回成功响应
  ↓
手势出现在"可选手势"列表中
```

### 2. 使用自定义手势进行标注

```
用户选择自定义手势
  ↓
点击"开始录制"
  ↓
手臂动作被捕捉
  ↓
点击"停止录制"
  ↓
数据标注为该自定义手势
  ↓
上传到服务器
```

### 3. 删除自定义手势

```
用户点击手势旁的"X"按钮
  ↓
前端执行：
  1. 从本地AppStorage删除
  2. 调用DELETE API删除服务器记录
  ↓
后端执行：
  1. 软删除（is_active = FALSE）
  2. 保留历史数据
  ↓
手势从列表中消失
```

## 🔌 API 接口规范

### 1. 保存自定义手势

**请求**

```http
POST /api/annotation/custom-gestures
Content-Type: application/json

{
  "deviceId": "emg_device_abc123",
  "gestureId": "victory_peace",
  "gestureLabel": "胜利",
  "gestureIcon": "✌️"
}
```

**响应成功（200）**

```json
{
  "code": 200,
  "message": "自定义手势保存成功",
  "data": {
    "id": 1,
    "deviceId": "emg_device_abc123",
    "gestureId": "victory_peace",
    "gestureLabel": "胜利",
    "gestureIcon": "✌️",
    "useCount": 0,
    "isActive": true,
    "createdAt": "2026-03-18T10:30:00"
  }
}
```

**参数说明**

| 参数 | 类型 | 说明 | 例子 |
|------|------|------|------|
| deviceId | String | 用户设备ID（App生成，唯一标识用户） | `emg_device_abc123` |
| gestureId | String | 手势ID（slug格式） | `victory_peace` |
| gestureLabel | String | 手势显示名称 | `胜利` |
| gestureIcon | String | emoji图标 | `✌️` |

### 2. 查询用户的自定义手势

**请求**

```http
GET /api/annotation/custom-gestures?deviceId=emg_device_abc123
```

**响应成功（200）**

```json
{
  "code": 200,
  "message": "查询成功",
  "data": [
    {
      "id": 1,
      "deviceId": "emg_device_abc123",
      "gestureId": "victory_peace",
      "gestureLabel": "胜利",
      "gestureIcon": "✌️",
      "useCount": 5,
      "isActive": true,
      "createdAt": "2026-03-18T10:30:00"
    },
    {
      "id": 2,
      "deviceId": "emg_device_abc123",
      "gestureId": "rock_hand",
      "gestureLabel": "摇滚",
      "gestureIcon": "🤟",
      "useCount": 2,
      "isActive": true,
      "createdAt": "2026-03-18T11:00:00"
    }
  ]
}
```

### 3. 删除自定义手势

**请求**

```http
DELETE /api/annotation/custom-gestures?deviceId=emg_device_abc123&gestureId=victory_peace
```

**响应成功（200）**

```json
{
  "code": 200,
  "message": "自定义手势删除成功"
}
```

## 💾 数据存储说明

### 本地存储（App）

**AppStorage Key**: `custom_gestures`

**存储格式**

```json
[
  {
    "gesture": "victory_peace",
    "label": "胜利",
    "icon": "✌️",
    "count": 0
  },
  {
    "gesture": "rock_hand",
    "label": "摇滚",
    "icon": "🤟",
    "count": 0
  }
]
```

### 服务器存储（MySQL）

**表**: `custom_gesture`

```sql
CREATE TABLE custom_gesture (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    device_id VARCHAR(64) NOT NULL,
    gesture_id VARCHAR(64) NOT NULL,
    gesture_label VARCHAR(100) NOT NULL,
    gesture_icon VARCHAR(10) NOT NULL,
    use_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    UNIQUE KEY uk_device_gesture (device_id, gesture_id),
    INDEX idx_device_id (device_id)
);
```

## 🔀 数据同步机制

### 场景1：首次使用App

1. App生成随机deviceId（如：`emg_device_abc123`）
2. 用户创建自定义手势
3. **前端**：保存到本地AppStorage
4. **后端**：上传到服务器MySQL
5. 用户可在其他设备通过deviceId同步数据（需要额外实现）

### 场景2：App重启

1. App读取本地AppStorage中的`custom_gestures`
2. 恢复之前创建的所有手势
3. 可选：调用GET /api/annotation/custom-gestures同步服务器记录

### 场景3：手势冲突处理

如果用户在多个设备创建相同名称的手势：

- **设备端**：保存为本地独立的手势
- **服务器端**：通过`device_id + gesture_id`的唯一键区分
- **建议**：添加deviceId标识符到UI中，让用户清楚知道数据范围

## 🧪 测试指南

### 单元测试

```bash
# 测试自定义手势Service
cd springboot_backend
mvn test -Dtest=CustomGestureServiceTest
```

### 集成测试

使用Postman或curl测试API：

```bash
# 1. 添加手势
curl -X POST http://localhost:8080/api/annotation/custom-gestures \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "test_device_001",
    "gestureId": "peace",
    "gestureLabel": "Peace",
    "gestureIcon": "✌️"
  }'

# 2. 查询手势
curl http://localhost:8080/api/annotation/custom-gestures?deviceId=test_device_001

# 3. 删除手势
curl -X DELETE http://localhost:8080/api/annotation/custom-gestures?deviceId=test_device_001&gestureId=peace
```

### 端到端测试

1. 在App中添加自定义手势
2. 检查服务器日志确认API被调用
3. 查询数据库确认数据已保存
4. 验证手势可用于标注
5. 验证删除功能正常工作

## ⚙️ 配置说明

### 前端配置

**AnnotationPage.ets**

```typescript
// 设备ID生成（可自定义）
@State deviceId: string = 'emg_device_' + Math.random().toString(36).substring(7);

// 服务器地址
const SERVER_URL: string = 'http://1.95.65.51:8080';
```

### 后端配置

**application.yml** (需要添加)

```yaml
spring:
  jpa:
    hibernate:
      ddl-auto: update  # 自动创建表
    show-sql: false
    properties:
      hibernate:
        jdbc:
          batch_size: 20
        order_inserts: true
```

### 数据库连接配置

确保Spring Boot应用能连接到华为云RDS MySQL：

```yaml
spring:
  datasource:
    url: jdbc:mysql://<RDS_HOST>:3306/emg_db
    username: <USERNAME>
    password: <PASSWORD>
    driver-class-name: com.mysql.cj.jdbc.Driver
```

## 🐛 故障排查

### 问题1：前端上传失败

**症状**: 创建手势后，App显示"保存成功"但后端日志无请求

**解决**:
1. 检查`SERVER_URL`是否正确
2. 检查网络连接（Wi-Fi/4G）
3. 查看浏览器控制台错误
4. 确保后端服务运行

### 问题2：数据库连接失败

**症状**: 后端日志显示`SQLException: Connection refused`

**解决**:
1. 检查RDS实例是否运行
2. 验证安全组规则允许3306端口
3. 检查数据库用户密码
4. 测试ECS到RDS的网络连接

### 问题3：自定义手势未出现在列表

**症状**: 添加手势后未在UI中显示

**解决**:
1. 检查AppStorage是否成功保存
2. 验证App重启后是否加载
3. 检查浏览器F12控制台的`custom_gestures`键值
4. 清除本地数据并重新添加

## 📊 监控和维护

### 数据库查询

```sql
-- 查看某用户的所有手势
SELECT * FROM custom_gesture 
WHERE device_id = 'emg_device_abc123' AND is_active = TRUE;

-- 查看所有用户的手势统计
SELECT device_id, COUNT(*) as gesture_count, SUM(use_count) as total_uses
FROM custom_gesture 
WHERE is_active = TRUE
GROUP BY device_id;

-- 查看最常使用的手势
SELECT gesture_id, gesture_label, SUM(use_count) as total_uses
FROM custom_gesture 
WHERE is_active = TRUE
GROUP BY gesture_id
ORDER BY total_uses DESC;

-- 检查删除的手势（软删除）
SELECT * FROM custom_gesture 
WHERE device_id = 'emg_device_abc123' AND is_active = FALSE;
```

### 日志监控

```bash
# 查看后端日志
tail -f /home/springboot/nohup.out | grep "custom_gesture"

# 查看特定用户的操作
tail -f nohup.out | grep "设备=emg_device_abc123"
```

## 📚 相关文件

- 前端: `app/entry/src/main/ets/pages/AnnotationPage.ets`
- 后端控制器: `springboot_backend/src/main/java/com/huaweiict/emg/controller/AnnotationController.java`
- 后端服务: `springboot_backend/src/main/java/com/huaweiict/emg/service/CustomGestureService.java`
- 数据访问: `springboot_backend/src/main/java/com/huaweiict/emg/repository/CustomGestureRepository.java`
- 数据模型: `springboot_backend/src/main/java/com/huaweiict/emg/model/CustomGesture.java`
- 数据库迁移: `docs/add_custom_gestures_table.sql`

## 📝 更新日志

### v1.0.0 (2026-03-18)

- ✅ 实现自定义手势本地存储（AppStorage）
- ✅ 实现自定义手势服务器存储（MySQL）
- ✅ 添加三个API端点（创建、查询、删除）
- ✅ 实现CustomGestureService业务逻辑
- ✅ 创建数据库迁移脚本
- ✅ 编写完整的使用指南

## 🔄 后续改进计划

- [ ] 实现多设备间手势同步
- [ ] 添加手势导入/导出功能
- [ ] 添加手势云备份
- [ ] 实现手势排序和分类
- [ ] 添加手势使用统计和分析
- [ ] 实现手势模板库共享

---

**文档更新时间**: 2026-03-18  
**维护者**: EMG识别系统开发团队
