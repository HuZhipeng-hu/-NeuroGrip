-- =============================================
-- EMG 手势识别系统 - 数据库架构更新
-- =============================================
-- 用途：支持数据标注、模型训练和部署管理
-- 执行：在华为云RDS MySQL中运行
-- =============================================

USE emg_system;

-- =============================================
-- 1. 标注数据表 (emg_labeled_data)
-- =============================================
-- 存储用户通过App标注的EMG数据
-- =============================================

CREATE TABLE IF NOT EXISTS emg_labeled_data (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    
    -- 时间信息
    capture_time DATETIME NOT NULL COMMENT '采集时间',
    device_ts BIGINT COMMENT '设备时间戳（毫秒）',
    
    -- EMG数据（JSON存储，保持原始格式）
    emg_data JSON NOT NULL COMMENT 'EMG原始数据 10x8 数组',
    acc_data JSON COMMENT '加速度数据 [x,y,z]',
    gyro_data JSON COMMENT '陀螺仪数据 [x,y,z]',
    angle_data JSON COMMENT '角度数据 [pitch,roll,yaw]',
    battery TINYINT COMMENT '电池电量 0-100',
    
    -- 标注信息
    gesture_label VARCHAR(50) NOT NULL COMMENT '手势标签: fist/ok/pinch/relax/sidegrip/ye等',
    annotator VARCHAR(100) COMMENT '标注人（用户ID或用户名）',
    annotation_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '标注时间',
    annotation_note TEXT COMMENT '标注备注',
    
    -- 训练相关
    is_used_for_training BOOLEAN DEFAULT FALSE COMMENT '是否已用于训练',
    split_type VARCHAR(20) COMMENT '数据集分割类型: train/val/test',
    training_task_id BIGINT COMMENT '使用该数据的训练任务ID',
    
    -- 数据质量
    quality_score FLOAT COMMENT '数据质量分数 0-1',
    signal_noise_ratio FLOAT COMMENT '信噪比',
    is_valid BOOLEAN DEFAULT TRUE COMMENT '是否有效（可用于过滤异常数据）',
    
    -- 元数据
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_gesture (gesture_label),
    INDEX idx_device (device_id),
    INDEX idx_time (capture_time),
    INDEX idx_training (is_used_for_training, split_type),
    INDEX idx_annotator (annotator),
    INDEX idx_valid (is_valid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='EMG标注数据表';

-- =============================================
-- 2. 训练任务表 (training_task)
-- =============================================
-- 管理模型训练任务的生命周期
-- =============================================

CREATE TABLE IF NOT EXISTS training_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    task_name VARCHAR(100) NOT NULL COMMENT '任务名称',
    task_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '任务状态: pending/running/completed/failed/cancelled',
    
    -- 训练参数配置
    config JSON COMMENT '训练配置参数 {epochs, batch_size, learning_rate, window_size, model_type等}',
    data_filter JSON COMMENT '数据筛选条件 {gestures, date_range, quality_threshold等}',
    
    -- 数据集统计
    total_samples INT COMMENT '总样本数',
    train_samples INT COMMENT '训练集样本数',
    val_samples INT COMMENT '验证集样本数',
    test_samples INT COMMENT '测试集样本数',
    gesture_distribution JSON COMMENT '手势分布统计 {"fist": 1200, "ok": 1000, ...}',
    
    -- 训练进度
    current_epoch INT DEFAULT 0 COMMENT '当前epoch',
    total_epochs INT COMMENT '总epoch数',
    progress_percent FLOAT DEFAULT 0.0 COMMENT '训练进度百分比 0-100',
    
    -- 训练结果
    model_path VARCHAR(500) COMMENT '模型文件路径',
    model_size_mb FLOAT COMMENT '模型文件大小（MB）',
    
    train_accuracy FLOAT COMMENT '训练集准确率',
    val_accuracy FLOAT COMMENT '验证集准确率',
    test_accuracy FLOAT COMMENT '测试集准确率',
    
    final_train_loss FLOAT COMMENT '最终训练损失',
    final_val_loss FLOAT COMMENT '最终验证损失',
    
    best_epoch INT COMMENT '最佳epoch',
    best_val_accuracy FLOAT COMMENT '最佳验证准确率',
    
    metrics JSON COMMENT '详细指标 {precision, recall, f1_score, confusion_matrix等}',
    
    -- 时间信息
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '任务创建时间',
    start_time DATETIME COMMENT '开始训练时间',
    end_time DATETIME COMMENT '结束时间',
    duration_seconds INT COMMENT '训练耗时（秒）',
    
    -- 日志与错误
    log_file VARCHAR(500) COMMENT '训练日志文件路径',
    error_message TEXT COMMENT '错误信息（失败时记录）',
    
    -- 创建者
    created_by VARCHAR(100) COMMENT '任务创建者（用户ID）',
    
    -- 索引
    INDEX idx_status (task_status),
    INDEX idx_time (created_time),
    INDEX idx_creator (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='训练任务表';

-- =============================================
-- 3. 模型版本表 (model_version)
-- =============================================
-- 管理训练完成的模型版本
-- =============================================

CREATE TABLE IF NOT EXISTS model_version (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    version VARCHAR(50) NOT NULL UNIQUE COMMENT '模型版本号 如: v1.0.0, v1.0.1',
    model_name VARCHAR(100) NOT NULL COMMENT '模型名称',
    
    -- 模型文件信息
    model_path VARCHAR(500) NOT NULL COMMENT '模型文件路径（相对路径或绝对路径）',
    model_format VARCHAR(20) NOT NULL COMMENT '模型格式: pytorch/onnx/tflite/mindspore',
    model_size_mb FLOAT COMMENT '模型文件大小（MB）',
    checksum VARCHAR(64) COMMENT '模型文件MD5/SHA256校验和',
    
    -- 训练信息
    training_task_id BIGINT COMMENT '关联的训练任务ID',
    trained_samples INT COMMENT '训练样本总数',
    gesture_classes JSON COMMENT '支持的手势类别列表 ["fist", "ok", ...]',
    num_classes INT COMMENT '手势类别数量',
    
    -- 模型架构
    model_architecture VARCHAR(100) COMMENT '模型架构: CNN/LSTM/CNN_LSTM/Transformer',
    input_shape JSON COMMENT '输入形状 {window_size: 150, channels: 8}',
    
    -- 性能指标
    accuracy FLOAT COMMENT '测试集准确率',
    precision_score FLOAT COMMENT '精确率',
    recall_score FLOAT COMMENT '召回率',
    f1_score FLOAT COMMENT 'F1分数',
    
    inference_time_ms FLOAT COMMENT '平均推理时间（毫秒）',
    model_params_count BIGINT COMMENT '模型参数量',
    
    -- 部署状态
    is_active BOOLEAN DEFAULT FALSE COMMENT '是否为当前激活/生产版本',
    deployed_to JSON COMMENT '部署位置列表 ["orangepi_01", "cloud"]',
    deploy_time DATETIME COMMENT '最近部署时间',
    
    -- 元数据
    description TEXT COMMENT '模型描述',
    tags JSON COMMENT '标签 ["baseline", "optimized", "production"]',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    
    -- 外键
    FOREIGN KEY (training_task_id) REFERENCES training_task(id) ON DELETE SET NULL,
    
    -- 索引
    INDEX idx_version (version),
    INDEX idx_active (is_active),
    INDEX idx_format (model_format),
    INDEX idx_task (training_task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型版本管理表';

-- =============================================
-- 4. 数据标注会话表 (annotation_session)
-- =============================================
-- 记录用户的标注会话（批量标注场景）
-- =============================================

CREATE TABLE IF NOT EXISTS annotation_session (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_name VARCHAR(100) COMMENT '会话名称',
    device_id VARCHAR(50) NOT NULL,
    annotator VARCHAR(100) NOT NULL,
    
    -- 时间范围
    start_time DATETIME NOT NULL COMMENT '标注数据的开始时间',
    end_time DATETIME NOT NULL COMMENT '标注数据的结束时间',
    
    -- 统计
    total_frames INT COMMENT '本次标注的总帧数',
    gesture_label VARCHAR(50) NOT NULL COMMENT '标注的手势类型',
    
    -- 元数据
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_annotator (annotator),
    INDEX idx_time (start_time, end_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标注会话记录表';

-- =============================================
-- 5. 模型部署记录表 (model_deployment)
-- =============================================
-- 记录模型部署历史
-- =============================================

CREATE TABLE IF NOT EXISTS model_deployment (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    model_version_id BIGINT NOT NULL COMMENT '模型版本ID',
    version VARCHAR(50) NOT NULL COMMENT '模型版本号',
    
    -- 部署目标
    target_type VARCHAR(20) NOT NULL COMMENT '部署目标类型: orangepi/cloud/edge',
    target_device_id VARCHAR(50) COMMENT '目标设备ID',
    
    -- 部署状态
    deploy_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '部署状态: pending/deploying/success/failed/rollback',
    
    -- 部署信息
    deploy_method VARCHAR(50) COMMENT '部署方式: auto_download/manual_upload/docker',
    deploy_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    activated_time DATETIME COMMENT '激活时间（开始使用）',
    deactivated_time DATETIME COMMENT '停用时间',
    
    -- 性能跟踪
    avg_inference_time_ms FLOAT COMMENT '实际平均推理时间',
    total_inferences BIGINT DEFAULT 0 COMMENT '总推理次数',
    success_rate FLOAT COMMENT '推理成功率',
    
    -- 日志
    error_message TEXT COMMENT '部署错误信息',
    deployed_by VARCHAR(100),
    
    FOREIGN KEY (model_version_id) REFERENCES model_version(id) ON DELETE CASCADE,
    
    INDEX idx_version (model_version_id),
    INDEX idx_target (target_device_id),
    INDEX idx_status (deploy_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型部署记录表';

-- =============================================
-- 6. 系统配置表 (system_config)
-- =============================================
-- 存储系统配置参数
-- =============================================

CREATE TABLE IF NOT EXISTS system_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    value_type VARCHAR(20) COMMENT '值类型: string/int/float/json/boolean',
    description TEXT COMMENT '配置说明',
    is_editable BOOLEAN DEFAULT TRUE COMMENT '是否可编辑',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    
    INDEX idx_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';

-- =============================================
-- 插入默认配置
-- =============================================

INSERT INTO system_config (config_key, config_value, value_type, description) VALUES
('data.cache.retention_minutes', '10', 'int', '实时数据缓存保留时间（分钟）'),
('data.cache.max_frames', '30000', 'int', '最大缓存帧数'),
('training.default_epochs', '50', 'int', '默认训练轮数'),
('training.default_batch_size', '32', 'int', '默认批次大小'),
('training.default_learning_rate', '0.001', 'float', '默认学习率'),
('training.default_window_size', '150', 'int', '默认滑动窗口大小'),
('model.active_version', '', 'string', '当前激活的模型版本'),
('model.auto_deploy', 'false', 'boolean', '是否自动部署新模型到OrangePi'),
('gesture.supported_classes', '["fist", "ok", "pinch", "relax", "sidegrip", "ye"]', 'json', '支持的手势类别')
ON DUPLICATE KEY UPDATE config_value=VALUES(config_value);

-- =============================================
-- 创建视图：训练任务摘要
-- =============================================

CREATE OR REPLACE VIEW v_training_task_summary AS
SELECT 
    t.id,
    t.task_name,
    t.task_status,
    t.total_samples,
    t.test_accuracy,
    t.created_time,
    t.duration_seconds,
    t.created_by,
    m.version AS model_version,
    m.is_active AS model_is_active
FROM training_task t
LEFT JOIN model_version m ON m.training_task_id = t.id
ORDER BY t.created_time DESC;

-- =============================================
-- 创建视图：数据标注统计
-- =============================================

CREATE OR REPLACE VIEW v_annotation_statistics AS
SELECT 
    gesture_label,
    COUNT(*) AS sample_count,
    COUNT(DISTINCT device_id) AS device_count,
    COUNT(DISTINCT annotator) AS annotator_count,
    MIN(capture_time) AS earliest_time,
    MAX(capture_time) AS latest_time,
    AVG(quality_score) AS avg_quality_score,
    SUM(CASE WHEN is_used_for_training THEN 1 ELSE 0 END) AS used_in_training_count
FROM emg_labeled_data
WHERE is_valid = TRUE
GROUP BY gesture_label;

-- =============================================
-- 创建存储过程：获取训练数据
-- =============================================

DELIMITER //

CREATE PROCEDURE get_training_data(
    IN p_gesture_filter JSON,
    IN p_date_from DATETIME,
    IN p_date_to DATETIME,
    IN p_min_quality FLOAT
)
BEGIN
    -- 查询符合条件的标注数据用于训练
    SELECT 
        id,
        device_id,
        capture_time,
        device_ts,
        emg_data,
        acc_data,
        gyro_data,
        angle_data,
        gesture_label
    FROM emg_labeled_data
    WHERE is_valid = TRUE
        AND quality_score >= IFNULL(p_min_quality, 0)
        AND capture_time BETWEEN p_date_from AND p_date_to
        AND (p_gesture_filter IS NULL OR JSON_CONTAINS(p_gesture_filter, JSON_QUOTE(gesture_label)))
    ORDER BY capture_time;
END //

DELIMITER ;

-- =============================================
-- 创建存储过程：更新训练进度
-- =============================================

DELIMITER //

CREATE PROCEDURE update_training_progress(
    IN p_task_id BIGINT,
    IN p_current_epoch INT,
    IN p_progress FLOAT,
    IN p_train_acc FLOAT,
    IN p_val_acc FLOAT,
    IN p_train_loss FLOAT,
    IN p_val_loss FLOAT
)
BEGIN
    UPDATE training_task
    SET 
        current_epoch = p_current_epoch,
        progress_percent = p_progress,
        train_accuracy = p_train_acc,
        val_accuracy = p_val_acc,
        final_train_loss = p_train_loss,
        final_val_loss = p_val_loss,
        updated_time = CURRENT_TIMESTAMP
    WHERE id = p_task_id;
END //

DELIMITER ;

-- =============================================
-- 说明
-- =============================================
-- 1. 执行此脚本后，需要确保原有的emg_frame和gesture_event表保留（用于历史数据）
-- 2. 新的标注数据将存储在emg_labeled_data表中
-- 3. 训练任务通过training_task表管理
-- 4. 模型版本通过model_version表管理
-- 5. 部署记录通过model_deployment表跟踪
-- =============================================
