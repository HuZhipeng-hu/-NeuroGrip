package com.huaweiict.emg.service;

import com.huaweiict.emg.model.CustomGesture;
import com.huaweiict.emg.repository.CustomGestureRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * 自定义手势服务类
 */
@Slf4j
@Service
public class CustomGestureService {
    
    @Autowired
    private CustomGestureRepository customGestureRepository;
    
    /**
     * 保存或更新自定义手势
     */
    @Transactional
    public CustomGesture saveCustomGesture(String deviceId, String gestureId, String gestureLabel, String gestureIcon) {
        log.info("保存自定义手势: deviceId={}, gestureId={}, label={}", deviceId, gestureId, gestureLabel);
        
        // 检查是否已存在
        Optional<CustomGesture> existing = customGestureRepository.findByDeviceIdAndGestureId(deviceId, gestureId);
        
        CustomGesture gesture;
        if (existing.isPresent()) {
            gesture = existing.get();
            gesture.setGestureLabel(gestureLabel);
            gesture.setGestureIcon(gestureIcon);
            gesture.setIsActive(true);
            gesture.setUpdatedAt(LocalDateTime.now());
            log.info("更新已存在的手势: id={}", gesture.getId());
        } else {
            gesture = new CustomGesture();
            gesture.setDeviceId(deviceId);
            gesture.setGestureId(gestureId);
            gesture.setGestureLabel(gestureLabel);
            gesture.setGestureIcon(gestureIcon);
            gesture.setUseCount(0);
            gesture.setIsActive(true);
            gesture.setCreatedAt(LocalDateTime.now());
            gesture.setUpdatedAt(LocalDateTime.now());
            log.info("创建新手势");
        }
        
        return customGestureRepository.save(gesture);
    }
    
    /**
     * 获取用户的所有激活手势
     */
    public List<CustomGesture> getActiveCustomGestures(String deviceId) {
        log.info("查询用户激活的自定义手势: deviceId={}", deviceId);
        return customGestureRepository.findByDeviceIdAndIsActive(deviceId, true);
    }
    
    /**
     * 获取用户的所有手势（包括已删除的）
     */
    public List<CustomGesture> getAllCustomGestures(String deviceId) {
        log.info("查询用户所有自定义手势: deviceId={}", deviceId);
        return customGestureRepository.findByDeviceId(deviceId);
    }
    
    /**
     * 删除自定义手势（软删除）
     */
    @Transactional
    public boolean deleteCustomGesture(String deviceId, String gestureId) {
        log.info("删除自定义手势: deviceId={}, gestureId={}", deviceId, gestureId);
        
        Optional<CustomGesture> gesture = customGestureRepository.findByDeviceIdAndGestureId(deviceId, gestureId);
        
        if (gesture.isPresent()) {
            CustomGesture g = gesture.get();
            g.setIsActive(false);
            g.setUpdatedAt(LocalDateTime.now());
            customGestureRepository.save(g);
            log.info("手势已标记为删除: id={}", g.getId());
            return true;
        } else {
            log.warn("手势不存在: deviceId={}, gestureId={}", deviceId, gestureId);
            return false;
        }
    }
    
    /**
     * 增加手势使用次数
     */
    @Transactional
    public void incrementUseCount(String deviceId, String gestureId) {
        Optional<CustomGesture> gesture = customGestureRepository.findByDeviceIdAndGestureId(deviceId, gestureId);
        
        if (gesture.isPresent()) {
            CustomGesture g = gesture.get();
            g.setUseCount(g.getUseCount() + 1);
            g.setUpdatedAt(LocalDateTime.now());
            customGestureRepository.save(g);
            log.debug("手势使用次数已更新: id={}, count={}", g.getId(), g.getUseCount());
        }
    }
    
    /**
     * 检查手势是否存在
     */
    public boolean existsCustomGesture(String deviceId, String gestureId) {
        return customGestureRepository.existsByDeviceIdAndGestureId(deviceId, gestureId);
    }
}
