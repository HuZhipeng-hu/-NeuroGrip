package com.huaweiict.emg.controller;

import com.huaweiict.emg.entity.DailyUsageStats;
import com.huaweiict.emg.service.DailyUsageStatsService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/stats")
public class DailyUsageStatsController {

    @Autowired
    private DailyUsageStatsService dailyUsageStatsService;

    // GET /api/stats/today?userId=1
    @GetMapping("/today")
    public ResponseEntity<?> getTodayStats(@RequestParam Long userId) {
        Optional<DailyUsageStats> stats = dailyUsageStatsService.getTodayStats(userId);
        if (stats.isPresent()) {
            return ResponseEntity.ok(stats.get());
        } else {
            return ResponseEntity.notFound().build();
        }
    }

    // GET /api/stats/last7days?userId=1
    @GetMapping("/last7days")
    public ResponseEntity<List<DailyUsageStats>> getLast7DaysStats(@RequestParam Long userId) {
        List<DailyUsageStats> stats = dailyUsageStatsService.getLast7DaysStats(userId);
        return ResponseEntity.ok(stats);
    }

    // POST /api/stats/update —— 用于设备上报一次使用
    @PostMapping("/update")
    public ResponseEntity<String> updateUsage(
            @RequestParam Long userId,
            @RequestParam(defaultValue = "1") Integer count,
            @RequestParam(required = false) String tips) {

        dailyUsageStatsService.saveOrUpdateTodayStats(userId, count, tips);
        return ResponseEntity.ok("Updated");
    }
}
