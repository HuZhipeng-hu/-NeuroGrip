package com.huaweiict.emg.service;

import com.huaweiict.emg.dto.ApiResponse;
import com.huaweiict.emg.dto.AuthRequest;
import com.huaweiict.emg.entity.User;
import com.huaweiict.emg.repository.UserRepository;
import com.huaweiict.emg.util.JwtUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private JwtUtil jwtUtil;

    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    public ApiResponse register(AuthRequest request) {
        if (userRepository.findByUsername(request.getUsername()).isPresent()) {
            throw new RuntimeException("用户名已存在");
        }
        String hashedPassword = passwordEncoder.encode(request.getPassword());
        User user = new User(request.getUsername(), hashedPassword);
        userRepository.save(user);
        return new ApiResponse("注册成功", null);
    }

    public ApiResponse login(AuthRequest request) {
        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new RuntimeException("用户不存在"));
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new RuntimeException("密码错误");
        }

        // 生成 JWT token
        String token = jwtUtil.generateToken(user.getUsername());
        return new ApiResponse("登录成功", token);
    }
}
