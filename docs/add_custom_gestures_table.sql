-- ==============================================================================
-- 自定义手势表迁移脚本
-- ==============================================================================
-- 用途：在华为云 RDS MySQL 中为用户创建自定义手势存储表

USE `emg_db`;

-- 创建用户表（如果不存在）
CREATE TABLE IF NOT EXISTS `app_user` (
    `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
    `device_id`     VARCHAR(64)       NOT NULL UNIQUE COMMENT '设备ID（从App端上报）',
    `user_name`     VARCHAR(100)      COMMENT '用户昵称',
    `created_at`    DATETIME(3)       DEFAULT CURRENT_TIMESTAMP(3),
    `updated_at`    DATETIME(3)       DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    INDEX `idx_device_id` (`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='应用用户表（以设备ID标识）';


-- 创建自定义手势表
CREATE TABLE IF NOT EXISTS `custom_gesture` (
    `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
    `device_id`     VARCHAR(64)       NOT NULL COMMENT '设备ID（用户标识）',
    `gesture_id`    VARCHAR(64)       NOT NULL COMMENT '手势ID（slug格式，如：victory_peace）',
    `gesture_label` VARCHAR(100)      NOT NULL COMMENT '手势显示名称（如：胜利）',
    `gesture_icon`  VARCHAR(10)       NOT NULL COMMENT '手势emoji图标（如：✌️）',
    `use_count`     INT DEFAULT 0     COMMENT '该手势的使用次数',
    `is_active`     BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    `created_at`    DATETIME(3)       DEFAULT CURRENT_TIMESTAMP(3),
    `updated_at`    DATETIME(3)       DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    UNIQUE KEY `uk_device_gesture` (`device_id`, `gesture_id`),
    INDEX `idx_device_id` (`device_id`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='用户自定义手势表（每用户、每手势唯一）';


-- 修改标注记录表，添加自定义手势支持（如果需要）
-- 检查 emg_frame 表是否已有 gesture 字段
-- ALTER TABLE `emg_frame` ADD COLUMN `is_custom_gesture` BOOLEAN DEFAULT FALSE COMMENT '是否为自定义手势';

-- ==============================================================================
-- 使用说明
-- ==============================================================================
-- 1. 用户首次添加自定义手势时，App 上报 device_id、gesture_id、gesture_label、gesture_icon
-- 2. 后端调用 POST /api/annotation/custom-gestures 保存到数据库
-- 3. 用户删除自定义手势时，更新 is_active = FALSE（软删除，保留历史数据）
-- 4. 查询用户的所有自定义手势：GET /api/annotation/custom-gestures?device_id=xxx
-- ==============================================================================
