# NeuroGrip Pro - 智能仿生机械臂控制 App (HarmonyOS)

## 📖 项目简介
本项目是 **NeuroGrip Pro** 智能仿生机械臂的前端控制应用，基于 **HarmonyOS (OpenHarmony)** 开发。
应用旨在为截肢用户提供“以用户为中心的智能交互体验”，通过直观的数据可视化、实时肌电信号反馈和个性化训练引导，实现高效、自然的义肢操控与康复训练管理。

本应用涵盖了设备连接、手势训练、数据分析、定位追踪及个性化设置等核心功能，配合后端服务（Spring Boot + Huawei Cloud）实现全链路智能交互。

## 🛠 技术栈
- **开发环境**: DevEco Studio 5.0.5+
- **SDK 版本**: HarmonyOS SDK API 10+ (Stage 模型)
- **编程语言**: ArkTS (TypeScript 扩展)
- **UI 框架**: ArkUI (声明式开发)
- **图表实现**: 基于 ArkUI Canvas 与基础组件自定义实现

## 📂 目录结构
```
app/
├── AppScope/           # 应用全局配置与资源
├── entry/              # 核心功能模块 (HAP)
│   ├── src/main/ets/
│   │   ├── common/     # 公共工具类与常量
│   │   ├── models/     # 数据模型定义
│   │   ├── pages/      # 页面视图 (Index, Training, Data, etc.)
│   │   └── services/   # 业务逻辑服务
│   └── src/main/resources # 资源文件 (多语言, 媒体资源)
├── oh_modules/         # 第三方依赖库
└── hvigor/             # 构建工具配置
```

## ✨ 功能模块

### 1. 首页 (Home)
- **状态概览**: 展示仿生机械臂的实时连接状态、电量及信号强度。
- **快捷入口**: 快速访问设备管理与训练建议。

### 2. 训练 (Training)
- **肌电模拟**: 实时显示肌电信号(EMG)波形图，直观反馈肌肉发力状态。
- **手势库**: 支持多种手势（RELAX, FIST, PINCH 等）的专项训练。
- **参数调节**: 支持灵敏度与阈值调节，适应不同用户的肌肉信号特征。

### 3. 数据分析 (Data)
- **趋势统计**: 展示每日/每周抓握次数与训练时长。
- **可视化图表**: 内置自定义柱状图与进度环，直观呈现康复进度。

### 4. 个人中心 (Profile)
- **用户档案**: 个人资料管理与使用时长统计。
- **设备管理**: 查看设备详细信息。

### 5. 定位追踪 (Location)
- **地图服务**: (UI已就绪) 显示义肢最后一次连接的地理位置，防止设备丢失。

### 6. 设置 (Settings)
- **偏好配置**: 自定义手势映射、数据同步频率等。
- **系统功能**: 账号登出、检查更新与帮助支持。

## 🚀 快速开始

1. **环境准备**:
   - 安装 [DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio/) (建议版本 5.0+)。
   - 下载并安装 OpenHarmony SDK (API 10)。

2. **导入项目**:
   - 打开 DevEco Studio，选择 `Open Project`。
   - 导航至 `HUAWEI_ICT/app` 目录并打开。

3. **同步依赖**:
   - 等待 `ohpm` 自动同步依赖，或在终端运行 `ohpm install`。

4. **运行调试**:
   - 连接 HarmonyOS真机或启动本地模拟器。
   - 点击顶部工具栏 `Run 'entry'` 按钮。

## 🔗 后端集成 (规划中)
复赛阶段将接入以下服务实现数据云端同步：
- **Websocket**: 实现毫秒级肌电数据传输。
- **Spring Boot**: 用户账户体系与训练数据持久化。
- **Huawei Cloud IoTDA**: 设备接入与消息透传。
- **GaussDB**: 康复数据存储。

## 📄 页面概览
| 页面 | 说明 |
|------|------|
| `Index.ets` | 应用入口，主 Tab 导航容器 |
| `HomePage.ets` | 首页仪表盘 |
| `Training.ets` | 训练与波形显示 |
| `Data.ets` | 统计图表 |
| `Location.ets` | 地图定位页面 |
| `Settings.ets` | 系统设置 |
