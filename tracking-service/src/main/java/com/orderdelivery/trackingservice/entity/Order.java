package com.orderdelivery.trackingservice.entity;

import com.orderdelivery.trackingservice.model.OrderStatus;
import jakarta.persistence.*;

/** Trimmed view of the orders table: this service only reads/writes order_id and status. */
@Entity
@Table(name = "orders")
public class Order {

    @Id
    @Column(name = "order_id")
    private Long orderId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private OrderStatus status;

    protected Order() {
    }

    public Long getOrderId() {
        return orderId;
    }

    public OrderStatus getStatus() {
        return status;
    }

    public void setStatus(OrderStatus status) {
        this.status = status;
    }
}
