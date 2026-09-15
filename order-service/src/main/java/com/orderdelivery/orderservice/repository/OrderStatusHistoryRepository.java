package com.orderdelivery.orderservice.repository;

import com.orderdelivery.orderservice.entity.OrderStatusHistory;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OrderStatusHistoryRepository extends JpaRepository<OrderStatusHistory, Long> {
}
