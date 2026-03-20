package com.huaweiict.emg.entity;

import lombok.Data;
import lombok.NoArgsConstructor;

import javax.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;

@Data
@NoArgsConstructor
@Entity
@Table(name = "daily_usage_stats")
public class DailyUsageStats {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "stat_date", nullable = false)
    private LocalDate statDate;

    @Column(name = "usage_count")
    private Integer usageCount = 0;

    @Column(name = "comfort_score", precision = 3, scale = 1)
    private BigDecimal comfortScore = new BigDecimal("4.8");

    @Column(name = "avg_daily_usage")
    private Integer avgDailyUsage = 0;

    @Column(name = "max_daily_usage")
    private Integer maxDailyUsage = 0;

    @Column(name = "comfort_level")
    private String comfortLevel = "舒适";

    @Column(name = "adaptation_stage")
    private String adaptationStage = "初期";

    @Column(name = "tips")
    private String tips;

    public DailyUsageStats(Long userId, LocalDate statDate) {
        this.userId = userId;
        this.statDate = statDate;
    }
}
