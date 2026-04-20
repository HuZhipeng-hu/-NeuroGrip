# 智能义肢控制系统技术方案

> 面向 大赛项目的技术方案、系统实现与测试分析

## 一、技术方案

### 1. 目标与约束
- 低延迟识别：手势识别与控制链路尽量在边缘侧完成，保证实时性。
- 端云协同：边缘完成采集与推理，云端完成管理、训练与模型版本控制。
- 可训练闭环：支持 App 发起标注与训练，持续优化识别效果。
- 可部署性：模型支持边缘与云端两种部署模式，便于扩展与容灾。

### 2. 总体架构
系统采用“边缘采集 + 云端服务 + App 交互”的三层架构：

- 感知层（Edge）：KunpengPro 连接 EMG 臂环采集 8 通道 EMG 与 IMU 数据，支持本地推理。
- 服务层（Cloud）：Spring Boot 后端提供 WebSocket 数据转发、标注管理、训练任务与模型管理。
- 应用层（User）：HarmonyOS App 展示实时波形、进行数据标注、训练管理与模型切换。

数据流转路径：
1) EMG 臂环 → KunpengPro（采集）
2) KunpengPro → Spring Boot（WebSocket）
3) Spring Boot → App（实时广播）
4) App 发起标注/训练 → Spring Boot → Python 训练服务
5) 训练完成 → 模型版本管理 → 部署到 KunpengPro/云端

### 3. 技术选型
- 边缘端：Python 3.9 + EMG 采集驱动 + MindSpore Lite/ONNX Runtime（推理）
- 后端：Java Spring Boot + WebSocket + MySQL（RDS）
- App：HarmonyOS（ArkTS）
- 训练：Python + 深度学习框架（CNN/RNN 结构）
- 部署：混合部署（边缘主推理 + 云端备用）

### 4. 模型与数据策略
- 采用滑动窗口对 EMG 序列进行分段，统一输入维度。
- 基于 CNN/RNN 结构进行特征抽取与时序建模。
- App 控制“是否保存到数据库”，避免无效数据污染训练集。
- 引入模型版本管理与回滚机制，保证稳定性。

---

## 二、系统实现

### 1. 边缘端实现（KunpengPro）
- 采集：通过串口读取 EMG 与 IMU 数据。
- 推理：本地加载模型（如 ONNX），在滑动窗口内执行推理。
- 传输：通过 WebSocket 将数据与推理结果上传后端。

关键脚本：
- 采集与推理：`code/scripts/KunpengPro_client.py`
- 臂环驱动：`code/scripts/emg_armband.py`

### 2. 后端实现（Spring Boot）
- WebSocket Hub：接收 KunpengPro 数据并广播给 App。
- 数据缓存：默认不落库，缓存 10 分钟供 App 选择性保存。
- 标注服务：App 发起标注请求，按时间段保存数据到 `emg_labeled_data`。
- 训练服务：创建训练任务、导出数据、调用 Python 训练脚本并写回结果。
- 模型管理：模型版本化、激活/回滚、下载与部署。

关键模块：
- WebSocket：`springboot_backend/src/main/java/.../websocket/EmgWebSocketHandler.java`
- 标注：`.../controller/AnnotationController.java` + `.../service/AnnotationService.java`
- 训练：`.../controller/TrainingController.java` + `.../service/TrainingService.java`
- 模型：`.../controller/ModelController.java` + `.../service/ModelService.java`

### 3. App 端实现（HarmonyOS）
- 实时监控：展示 EMG 波形与当前识别手势。
- 数据标注：选择时间段与手势类别，提交标注请求。
- 训练管理：配置参数并发起训练任务，查看进度与结果。
- 模型管理：展示模型版本、激活/切换。

### 4. 训练与模型部署
- 训练过程：后端导出标注数据 → Python 脚本训练 → 输出模型与指标。
- 部署策略：边缘主推理，云端备用推理；支持自动模型更新。
- 转换流程：训练模型可导出 ONNX/TFLite 以适配边缘环境。

---

## 三、测试分析

### 1. 测试目标
- 验证端到端链路：采集 → 传输 → 展示 → 标注 → 训练 → 部署。
- 验证核心性能：实时性、稳定性、数据完整性。
- 验证业务闭环：标注数据可被训练并产生新模型版本。

### 2. 测试维度与用例

**(1) 功能测试**
- WebSocket 连接与数据广播：验证 KunpengPro 数据可被 App 实时接收。
- 数据标注保存：App 选择时间段后，数据库落库数量正确。
- 训练任务流程：任务可创建、进度可查询、结果可回写。
- 模型版本管理：激活/下载/回滚功能正常。

**(2) 集成测试**
- 端云协同链路：KunpengPro → 后端 → App 全链路连续运行。
- 训练闭环：标注 → 训练 → 新模型部署 → 推理更新。

**(3) 性能测试**
- 延迟：边缘推理在实时窗口内完成，端到端延迟可控。
- 稳定性：长时间运行无断连、无内存泄漏。
- 吞吐：多设备接入时后端广播稳定。

### 3. 测试工具与脚本
- WebSocket 调试：`test_websocket_app.py` 模拟 App 端接收数据。
- Windows 端上传工具：`windows_emg_uploader.py` 模拟数据注入。
- 训练验证：训练脚本输出日志与指标，验证任务状态一致性。

### 4. 结果分析与改进方向
- 数据质量：通过标注流程控制数据进入训练集，提高稳定性。
- 模型迭代：以“版本化 + 可回滚”方式降低更新风险。
- 可用性保障：边缘优先推理，云端备用推理提升鲁棒性。

---

## 附：与项目代码的对应关系
- 边缘采集与推理：`code/scripts/`
- 模型训练与评估：`code/training/`、`code/event_onset/`
- 后端服务：`springboot_backend/src/main/java/`
- App 前端：`app/entry/src/main/ets/`

