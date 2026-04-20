# 无监督手势识别集成方案

## 概述

本方案基于 **GeometryOFsEMG** 项目的思想，将黎曼流形几何方法集成到现有的EMG手势识别系统中，提供**无监督学习**的替代方案。

### 核心优势

1. **无需标注数据**：k-Medoids聚类可以直接从原始EMG信号中发现手势模式
2. **轻量级**：不需要大规模神经网络训练，计算资源需求低
3. **可解释性强**：基于几何距离，易于理解和调试
4. **个性化适应**：对个体差异更敏感，适合单用户场景

### 理论基础

#### 黎曼流形方法

EMG信号的协方差矩阵是**对称正定(SPD)矩阵**，这些矩阵构成一个黎曼流形。在这个流形上：

- **欧几里得几何不适用**：直接的线性距离会扭曲数据结构
- **黎曼度量**：使用对数欧几里得距离或仿射不变度量
- **黎曼均值**：Karcher mean，而非算术平均

#### 距离度量

**Log-Euclidean 距离**（快速）:
```
d(C₁, C₂) = ||log(C₁) - log(C₂)||_F
```

**仿射不变黎曼距离**（精确）:
```
d(C₁, C₂) = ||log(C₁^{-1/2} C₂ C₁^{-1/2})||_F
```

---

## 文件结构

```
code/unsupervised/
├── __init__.py                    # 模块入口
├── manifold_utils.py              # 黎曼流形工具函数
├── riemannian_classifier.py       # 分类器实现
└── unsupervised_train.py          # 训练/预测脚本
```

---

## 使用方法

### 1. 无监督训练（k-Medoids聚类）

不需要标注数据，自动发现手势模式：

```bash
cd code
python -m unsupervised.unsupervised_train \
    --mode unsupervised \
    --data_dir ../data \
    --n_clusters 6 \
    --window_size 150 \
    --stride 75 \
    --metric logeuclid \
    --output models/unsupervised_riemannian.pkl
```

**参数说明**:
- `--n_clusters`: 手势类别数量（需要预先知道）
- `--window_size`: EMG窗口大小（帧数），与数据采集率相关
- `--stride`: 滑动窗口步长，越小样本越多
- `--metric`: 距离度量，`logeuclid` 更快，`riemannian` 更精确

**输出**:
- 聚类模型文件（.pkl）
- 聚类质量评估（如果有标签）

### 2. MDM训练（需要标签）

使用标注数据训练MDM分类器：

```bash
python -m unsupervised.unsupervised_train \
    --mode mdm \
    --data_dir ../data \
    --window_size 150 \
    --metric logeuclid \
    --output models/mdm_classifier.pkl
```

**优势**:
- 训练极快（只需计算类均值，无需梯度下降）
- 模型小（只存储每个类的SPD矩阵）
- 适合快速原型和实时更新

### 3. 预测

使用训练好的模型预测新数据：

```bash
python -m unsupervised.unsupervised_train \
    --mode predict \
    --model models/unsupervised_riemannian.pkl \
    --input test_data.csv \
    --output_csv predictions.csv
```

---

## 代码示例

### 基本使用

```python
from code.unsupervised import RiemannianGestureClassifier
import numpy as np

# 1. 准备数据（假设已有EMG窗口）
emg_windows = [...]  # List[np.ndarray], 每个形状 (150, 8)

# 2. 创建分类器
classifier = RiemannianGestureClassifier(
    n_clusters=6,
    window_size=150,
    metric='logeuclid'
)

# 3. 无监督训练
classifier.fit(emg_windows, max_iter=50)

# 4. 预测新数据
new_window = np.random.randn(150, 8)  # 示例
gesture_id, confidence = classifier.predict(new_window)
print(f"预测手势: {gesture_id}, 置信度: {confidence:.2f}")

# 5. 保存/加载模型
classifier.save('models/my_model.pkl')
loaded_classifier = RiemannianGestureClassifier.load('models/my_model.pkl')
```

### MDM分类器

```python
from code.unsupervised import MDMClassifier

# 有标签数据
emg_windows = [...]  # List[np.ndarray]
labels = np.array([0, 0, 1, 1, 2, 2, ...])  # 手势标签
class_names = {0: 'fist', 1: 'pinch', 2: 'relax'}

# 训练
mdm = MDMClassifier(window_size=150, metric='logeuclid')
mdm.fit(emg_windows, labels, class_names)

# 预测
gesture_id, confidence = mdm.predict(new_window)
print(f"手势: {class_names[gesture_id]}, 置信度: {confidence:.2f}")

# 保存
mdm.save('models/mdm_model.pkl')
```

### 与现有系统集成

可以在实时推理时同时运行有监督和无监督模型，进行融合决策：

```python
# 加载两种模型
from code.runtime.inference import InferenceEngine  # 现有的CNN/LSTM模型
from code.unsupervised import RiemannianGestureClassifier

cnn_lstm_engine = InferenceEngine('models/neurogrin_net.ckpt')
riemannian_clf = RiemannianGestureClassifier.load('models/unsupervised.pkl')

# 融合预测
def fused_predict(emg_window):
    # 有监督预测
    supervised_probs = cnn_lstm_engine.predict_proba(emg_window)
    supervised_gesture = int(np.argmax(supervised_probs))
    
    # 无监督预测
    unsupervised_gesture, unsup_conf = riemannian_clf.predict(emg_window)
    
    # 简单融合：高置信度优先
    if unsup_conf > 0.8:
        return unsupervised_gesture
    else:
        return supervised_gesture
```

---

## 算法对比

