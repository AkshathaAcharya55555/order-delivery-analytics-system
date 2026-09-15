package com.orderdelivery.trackingservice.repository;

import com.orderdelivery.trackingservice.entity.Order;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OrderRepository extends JpaRepository<Order, Long> {
}
