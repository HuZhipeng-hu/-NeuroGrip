package com.huaweiict.emg.service;

import com.huaweiict.emg.entity.DailyUsageStats;
import com.huaweiict.emg.repository.DailyUsageStatsRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Service
public class DailyUsageStatsService {

    @Autowired
    private DailyUsageStatsRepository dailyUsageStatsRepository;

    // 获取用户今天的数据
    public Optional<DailyUsageStats> getTodayStats(Long userId) {
        LocalDate today = LocalDate.now();
        DailyUsageStats stats = dailyUsageStatsRepository.findByUserIdAndStatDate(userId, today);
        return Optional.ofNullable(stats);
    }

    // 获取最近7天的数据（用于前端条形图）
    public List<DailyUsageStats> getLast7DaysStats(Long userId) {
        LocalDate today = LocalDate.now();
        LocalDate sevenDaysAgo = today.minusDays(6);
        return dailyUsageStatsRepository.findByUserIdAndStatDateBetweenOrderByStatDateAsc(
                userId, sevenDaysAgo, today);
    }

    // 更新或创建今日统计（核心方法）
    public void saveOrUpdateTodayStats(Long userId, int incrementCount, String tips) {
        LocalDate today = LocalDate.now();

        // 1. 查找今天是否已有记录
        DailyUsageStats existing = dailyUsageStatsRepository.findByUserIdAndStatDate(userId, today);

        DailyUsageStats stats;
        if (existing != null) {
            // 已存在：累加使用次数
            stats = existing;
            int newCount = stats.getUsageCount() + incrementCount;
            stats.setUsageCount(newCount);
        } else {
            // 不存在：创建新记录
            stats = new DailyUsageStats(userId, today);
            stats.setUsageCount(incrementCount);
            stats.setTips(tips);
            // 其他字段使用默认值（舒适=4.8，阶段=初期等）
        }

        // 2. 计算近7天平均使用次数（含今天）
        List<DailyUsageStats> last7Days = getLast7DaysStats(userId);
        int total = 0;
        for (DailyUsageStats d : last7Days) {
            total += d.getUsageCount();
        }
        int avg = last7Days.isEmpty() ? 0 : total / last7Days.size();
        stats.setAvgDailyUsage(avg);

        // 3. 更新历史最大值
        Integer maxEver = dailyUsageStatsRepository.findMaxUsageCountByUserId(userId);
        if (maxEver == null || stats.getUsageCount() > maxEver) {
            stats.setMaxDailyUsage(stats.getUsageCount());
        } else {
            stats.setMaxDailyUsage(maxEver);
        }

        // 4. 保存
        dailyUsageStatsRepository.save(stats);
    }
}
