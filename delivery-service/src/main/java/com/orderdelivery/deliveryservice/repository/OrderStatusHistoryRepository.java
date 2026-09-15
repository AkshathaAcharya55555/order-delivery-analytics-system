package com.orderdelivery.deliveryservice.repository;

import com.orderdelivery.deliveryservice.entity.OrderStatusHistory;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OrderStatusHistoryRepository extends JpaRepository<OrderStatusHistory, Long> {
}
