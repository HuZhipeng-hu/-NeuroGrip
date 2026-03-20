package com.huaweiict.emg.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import javax.persistence.*;
import java.time.LocalDateTime;

/**
 * 用户自定义手势实体类
 */
@Entity
@Table(name = "custom_game_gestures")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class CustomGesture {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /** 设备ID（用户标识） */
    @Column(name = "device_id")
    private String deviceId;
    
    /** 手势ID（slug格式） */
    @Column(name = "gesture_id")
    private String gestureId;
    
    /** 手势显示标签 */
    @Column(name = "gesture_label")
    private String gestureLabel;
    
    /** 手势emoji图标 */
    @Column(name = "gesture_icon")
    private String gestureIcon;
    
    /** 手势使用次数 */
    @Column(name = "use_count")
    private Integer useCount = 0;
    
    /** 是否激活 */
    @Column(name = "is_active")
    private Boolean isActive = true;
    
    /** 创建时间 */
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    /** 更新时间 */
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
