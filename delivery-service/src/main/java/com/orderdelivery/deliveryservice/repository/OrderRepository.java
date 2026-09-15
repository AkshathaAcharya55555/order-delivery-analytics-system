package com.orderdelivery.deliveryservice.repository;

import com.orderdelivery.deliveryservice.entity.Order;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OrderRepository extends JpaRepository<Order, Long> {
}
