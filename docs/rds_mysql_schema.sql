-- ==============================================================================
-- 华为 RDS for MySQL 建表 SQL
-- ==============================================================================
-- 在华为云 RDS 控制台或 MySQL 客户端执行
-- 确保已在安全组中开放 3306 端口（仅允许 ECS 内网 IP 访问）
--
-- 使用前：
--   1. 在华为云 RDS 控制台创建数据库实例
--   2. 配置安全组：入方向规则添加 3306 端口，源地址设为你的 ECS 内网 IP 或 CIDR
--   3. 创建数据库和用户
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS `emg_db`
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `emg_db`;

-- 1. EMG 帧数据表（核心表，存储每帧完整数据）
CREATE TABLE IF NOT EXISTS `emg_frame` (
    `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
    `device_id`     VARCHAR(64)       NOT NULL COMMENT '设备标识（如 orangepi_01）',
    `device_ts`     INT UNSIGNED      COMMENT '设备端时间戳',
    `server_time`   DATETIME(3)       NOT NULL COMMENT '服务器接收时间（毫秒精度）',
    `emg_data`      JSON              COMMENT 'EMG 10x8 二维数组 JSON',
    `emg_pack1`     VARCHAR(64)       COMMENT 'EMG 第1包8通道（逗号分隔，方便查询）',
    `acc_x`         TINYINT           COMMENT '加速度X',
    `acc_y`         TINYINT           COMMENT '加速度Y',
    `acc_z`         TINYINT           COMMENT '加速度Z',
    `gyro_x`        TINYINT           COMMENT '陀螺仪X',
    `gyro_y`        TINYINT           COMMENT '陀螺仪Y',
    `gyro_z`        TINYINT           COMMENT '陀螺仪Z',
    `pitch`         TINYINT           COMMENT '俯仰角',
    `roll`          TINYINT           COMMENT '横滚角',
    `yaw`           TINYINT           COMMENT '偏航角',
    `battery`       TINYINT UNSIGNED  COMMENT '电池电量 0-100',
    `gesture`       VARCHAR(32)       COMMENT '识别的手势',
    `confidence`    FLOAT             COMMENT '手势置信度 0-1',
    `created_at`    DATETIME(3)       DEFAULT CURRENT_TIMESTAMP(3),
    INDEX `idx_device_time` (`device_id`, `server_time`),
    INDEX `idx_server_time` (`server_time`),
    INDEX `idx_gesture` (`gesture`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='EMG 实时帧数据';


-- 2. 手势事件表（手势变化时记录，App 查询"发生了什么手势"）
CREATE TABLE IF NOT EXISTS `gesture_event` (
    `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
    `device_id`     VARCHAR(64)       NOT NULL,
    `event_time`    DATETIME(3)       NOT NULL COMMENT '事件发生时间',
    `gesture`       VARCHAR(32)       NOT NULL COMMENT '手势名称',
    `confidence`    FLOAT             COMMENT '置信度',
    `duration_ms`   INT               COMMENT '持续时长（毫秒）',
    `created_at`    DATETIME(3)       DEFAULT CURRENT_TIMESTAMP(3),
    INDEX `idx_device_event` (`device_id`, `event_time`),
    INDEX `idx_gesture` (`gesture`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='手势变化事件（手势切换时写入一条）';


-- 3. 设备状态表（记录设备上下线、电池等）
CREATE TABLE IF NOT EXISTS `device_status` (
    `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
    `device_id`     VARCHAR(64)       NOT NULL,
    `status`        VARCHAR(16)       COMMENT 'online/offline',
    `battery`       TINYINT UNSIGNED  COMMENT '电池电量',
    `fps`           FLOAT             COMMENT '当前帧率',
    `ip_address`    VARCHAR(64)       COMMENT '上报端IP',
    `update_time`   DATETIME(3)       NOT NULL,
    `created_at`    DATETIME(3)       DEFAULT CURRENT_TIMESTAMP(3),
    INDEX `idx_device` (`device_id`),
    INDEX `idx_update_time` (`update_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='设备状态（上下线、心跳）';


-- 4. EMG 聚合统计表（可选，用于首页展示统计数据）
CREATE TABLE IF NOT EXISTS `emg_statistics` (
    `id`            BIGINT AUTO_INCREMENT PRIMARY KEY,
    `device_id`     VARCHAR(64)       NOT NULL,
    `stat_time`     DATETIME          NOT NULL COMMENT '统计时间（按分钟）',
    `frame_count`   INT               COMMENT '帧数',
    `avg_battery`   FLOAT             COMMENT '平均电量',
    `gesture_counts`JSON              COMMENT '各手势出现次数 {"fist":10,"open":5}',
    INDEX `idx_device_stat` (`device_id`, `stat_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='EMG 分钟级聚合统计';


-- ==============================================================================
-- 安全组配置说明（华为云）
-- ==============================================================================
-- 1. 进入华为云控制台 → 虚拟私有云 → 安全组
-- 2. 找到 RDS 实例关联的安全组
-- 3. 添加入方向规则：
--      协议: TCP
--      端口: 3306
--      源地址: 你的 ECS 实例内网IP/32  （如 192.168.0.100/32）
--    ⚠ 不要设为 0.0.0.0/0（不安全）
-- 4. 如果 OrangePi 在公网，需要开启 RDS 公网访问并绑定 EIP
--    但推荐：OrangePi → ECS(Spring Boot) → RDS（三层架构更安全）
-- ==============================================================================
