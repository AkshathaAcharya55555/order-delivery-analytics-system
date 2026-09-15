package com.orderdelivery.orderservice.repository;

import com.orderdelivery.orderservice.entity.Order;
import com.orderdelivery.orderservice.model.OrderStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OrderRepository extends JpaRepository<Order, Long> {
    Page<Order> findByStatus(OrderStatus status, Pageable pageable);
}