| 特性 | 现有方案 (CNN/LSTM) | 无监督方案 (Riemannian) | MDM方案 |
|------|-------------------|----------------------|---------|
| **需要标注** | ✅ 是 | ❌ 否 | ✅ 是 |
| **训练时间** | 长（数小时） | 中（分钟级） | 快（秒级） |
| **推理速度** | 快 | 快 | 快 |
| **准确率** | 高（90%+） | 中（70-85%） | 中高（80-90%） |
| **模型大小** | 大（MB级） | 小（KB级） | 极小（KB级） |
| **可解释性** | 低 | 高 | 高 |
| **适用场景** | 多用户通用模型 | 单用户冷启动 | 快速原型/在线学习 |

---

## 应用场景

### 1. 冷启动问题

新用户没有标注数据时，可以：
1. 让用户自然做各种手势
2. 使用无监督聚类发现模式
3. 用户确认聚类对应的手势
4. 转换为有监督模型或MDM

### 2. 在线学习

边使用边改进：
1. 初始使用无监督或MDM模型
2. 收集使用中的正确/错误反馈
3. 更新类均值或聚类中心
4. 无需重新训练整个神经网络

### 3. 异常检测

所有聚类中心距离都很远 → 可能是新手势或错误数据

### 4. 跨用户迁移

在新用户上快速适应：
1. 使用通用CNN/LSTM提取特征
2. 在特征空间上应用黎曼方法
3. 只需少量样本即可个性化

---

## 性能优化建议

### 1. 距离度量选择

- **Log-Euclidean**: 速度快 2-3倍，适合实时应用
- **Riemannian**: 更精确，适合离线训练

### 2. 窗口大小

- 150帧（200Hz→0.75秒）是经验值
- 太短：信号不稳定
- 太长：延迟高，手势转换慢

### 3. 正则化参数

协方差矩阵加入 `λI` 确保正定：
- 默认 `1e-6` 适合大部分情况
- 信号噪声大时增加到 `1e-4`

### 4. 聚类初始化

当前使用随机初始化，可以改进为：
- 使用PCA降维后的k-means++初始化
- 多次运行选择最佳结果

---

## 实验结果（预期）

基于文献和GeometryOFsEMG项目的报告：

| 方法 | Ninapro DB1 | MyoArmband | 本项目数据 (预估) |
|------|-------------|------------|----------------|
| CNN/LSTM (有监督) | 92-95% | 88-92% | 90-94% |
| k-Medoids (无监督) | 70-75% | 65-72% | **70-80%** |
| MDM (有监督) | 82-87% | 78-85% | **80-88%** |

**注意**: 实际性能取决于：
- 数据质量
- 用户个体差异
- 手势相似度

---

## 进一步改进方向

### 1. 混合模型

```python
# 切空间投影 + 传统ML
from code.unsupervised import tangent_space_projection, vectorize_symmetric
from sklearn.svm import SVC

# 计算参考点（所有类的黎曼均值）
reference = riemannian_mean(all_spd_matrices)

# 投影到切空间并向量化
features = []
for spd in spd_matrices:
    tangent = tangent_space_projection(spd, reference)
    vec = vectorize_symmetric(tangent)
    features.append(vec)

# 使用SVM分类
X = np.array(features)
y = labels
svm = SVC(kernel='rbf').fit(X, y)
```

### 2. 迁移学习

预训练CNN特征提取器 + 黎曼分类器

### 3. 自适应更新

在线更新聚类中心：
```python
# 收到新的正确预测样本
new_spd = compute_covariance_matrix(new_window)
# 指数移动平均更新
alpha = 0.1
cluster_centers_[gesture_id] = (
    (1 - alpha) * cluster_centers_[gesture_id] + 
    alpha * new_spd
)
```

---

## 故障排查

### 问题1: 聚类质量差

**症状**: 聚类纯度 < 50%

**解决**:
1. 增加样本数量
2. 调整窗口大小
3. 尝试不同的度量（logeuclid vs riemannian）
4. 检查数据是否包含明显不同的手势

### 问题2: 预测速度慢

**症状**: 推理延迟 > 100ms

**解决**:
1. 使用 `logeuclid` 而非 `riemannian`
2. 减少聚类数量
3. 预计算并缓存矩阵的逆、特征分解等

### 问题3: 与有监督模型结果差异大

**症状**: 两种方法预测完全不同

**原因**: 无监督聚类的类别ID是任意的，不对应真实标签

**解决**: 使用聚类到手势的映射表（通过少量标注样本建立）

---

## 参考资料

1. **论文**: "Topology of surface electromyogram signals: hand gesture decoding on Riemannian manifolds"
   - https://iopscience.iop.org/article/10.1088/1741-2552/ad5107

2. **代码**: GeometryOFsEMG
   - https://github.com/HarshavardhanaTG/GeometryOFsEMG

3. **Pyriemann库** (可选集成):
   - https://pyriemann.readthedocs.io/

4. **相关论文**:
   - Barachant et al. "Classification of covariance matrices using a Riemannian-based kernel for BCI applications"
   - Congedo et al. "Riemannian geometry for EEG-based brain-computer interfaces"

---

## 总结

本方案提供了一个完整的无监督/半监督手势识别解决方案，可以：

✅ **独立使用**: 在没有标注数据时提供基础识别能力  
✅ **与现有系统并行**: 作为补充方案提高鲁棒性  
✅ **快速原型**: MDM训练极快，适合实验迭代  
✅ **在线学习**: 轻量级更新，适合个性化适应  

建议的使用流程：
1. 先用现有CNN/LSTM方案获得高精度基线
2. 新用户冷启动时使用无监督方案
3. 收集少量反馈后切换到MDM
4. 数据充足后训练个性化CNN/LSTM模型

这样可以在不同阶段选择最合适的方法，充分利用两种范式的优势。

