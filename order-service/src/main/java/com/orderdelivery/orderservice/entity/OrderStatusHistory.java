package com.orderdelivery.orderservice.entity;

import com.orderdelivery.orderservice.model.OrderStatus;
import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "order_status_history")
public class OrderStatusHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "history_id")
    private Long historyId;

    @Column(name = "order_id", nullable = false)
    private Long orderId;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 20)
    private OrderStatus status;

    @Column(name = "changed_at", nullable = false)
    private LocalDateTime changedAt;

    protected OrderStatusHistory() {
    }

    public OrderStatusHistory(Long orderId, OrderStatus status, LocalDateTime changedAt) {
        this.orderId = orderId;
        this.status = status;
        this.changedAt = changedAt;
    }

    public Long getHistoryId() {
        return historyId;
    }

    public Long getOrderId() {
        return orderId;
    }

    public OrderStatus getStatus() {
        return status;
    }

    public LocalDateTime getChangedAt() {
        return changedAt;
    }
}
