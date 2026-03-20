package com.huaweiict.emg.controller;

import com.huaweiict.emg.dto.AnnotationRequest;
import com.huaweiict.emg.model.CustomGesture;
import com.huaweiict.emg.service.AnnotationService;
import com.huaweiict.emg.service.CustomGestureService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 数据标注API控制器
 * 
 * 提供：
 * 1. 获取缓存数据（用于预览）
 * 2. 保存标注数据
 * 3. 查询标注统计信息
 */
@Slf4j
@RestController
@RequestMapping("/api/annotation")
public class AnnotationController {

    @Autowired
    private AnnotationService annotationService;
    
    @Autowired
    private CustomGestureService customGestureService;

    /**
     * 获取缓存数据（用于预览）
     * GET /api/annotation/cache-data?device_id=orangepi_01&start_time=xxx&end_time=xxx
     */
    @GetMapping("/cache-data")
    public Map<String, Object> getCacheData(
            @RequestParam(required = false, defaultValue = "orangepi_01") String deviceId,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime) {
        
        Map<String, Object> result = new HashMap<>();
        try {
            LocalDateTime start = startTime != null ? LocalDateTime.parse(startTime) : LocalDateTime.now().minusMinutes(1);
            LocalDateTime end = endTime != null ? LocalDateTime.parse(endTime) : LocalDateTime.now();
            
            Map<String, Object> cacheData = annotationService.getCacheData(deviceId, start, end);
            result.put("code", 200);
            result.put("data", cacheData);
        } catch (Exception e) {
            log.error("获取缓存数据失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 保存标注数据
     * POST /api/annotation/save
     * Body: { deviceId, startTime, endTime, gestureLabel, annotator }
     */
    @PostMapping("/save")
    public Map<String, Object> saveAnnotation(@RequestBody AnnotationRequest request) {
        Map<String, Object> result = new HashMap<>();
        try {
            log.info("收到标注请求: 设备={}, 手势={}, 时间={}~{}", 
                    request.getDeviceId(), request.getGestureLabel(), 
                    request.getStartTime(), request.getEndTime());
            
            Map<String, Object> saveResult = annotationService.saveAnnotation(request);
            
            result.put("code", 200);
            result.put("message", "标注保存成功");
            result.put("data", saveResult);
            
            log.info("标注保存成功: 保存了 {} 帧数据", saveResult.get("saved_count"));
        } catch (Exception e) {
            log.error("保存标注失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", "保存失败: " + e.getMessage());
        }
        return result;
    }

    /**
     * 查询标注数据统计
     * GET /api/annotation/statistics
     */
    @GetMapping("/statistics")
    public Map<String, Object> getStatistics() {
        Map<String, Object> result = new HashMap<>();
        try {
            Map<String, Object> stats = annotationService.getAnnotationStatistics();
            result.put("code", 200);
            result.put("data", stats);
        } catch (Exception e) {
            log.error("获取统计信息失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 开始录制标注数据
     * POST /api/annotation/start
     * Body: { gesture, duration }
     */
    @PostMapping("/start")
    public Map<String, Object> startRecording(@RequestBody Map<String, Object> request) {
        Map<String, Object> result = new HashMap<>();
        try {
            String gesture = (String) request.get("gesture");
            Integer duration = (Integer) request.get("duration");
            
            log.info("开始录制: 手势={}, 时长={}秒", gesture, duration);
            
            Map<String, Object> startResult = new HashMap<>();
            startResult.put("recordingId", System.currentTimeMillis());
            startResult.put("gesture", gesture);
            startResult.put("duration", duration);
            startResult.put("startTime", LocalDateTime.now().toString());
            
            result.put("code", 200);
            result.put("message", "录制已启动");
            result.put("data", startResult);
            
            log.info("录制启动成功，ID={}", startResult.get("recordingId"));
        } catch (Exception e) {
            log.error("启动录制失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", "启动录制失败: " + e.getMessage());
        }
        return result;
    }

    /**
     * 停止录制标注数据
     * POST /api/annotation/stop
     * Body: { gesture }
     */
    @PostMapping("/stop")
    public Map<String, Object> stopRecording(@RequestBody Map<String, Object> request) {
        Map<String, Object> result = new HashMap<>();
        try {
            String gesture = (String) request.get("gesture");
            
            log.info("停止录制: 手势={}", gesture);
            
            // 模拟返回样本统计
            Map<String, Object> stopResult = new HashMap<>();
            stopResult.put("recordingId", System.currentTimeMillis());
            stopResult.put("gesture", gesture);
            stopResult.put("sampleCount", 150);  // 模拟150个样本
            stopResult.put("qualityScore", 0.92);  // 质量评分
            stopResult.put("uploadedTime", LocalDateTime.now().toString());
            
            result.put("code", 200);
            result.put("message", "录制已停止");
            result.put("data", stopResult);
            
            log.info("录制停止成功，保存了 {} 个样本", stopResult.get("sampleCount"));
        } catch (Exception e) {
            log.error("停止录制失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", "停止录制失败: " + e.getMessage());
        }
        return result;
    }

    /**
     * 获取标注统计信息
     * GET /api/annotation/stats
     */
    @GetMapping("/stats")
    public Map<String, Object> getStats() {
        Map<String, Object> result = new HashMap<>();
        try {
            Map<String, Object> stats = new HashMap<>();
            stats.put("totalSamples", 1500);
            stats.put("cachedSamples", 45);
            stats.put("gestureCounts", new java.util.ArrayList<>() {{
                add(new java.util.HashMap<String, Object>() {{ put("gesture", "fist"); put("count", 250); }});
                add(new java.util.HashMap<String, Object>() {{ put("gesture", "ok"); put("count", 280); }});
                add(new java.util.HashMap<String, Object>() {{ put("gesture", "pinch"); put("count", 200); }});
                add(new java.util.HashMap<String, Object>() {{ put("gesture", "relax"); put("count", 220); }});
                add(new java.util.HashMap<String, Object>() {{ put("gesture", "sidegrip"); put("count", 265); }});
                add(new java.util.HashMap<String, Object>() {{ put("gesture", "ye"); put("count", 285); }});
            }});
            
            result.put("code", 200);
            result.put("data", stats);
        } catch (Exception e) {
            log.error("获取统计信息失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 获取最近的标注记录
     * GET /api/annotation/records?limit=10
     */
    @GetMapping("/records")
    public Map<String, Object> getRecords(
            @RequestParam(defaultValue = "10") int limit) {
        Map<String, Object> result = new HashMap<>();
        try {
            java.util.List<Map<String, Object>> records = new java.util.ArrayList<>();
            // 模拟返回最近的记录
            for (int i = 0; i < Math.min(limit, 5); i++) {
                final int index = i;
                records.add(new java.util.HashMap<String, Object>() {{
                    put("id", index + 1);
                    put("gesture", new String[]{"fist", "ok", "pinch", "relax", "sidegrip"}[index % 5]);
                    put("duration", 3 + index % 3);
                    put("sampleCount", 150 + index * 10);
                    put("quality", 0.8 + (index * 0.02));
                    put("createdTime", LocalDateTime.now().minusDays(index).toString());
                }});
            }
            
            result.put("code", 200);
            result.put("data", records);
        } catch (Exception e) {
            log.error("获取记录失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }
    public Map<String, Object> deleteAnnotation(@PathVariable Long id) {
        Map<String, Object> result = new HashMap<>();
        try {
            annotationService.deleteAnnotation(id);
            result.put("code", 200);
            result.put("message", "删除成功");
        } catch (Exception e) {
            log.error("删除标注失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 查询标注历史
     * GET /api/annotation/history?gesture=fist&limit=100
     */
    @GetMapping("/history")
    public Map<String, Object> getHistory(
            @RequestParam(required = false) String gesture,
            @RequestParam(required = false) String annotator,
            @RequestParam(defaultValue = "100") int limit) {
        
        Map<String, Object> result = new HashMap<>();
        try {
            result.put("code", 200);
            result.put("data", annotationService.getHistory(gesture, annotator, limit));
        } catch (Exception e) {
            log.error("查询历史失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 保存自定义手势
     * POST /api/annotation/custom-gestures
     * Body: { deviceId, gestureId, gestureLabel, gestureIcon }
     */
    @PostMapping("/custom-gestures")
    public Map<String, Object> saveCustomGesture(@RequestBody Map<String, String> request) {
        Map<String, Object> result = new HashMap<>();
        try {
            String deviceId = request.get("deviceId");
            String gestureId = request.get("gestureId");
            String gestureLabel = request.get("gestureLabel");
            String gestureIcon = request.get("gestureIcon");
            
            // 参数校验
            if (deviceId == null || deviceId.isEmpty() || 
                gestureId == null || gestureId.isEmpty() ||
                gestureLabel == null || gestureLabel.isEmpty() ||
                gestureIcon == null || gestureIcon.isEmpty()) {
                result.put("code", 400);
                result.put("message", "缺少必要参数：deviceId, gestureId, gestureLabel, gestureIcon");
                return result;
            }
            
            log.info("保存自定义手势: 设备={}, 手势ID={}, 标签={}, 图标={}", 
                    deviceId, gestureId, gestureLabel, gestureIcon);
            
            // 调用Service保存到数据库
            CustomGesture savedGesture = customGestureService.saveCustomGesture(
                    deviceId, gestureId, gestureLabel, gestureIcon);
            
            result.put("code", 200);
            result.put("message", "自定义手势保存成功");
            result.put("data", savedGesture);
        } catch (Exception e) {
            log.error("保存自定义手势失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", "保存失败: " + e.getMessage());
        }
        return result;
    }

    /**
     * 获取用户的所有自定义手势
     * GET /api/annotation/custom-gestures?deviceId=xxx
     */
    @GetMapping("/custom-gestures")
    public Map<String, Object> getCustomGestures(
            @RequestParam String deviceId) {
        Map<String, Object> result = new HashMap<>();
        try {
            if (deviceId == null || deviceId.isEmpty()) {
                result.put("code", 400);
                result.put("message", "deviceId 不能为空");
                return result;
            }
            
            log.info("查询自定义手势: 设备={}", deviceId);
            
            // 调用Service查询数据库
            java.util.List<CustomGesture> customGestures = customGestureService.getActiveCustomGestures(deviceId);
            
            result.put("code", 200);
            result.put("message", "查询成功");
            result.put("data", customGestures);
        } catch (Exception e) {
            log.error("查询自定义手势失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", "查询失败: " + e.getMessage());
        }
        return result;
    }

    /**
     * 删除用户的自定义手势
     * DELETE /api/annotation/custom-gestures?deviceId=xxx&gestureId=xxx
     */
    @DeleteMapping("/custom-gestures")
    public Map<String, Object> deleteCustomGesture(
            @RequestParam String deviceId,
            @RequestParam String gestureId) {
        Map<String, Object> result = new HashMap<>();
        try {
            if (deviceId == null || deviceId.isEmpty() || gestureId == null || gestureId.isEmpty()) {
                result.put("code", 400);
                result.put("message", "deviceId 和 gestureId 不能为空");
                return result;
            }
            
            log.info("删除自定义手势: 设备={}, 手势ID={}", deviceId, gestureId);
            
            // 调用Service删除（软删除）
            boolean deleted = customGestureService.deleteCustomGesture(deviceId, gestureId);
            
            if (deleted) {
                result.put("code", 200);
                result.put("message", "自定义手势删除成功");
            } else {
                result.put("code", 404);
                result.put("message", "手势不存在");
            }
        } catch (Exception e) {
            log.error("删除自定义手势失败: {}", e.getMessage());
            result.put("code", 500);
            result.put("message", "删除失败: " + e.getMessage());
        }
        return result;
    }
}


