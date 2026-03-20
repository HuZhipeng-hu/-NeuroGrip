package com.huaweiict.emg.repository;

import com.huaweiict.emg.model.CustomGesture;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 自定义手势数据访问层
 */
@Repository
public interface CustomGestureRepository extends JpaRepository<CustomGesture, Long> {
    
    /**
     * 根据设备ID查询所有激活的自定义手势
     */
    List<CustomGesture> findByDeviceIdAndIsActive(String deviceId, Boolean isActive);
    
    /**
     * 查询所有自定义手势（包括已删除的）
     */
    List<CustomGesture> findByDeviceId(String deviceId);
    
    /**
     * 根据设备ID和手势ID查询
     */
    Optional<CustomGesture> findByDeviceIdAndGestureId(String deviceId, String gestureId);
    
    /**
     * 检查是否存在相同的手势（按设备和手势ID）
     */
    boolean existsByDeviceIdAndGestureId(String deviceId, String gestureId);
}
