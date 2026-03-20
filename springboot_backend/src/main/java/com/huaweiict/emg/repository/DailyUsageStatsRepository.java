package com.huaweiict.emg.repository;

import com.huaweiict.emg.entity.DailyUsageStats;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

@Repository
public interface DailyUsageStatsRepository extends JpaRepository<DailyUsageStats, Long> {

    // 根据用户ID和日期查询（用于检查当天记录是否存在）
    DailyUsageStats findByUserIdAndStatDate(Long userId, LocalDate statDate);

    // 查询某用户在指定日期范围内的记录（用于“最近7天”图表）
    List<DailyUsageStats> findByUserIdAndStatDateBetweenOrderByStatDateAsc(
            Long userId, LocalDate startDate, LocalDate endDate);

    // 查询该用户所有记录中的最大 usageCount（用于 max_daily_usage）
    // 注意：需要确保 max() 的返回值
    // Query annotation might be needed if JPQL behavior is different, but method name parsing usually works.
    // However, findMaxUsageCountByUserId is not a standard strict query method name unless defined.
    // The original code used findMaxUsageCountByUserId.
    // Wait, Spring Data JPA doesn't support aggregate functions directly via method name like this unless it's `findTopByOrderByUsageCountDesc`.
    // Let's check `ict_end` again. Did it have `@Query`? No.
    // Ah, `findMaxUsageCountByUserId` is NOT standard. It probably failed or relied on something else.
    // Or maybe `ict_end` had `@Query` and I missed it?
    // Let's check `ict_end/repository/DailyUsageStatsRepository.java`.
    // I read it in previous turn. It did NOT have `@Query`.
    // That method `findMaxUsageCountByUserId` is suspicious.
    // Spring Data JPA derives query from method name. `find`... `MaxUsageCount`... `ByUserId`.
    // No, standard keywords are `find...By...`. `MaxUsageCount` is not a property unless the property is `maxUsageCount` (which it is not, it is `usageCount`).
    // So `findTopByUserIdOrderByUsageCountDesc` would restrict by user and order by usageCount, then gettop.
    // I should fix this to be correct.
    
    // BETTER: Use @Query.
    // @Query("SELECT MAX(d.usageCount) FROM DailyUsageStats d WHERE d.userId = ?1")
    // Integer findMaxUsageCountByUserId(Long userId);

    @org.springframework.data.jpa.repository.Query("SELECT MAX(d.usageCount) FROM DailyUsageStats d WHERE d.userId = ?1")
    Integer findMaxUsageCountByUserId(Long userId);
}
